"""Changing the user's settings and watched companies, one checked change at a time.

Every change is validated before anything is written: a pattern must compile, a number must be a
number, a key must be one the engine knows, and a label may only use its own placeholders. A
refused change leaves the file exactly as it was.
"""

import os
import re

from . import changes, settings, tomlwrite
from .boards import READERS
from .clock import Clock
from .errors import Refused
from .toml import load_file

PATTERN, NUMBER, TEXT = "pattern", "number", "text"

KNOWN = {
    "you": {"timezone": TEXT, "name": TEXT},
    "titles": {"function": PATTERN, "level": PATTERN, "exclude": PATTERN, "field_words": PATTERN},
    "places": {k: PATTERN for k in ("remote", "hybrid_ok", "remote_only", "in_country", "country_wide", "abroad")},
    "description": {k: PATTERN for k in ("remote_language", "contract", "onsite_days", "onsite_place")},
    "pay": {"reject_if_top_below": NUMBER},
    "workday": {"country_facet": PATTERN, "max_total": NUMBER},
    "triage": {"cooldown_days": NUMBER},
    "tracking": {"follow_up_after_days": NUMBER, "presume_after_days": NUMBER},
    "page": {"url": TEXT, "version": TEXT, "route": ("", "storage", "republish", "file"), "pushed": TEXT},
    "schedule": {"scan": ("", "daily", "weekdays", "weekly"), "review": ("", "weekly")},
    "labels": {k: TEXT for k in settings.DEFAULT_LABELS},
}

# The placeholders each label may use.
LABEL_FIELDS = {
    "flag_contract": {"phrase"}, "flag_onsite": {"quote"}, "flag_applied": {"applied"}, "flag_pasted": {"date"},
    "reason_in_country": {"location"}, "reason_remote_only": {"location"}, "reason_phrase": {"hits"},
    "reason_pay": {"top_k", "low_k", "line_k"}, "reason_abroad": {"location"},
}

# What each board system needs in its companies.toml entry.
NEEDS = {"greenhouse": ("token",), "ashby": ("token",), "lever": ("token",), "smartrecruiters": ("token",),
         "rippling": ("token",), "workday": ("host", "tenant", "site"), "careers_api": ("host",),
         "talentbrew": ("host",), "atlassian": (), "himalayas": ("queries",), "manual": ("careers_url",)}


def _paths(folder):
    return os.path.join(folder, "profile", "settings.toml"), os.path.join(folder, "profile", "companies.toml")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def check_pattern(p):
    try:
        re.compile(p, re.I)
    except re.error as e:
        raise Refused(f"that pattern doesn't work: {e}") from None


def check_label(name, template):
    allowed = LABEL_FIELDS.get(name, set())
    used = set(re.findall(r"{(\w+)}", template))
    if used - allowed:
        raise Refused(f"{name} can only use {sorted(allowed) or 'no'} placeholders, not {sorted(used - allowed)}")
    try:
        template.format(**{k: "x" for k in allowed})
    except (KeyError, IndexError, ValueError) as e:
        raise Refused(f"{name} isn't a usable template: {e}") from None


def show(folder):
    return load_file(_paths(folder)[0])


def coerce(key, raw_value):
    """(section, name, value) for a setting given as text, checked. Refused if it isn't right."""
    if "." not in key:
        raise Refused("give the setting as section.name, for example titles.function")
    section, name = key.split(".", 1)
    kind = KNOWN.get(section, {}).get(name)
    if kind is None:
        raise Refused(f"there's no setting called {key}")
    if isinstance(kind, tuple):  # one of a few words
        if raw_value not in kind:
            raise Refused(f"{key} is one of {', '.join(repr(k) for k in kind)}")
        new = raw_value
    elif kind == NUMBER:
        try:
            new = int(raw_value)
        except ValueError:
            raise Refused(f"{key} has to be a whole number") from None
    else:
        new = raw_value
        if kind == PATTERN and new:
            check_pattern(new)
        if section == "labels":
            check_label(name, new)
    return section, name, new


