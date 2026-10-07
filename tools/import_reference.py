#!/usr/bin/env python3
"""
Convert the reference scanner's files into job-search-kit's formats. A development tool, not
part of the kit: it exists to prove the engine matches the scanner it was ported from, and to
move that scanner's one user onto the kit.

    python tools/import_reference.py --config config.toml --watchlist watchlist.toml \
        [--pipeline pipeline.md] [--relative-dates dates.json] [--labels labels.json] \
        [--seen seen.json --postings-dir postings/] [--triage-log triage-log.md] \
        [--timezone Area/City] --out <folder>

Writes <folder>/profile/settings.toml, <folder>/profile/companies.toml and
<folder>/data/applications.json; with --seen, also data/postings.json and the saved descriptions;
with --triage-log, also data/decisions.log. It refuses to write inside this repository, because
the result is one person's data.

--relative-dates maps the tracker's relative application dates ("1w") to the date each meant,
as a JSON object. Without it those applications keep an unknown date.

--labels is a JSON file of settings.toml [labels] wording (flag_in_country, reason_pay, ...), for
reproducing the reference scanner's exact flag and reason text. Without it the kit's plain
defaults are used.
"""

import argparse
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "plugins", "job-search", "engine"))
sys.dont_write_bytecode = True

from jobkit.toml import load_file  # noqa: E402
from jobkit.track import normalize as normalize_application  # noqa: E402
from jobkit.tomlwrite import value as toml_value  # noqa: E402

# Reference config.toml [location] keys -> settings.toml [places] keys.
PLACES = {"remote": "remote", "bay_core": "hybrid_ok", "bay_outer": "remote_only",
          "us": "in_country", "us_national": "country_wide", "drop": "abroad"}


def settings_toml(config, labels, timezone):
    t, loc = config.get("titles", {}), config.get("location", {})
    out = ["# Converted from the reference scanner's config.toml by tools/import_reference.py.", ""]
    out += ["[you]", f"timezone = {toml_value(timezone)}", ""]
    out += ["[titles]"] + [f"{k} = {toml_value(t[k])}" for k in ("function", "level", "exclude") if k in t] + [""]
    out += ["[places]"] + [f"{new} = {toml_value(loc[old])}" for old, new in PLACES.items() if old in loc] + [""]
    desc = {"remote_language": loc.get("remote_language"), "contract": t.get("contract"),
            "onsite_days": loc.get("onsite_days"), "onsite_place": loc.get("onsite_place")}
    out += ["[description]"] + [f"{k} = {toml_value(v)}" for k, v in desc.items() if v] + [""]
    if t.get("renewals"):
        # The reference counts two distinct phrases, with "net revenue retention" and "NRR" as one.
        out += ["[[phrase_rejects]]", 'name = "renewals"', f"phrases = {toml_value(t['renewals'])}", "min_distinct = 2",
                'same_as = { "net revenue retention" = "nrr" }']
        if labels.get("reason_renewals"):
            out.append(f"reason = {toml_value(labels['reason_renewals'])}")
        out.append("")
    out += ["[pay]", f"reject_if_top_below = {int((config.get('pay') or {}).get('reject_if_top_below', 0))}", ""]
    wd = config.get("workday", {})
    out += ["[workday]", f"country_facet = {toml_value(wd.get('country_facet', ''))}",
            f"max_total = {int(wd.get('max_total', 2000))}", ""]
    kit_labels = {k: v for k, v in labels.items() if k != "reason_renewals"}
    if kit_labels:
        out += ["[labels]"] + [f"{k} = {toml_value(v)}" for k, v in kit_labels.items()] + [""]
    return "\n".join(out)


def companies_toml(watchlist):
    out = ["# Converted from the reference scanner's watchlist.toml by tools/import_reference.py.", ""]
    for c in watchlist.get("company", []):
        out.append("[[company]]")
        out += [f"{k} = {toml_value(v)}" for k, v in c.items()]
        out.append("")
    return "\n".join(out)


_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_LINK_URLS = re.compile(r"\]\((https?://[^)]+)\)")
# "Role ([posting](url))": the link is kept in urls, and the word "posting" isn't part of the role.
_POSTING_LINK = re.compile(r"\s*\(\s*\[posting\]\([^)]*\)\s*\)", re.I)


def plain(cell):
    """A table cell without its markdown emphasis: **bold**, *italic*, `code`."""
    return re.sub(r"[*`]", "", cell or "").strip()


def role_text(cell):
    return plain(_LINK.sub(r"\1", _POSTING_LINK.sub("", cell or "")))


def level_parts(cell):
    """("Manager", "8 PMs") from "Manager, 8 PMs": the level the tracker gave, and its detail."""
    level, _, detail = plain(cell).partition(", ")
    return level.strip(), detail.strip()