def set_value(folder, key, raw_value, why="", accept=(), clock=None, setup=False):
    """Set `section.key` to a value given as text. Returns (old, new).

    Once there are saved postings, a change to how they're screened needs a replay of exactly this
    change first, the user's words (`why`), and their acceptance of any job they applied to or wanted
    that it would turn away (changes.guard). It is then logged in data/changes.log."""
    section, name, new = coerce(key, raw_value)
    path = _paths(folder)[0]
    text = _read(path)
    raw = load_file(path)
    old = raw.get(section, {}).get(name)
    kind = changes.guard_kind(key)
    rep = None
    if kind and not (setup and changes.setup_allowed(folder)):
        clk = clock or Clock(settings.parse(raw).timezone)
        rep = changes.guard(folder, kind, lambda ch: _covers(ch, kind, key, new), accept, why, clk)
    raw.setdefault(section, {})[name] = new
    settings.parse(raw)  # the whole file must still load
    _write(path, tomlwrite.settings_text(raw, tomlwrite.header_of(text)))
    if rep is not None:
        changes.log(folder, clk, f"setting {key}", "changed", old, new, why, rep, accept)
    return old, new


def _covers(change, kind, key, value):
    if kind == "titles":
        return change.get(key) == value
    return [key, value] in (change.get("set") or [])


def phrase_rule(name, phrases, min_distinct=2, reason="", same_as=None):
    """A phrase rule as it would be saved, checked."""
    check_pattern(phrases)
    if min_distinct < 1:
        raise Refused("min-distinct has to be at least 1")
    if reason:
        used = set(re.findall(r"{(\w+)}", reason))
        if used - {"hits"}:
            raise Refused("a phrase rule's reason can only use {hits}")
    rule = {"name": name, "phrases": phrases, "min_distinct": min_distinct}
    if same_as:
        rule["same_as"] = same_as
    if reason:
        rule["reason"] = reason
    return rule


def phrase_reject(folder, name, phrases, min_distinct=2, reason="", same_as=None, why="", accept=(), clock=None,
                  setup=False):
    """Add a phrase rule, or replace the one with the same name. Guarded like set_value."""
    rule = phrase_rule(name, phrases, min_distinct, reason, same_as)
    path = _paths(folder)[0]
    text = _read(path)
    raw = load_file(path)
    clk = clock or Clock(settings.parse(raw).timezone)
    rep = None
    if not (setup and changes.setup_allowed(folder)):
        rep = changes.guard(folder, "settings", lambda ch: ch.get("phrase_reject") == rule, accept, why, clk)
    old = next((r for r in raw.get("phrase_rejects", []) if r.get("name") == name), None)
    rules = [r for r in raw.get("phrase_rejects", []) if r.get("name") != name] + [rule]
    raw["phrase_rejects"] = rules
    settings.parse(raw)
    _write(path, tomlwrite.settings_text(raw, tomlwrite.header_of(text)))
    if rep is not None:
        changes.log(folder, clk, f"phrase rule {name}", "changed", old, rule, why, rep, accept)
    return rule


def list_companies(folder):
    return settings.load_companies(folder)


def add_company(folder, entry):
    entry = {k: v for k, v in entry.items() if v not in (None, "", [])}
    ats = entry.get("ats", "")
    if ats not in NEEDS:
        raise Refused(f"unknown board system {ats!r}; one of {', '.join(sorted(NEEDS))}")
    missing = [k for k in ("name", "slug") + NEEDS[ats] if not entry.get(k)]
    if missing:
        raise Refused(f"a {ats} board needs {', '.join(missing)}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", entry["slug"]):
        raise Refused("a slug is lower-case letters, digits and dashes")
    path = _paths(folder)[1]
    text = _read(path) if os.path.exists(path) else ""
    companies = load_file(path).get("company", []) if text else []
    if any(c["slug"] == entry["slug"] for c in companies):
        raise Refused(f"{entry['slug']} is already on the list")
    order = ("name", "slug", "ats", "token", "host", "tenant", "site", "queries", "careers_url")
    companies.append({k: entry[k] for k in order if k in entry})
    _write(path, tomlwrite.companies_text(companies, tomlwrite.header_of(text)))
    return companies[-1]


def drop_company(folder, slug):
    """Take a company off the list. Its saved postings and verdicts stay."""
    path = _paths(folder)[1]
    text = _read(path)
    companies = load_file(path).get("company", [])
    keep = [c for c in companies if c["slug"] != slug]
    if len(keep) == len(companies):
        raise Refused(f"{slug} isn't on the list")
    _write(path, tomlwrite.companies_text(keep, tomlwrite.header_of(text)))
    return len(keep)


assert set(NEEDS) - {"manual"} == set(READERS), "every board reader needs an entry in NEEDS"