def applied_date(cell, relative):
    """(ISO date, estimated): a date written in the cell, or a relative label mapped through `relative`."""
    cell = re.sub(r"[*`]", "", cell or "").strip()
    m = re.search(r"\d{4}-\d{2}-\d{2}", cell)
    if m:
        return m.group(0), False
    if cell in relative:
        return relative[cell], True
    return "", False


def applications(pipeline_text, relative=None):
    """Rows of the first table under '## Applied', in the reference tracker's 8- or 9-column shape:
    Company | Role | Fit | Level | Pay | Applied | (Followed up) | Status | Note. Each is written in the
    kit's application shape (jobkit/track.py), with the tracker's own status words kept as status_was."""
    m = re.search(r"^## Applied\s*$(.*?)^## ", pipeline_text, re.M | re.S)
    if not m:
        return []
    rows = []
    for line in m.group(1).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) not in (8, 9) or cells[0] == "Company" or set(cells[0]) <= {"-"}:
            continue
        if len(cells) == 8:
            cells.insert(6, "")
        company, role, fit, level, pay, applied, followed, status, note = cells
        when, estimated = applied_date(applied, relative or {})
        level, level_detail = level_parts(level)
        followed_on, _ = applied_date(followed, {})  # a date, or nothing: "—" isn't a follow-up
        row = {
            "company": plain(company),
            "role": role_text(role),
            "urls": _LINK_URLS.findall(role),
            "fit": plain(fit), "level": level, "posted_pay": plain(pay),
            "applied": applied,
            "applied_date": when,
            "applied_date_estimated": estimated,
            "followed_up": followed_on, "status": status, "note": note,
        }
        if level_detail:
            row["level_detail"] = level_detail
        rows.append(normalize_application(row))
    return rows


# The reference's "closed" (the job came down) has no status of its own in the kit: it is skipped,
# with "No longer open" in front of its note, so it shows and reads the same as the page's own button.
STATUS = {"new": "new", "apply": "worth_applying", "maybe": "your_call", "reject": "not_a_fit",
          "skipped": "skipped", "applied": "applied", "closed": "skipped"}
VERDICT = {"APPLY": "worth_applying", "MAYBE": "your_call", "REJECT": "not_a_fit", "SKIPPED": "skipped",
           "APPLIED": "applied", "CLOSED": "skipped"}
NO_LONGER_OPEN = "No longer open"


def _closed_note(note):
    if (note or "").lower().startswith(NO_LONGER_OPEN.lower()):
        return note  # it says so already
    return f"{NO_LONGER_OPEN}: {note}" if note else NO_LONGER_OPEN


def rule_of(note):
    """The kit's rule id for a reference verdict note, or ""."""
    note = note or ""
    if note.startswith("Location rule, applied by the scanner"):
        return "location_remote_only" if " is the outer " in note else "location_in_country"
    if note.startswith("Rule 5, applied by the scanner"):
        return "phrases:renewals"
    if note.startswith("Rule 12, applied by the scanner"):
        return "pay"
    m = re.match(r"\s*Rule (\d+)", note)
    return f"rule {m.group(1)}" if m else ""  # the engine's own id for a rules.md rule (review.rule_of)


def postings(seen, descriptions_from, out):
    """The reference memory as the kit's postings.json, and its saved descriptions copied across."""
    kit = {"postings": {}, "boards": dict(seen.get("sources", {}))}
    copied = 0
    os.makedirs(os.path.join(out, "data", "postings"), exist_ok=True)
    for k, v in seen.get("postings", {}).items():
        e = {x: v[x] for x in ("salary", "first_seen", "last_seen", "company", "title", "location", "url", "posted",
                               "source", "flag", "file", "note", "triaged", "gone") if x in v}
        e["status"] = STATUS.get(v.get("status"), v.get("status"))
        if v.get("status") == "closed":
            e["note"] = _closed_note(v.get("note", ""))
        e["flags"] = [{"code": "imported", "text": t} for t in (v.get("flag") or "").split("; ") if t]
        if rule_of(v.get("note")):
            e["rule"] = rule_of(v.get("note"))
        src = os.path.join(descriptions_from, v.get("file") or f"{k}.md")
        if os.path.exists(src):
            with open(src, encoding="utf-8") as f:
                text = f.read()
            with open(os.path.join(out, "data", "postings", os.path.basename(src)), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            copied += 1
        kit["postings"][k] = e
    return kit, copied


def _log_row(line):
    """A triage-log row as (date, company, title, verdict, reason, key), or None. Found by the verdict
    cell's value rather than its place, because a job title can itself contain a "|"."""
    if not re.match(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|", line):
        return None
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 6:
        return None
    known = [i for i in range(3, len(cells) - 1) if cells[i] in VERDICT]
    other = [i for i in range(3, len(cells) - 1) if re.fullmatch(r"[A-Z]+", cells[i])]  # CLOSED, say
    for i in (known or other)[:1]:
        return cells[0], cells[1], " | ".join(cells[2:i]), cells[i], " | ".join(cells[i + 1:-1]), cells[-1]
    return None


# A verdict clicked on the reference's own page starts "page:", after any "REVERSAL of X." or a cell bar.
_CLICKED = re.compile(r"(?:^|\|\s*|REVERSAL of [A-Z]+\.\s*)page:")


def decisions(log_text):
    """The reference triage log as decisions.log rows. A verdict clicked on the reference's own page
    is the user's decision; every other row was Claude's."""
    rows = []
    for line in log_text.splitlines():
        m = _log_row(line)
        if not m:
            continue
        date, company, title, verdict, why, key = m
        why = why.strip()
        if verdict == "CLOSED":
            why = _closed_note(why)
        row = {"date": date, "key": key, "company": company.strip(), "title": title.strip(),
               "verdict": VERDICT.get(verdict, verdict.lower()), "reason": why,
               "by": "user" if _CLICKED.search(why) else "claude"}
        rev = re.search(r"REVERSAL of ([A-Z]+)", why)
        if rev:
            row["reverses"] = VERDICT.get(rev.group(1), rev.group(1).lower())
        if rule_of(why):
            row["rule"] = rule_of(why)
        rows.append(row)
    return rows


def join(apps, kit_postings):
    """Give each imported application its saved posting's key, so the two read as one job: the one
    applied-to posting it matches (the same link, or the same company and title), when that posting
    matches no other application. The rest stay recorded by company and role, as before. Returns
    how many were joined."""
    from jobkit.store import application_for
    claims = {}
    for i, app in enumerate(apps):
        if app.get("key"):
            continue
        found = [k for k, v in kit_postings.items() if v.get("status") == "applied" and application_for(
            {"company": v.get("company", ""), "title": v.get("title", ""), "url": v.get("url", "")}, [app])]
        if len(found) == 1:
            claims.setdefault(found[0], []).append(i)
    joined = 0
    for k, idx in claims.items():
        if len(idx) != 1:
            continue  # two applications to one posting (applied twice?): leave both by name
        app = apps[idx[0]]
        app["key"] = k
        url = kit_postings[k].get("url")
        if url and url not in app.setdefault("urls", []):
            app["urls"].append(url)
        joined += 1
    return joined


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--config", required=True)
    p.add_argument("--watchlist", required=True)
    p.add_argument("--pipeline")
    p.add_argument("--relative-dates")
    p.add_argument("--labels")
    p.add_argument("--seen")
    p.add_argument("--postings-dir")
    p.add_argument("--triage-log")
    p.add_argument("--timezone", default="")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    out = os.path.abspath(a.out)
    if os.path.commonpath([out, REPO]) == REPO:
        print("refusing to write inside the repository: the result is personal data", file=sys.stderr)
        return 3
    if any(os.path.exists(os.path.join(out, *p)) for p in (("profile", "settings.toml"), ("data", "postings.json"),
                                                            ("data", "applications.json"))):
        print("refusing to write over a folder that is already set up: everything recorded there since would be "
              "lost. Import into a new, empty folder.", file=sys.stderr)
        return 3
    labels = {}
    if a.labels:
        with open(a.labels, encoding="utf-8") as f:
            labels = json.load(f)
    os.makedirs(os.path.join(out, "profile"), exist_ok=True)
    os.makedirs(os.path.join(out, "data"), exist_ok=True)
    with open(os.path.join(out, "profile", "settings.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(settings_toml(load_file(a.config), labels, a.timezone))
    with open(os.path.join(out, "profile", "companies.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(companies_toml(load_file(a.watchlist)))
    relative = {}
    if a.relative_dates:
        with open(a.relative_dates, encoding="utf-8") as f:
            relative = json.load(f)
    apps = []
    if a.pipeline:
        with open(a.pipeline, encoding="utf-8") as f:
            apps = applications(f.read(), relative)
    report = [f"{len(load_file(a.watchlist).get('company', []))} companies", f"{len(apps)} applications"]
    if a.seen:
        with open(a.seen, encoding="utf-8") as f:
            seen = json.load(f)
        kit, copied = postings(seen, a.postings_dir or os.path.join(os.path.dirname(a.seen), "postings"), out)
        with open(os.path.join(out, "data", "postings.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(kit, f, indent=1, ensure_ascii=False)
        report.append(f"{len(kit['postings'])} postings ({copied} descriptions)")
        report[1] += f" ({join(apps, kit['postings'])} joined to their postings)"
    with open(os.path.join(out, "data", "applications.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"applications": apps}, f, indent=1, ensure_ascii=False)
    if a.triage_log:
        with open(a.triage_log, encoding="utf-8") as f:
            rows = decisions(f.read())
        with open(os.path.join(out, "data", "decisions.log"), "w", encoding="utf-8", newline="\n") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        report.append(f"{len(rows)} decisions")
    print(f"wrote settings, {', '.join(report)} to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
