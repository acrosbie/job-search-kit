"""Recording a verdict on a posting: its status in postings.json, and a line in decisions.log.

The user's own decision always stands: Claude can't overwrite it unless the user asks (force). Only
the user marks a posting applied, and that goes through track.apply, which also records the
application, so a posting is never applied without one.
"""

import datetime as dt
import os
import re

from . import settings, store
from .clock import Clock
from . import summary as summary_mod
from .errors import NotFound, Refused

# A verdict that contradicts an earlier one, for spotting when the user overturns Claude or a rule.
OPPOSED = {"worth_applying": {"not_a_fit", "skipped"}, "not_a_fit": {"worth_applying", "applied"}}
_PLAIN = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
                        "\u00a0": " ", "*": " ", "`": " "})


def _plain(s):
    """Text as a quote is looked for: one case, plain dashes, no quote marks, bullets or emphasis."""
    s = (s or "").translate(_PLAIN)
    s = re.sub(r"(^|\n)\s*(?:[-•]|\d+[.)])\s+", " ", s)
    s = re.sub(r"[\"']", "", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def quote_found(quote, text):
    """True when every part of the quote (split at "..." or the ellipsis character) is in the text, in order."""
    body, pos = _plain(text), 0
    parts = [p for p in (_plain(x).strip(" .,;:") for x in re.split(r"\.\.\.|…", quote or "")) if p]
    if not parts:
        return False
    for p in parts:
        at = body.find(p, pos)
        if at < 0:
            return False
        pos = at + len(p)
    return True


def _rule_id(root, rule):
    """'rule N' for a rule rules.md has, from "N", "rule N" or "Rule N"."""
    m = re.fullmatch(r"\s*(?:rule\s*)?(\d+)\s*", rule or "", re.I)
    if not m:
        raise Refused(f"name the rule by its number in rules.md, as --rule N, not {rule!r}")
    n = int(m.group(1))
    try:
        from . import rules
        known = rules.sections(rules.read(root).splitlines())
    except FileNotFoundError:
        known = None
    if known is not None and n not in known:
        raise Refused(f"rules.md has no rule {n}")
    return f"rule {n}"


def _check_evidence(root, folder, key, entry, status, rule, quote):
    """Claude's Not a fit names its rule; a Not a fit or Your call quotes the posting line it rests on,
    and the quote must be in the saved posting: it shows the posting was read, and lets the weekly
    review group overturns by rule however the note is worded."""
    if status not in ("not_a_fit", "your_call"):
        return ""
    if status == "not_a_fit" and not rule:
        raise Refused("name the rule it rests on: --rule N, its number in rules.md")
    if not quote:
        raise Refused("quote the line from the posting this rests on, word for word: --quote \"...\"")
    if entry.get("unread"):
        raise Refused("this posting's description couldn't be read yet, so it can't be judged; the next scan reads it")
    text = folder.read_description(key) or ""
    if not quote_found(quote, text):
        raise Refused("that quote isn't in the posting as saved: copy the words exactly (show KEY prints it). "
                      "Use ... between two parts")
    return _rule_id(root, rule) if rule else ""


def last_user_decision(decisions, key):
    """The user's most recent verdict on this posting, or None."""
    mine = [d for d in decisions if d.get("key") == key and d.get("by") == "user"]
    return mine[-1] if mine else None


def _summary(folder, key, status, by, summary, day):
    """Claude's summary of a posting, checked against it (summary.py), dated; or None."""
    if summary is None:
        return None
    if by != "claude":
        raise Refused("a summary is Claude's account of the posting; the user's own words go in the note")
    checked = summary_mod.check(summary, status, folder.read_description(key))
    return {**checked, "date": day}


def summarize(root, key, summary, clock=None):
    """Write Claude's summary of a posting again without a new verdict: for a job already decided, or
    one judged before summaries. Nothing else about it changes, and no verdict is logged."""
    folder = store.Folder(root)
    state = folder.load_postings()
    entry = state["postings"].get(key)
    if not entry:
        raise NotFound(f"unknown key {key}")
    entry["summary"] = _summary(folder, key, entry.get("status", ""), "claude", summary, (clock or Clock()).today())
    folder.save_postings(state)
    return {"key": key, "status": entry.get("status", ""), "summary": entry["summary"]}


HOLD_THEN = ("worth_applying", "your_call")


def hold_until(root, company, clock):
    """The day the cooldown at `company` ends: the latest known application there within the cooldown,
    plus cooldown_days; or "" when there is none (nothing to wait for)."""
    from . import queue, track
    s = settings.load(root)
    folder = store.Folder(root)
    today = dt.date.fromisoformat(clock.today())
    recent = queue.recent_applications(company, [track.normalize(a) for a in folder.load_applications()],
                                       folder.load_postings()["postings"],
                                       today, s.cooldown_days)
    days = [dt.date.fromisoformat(r["applied"]) for r in recent if r.get("date_known")]
    return (max(days) + dt.timedelta(days=s.cooldown_days)).isoformat() if days else ""


def _check_hold(root, entry, until, then, clock):
    then = then or "worth_applying"
    if then not in HOLD_THEN:
        raise Refused(f"after the wait a job is worth_applying or your_call, not {then!r}")
    until = until or hold_until(root, entry.get("company", ""), clock)
    if not until:
        raise Refused(f"no application to {entry.get('company', '')} in the cooldown, so nothing to wait for: "
                      "judge it now, or give --until YYYY-MM-DD")
    try:
        day = dt.date.fromisoformat(until)
    except ValueError:
        raise Refused(f"--until is a date, YYYY-MM-DD, not {until!r}")
    if day <= dt.date.fromisoformat(clock.today()):
        raise Refused(f"{until} isn't after today: judge it now instead")
    return until, then


def mark(root, key, status, by, note="", force=False, clock=None, choice="", at="", record_only=False,
         rule="", quote="", evidence=False, candidate_rule=False, summary=None, until="", then=""):
    """Record one verdict and return the decisions.log row. `choice` is the id of a click on the jobs
    page, kept so the same click is never recorded twice, and `at` the time it was made (default now).

    `record_only` logs Claude's verdict without changing the posting: for a job the user had already
    applied to before Claude judged it, so the weekly review's outcomes can still compare the two.

    `evidence` (the command line sets it for Claude) requires a Not a fit to name its `rule` and a Not a
    fit or Your call to `quote` the posting; both are kept on the row. `candidate_rule` marks the
    user's reason as one that sounds like a rule, for the weekly review. `summary` is Claude's account
    of the posting for the page and chat (summary.py), checked before anything is saved.

    `on_hold` is a job turned away only by the cooldown: it waits `until` the day the cooldown ends
    (worked out from the applications when not given), then becomes `then`, Worth applying or Your
    call (release_holds)."""
    folder = store.Folder(root)
    state = folder.load_postings()
    entry = state["postings"].get(key)
    if not entry:
        raise NotFound(f"unknown key {key}")
    if status == "applied" and by != "user":
        raise Refused("only the user marks a posting applied")
    rule_id = ""
    if record_only:
        if by != "claude":
            raise Refused("only Claude's own verdict is recorded without changing the posting")
        if evidence:
            rule_id = _check_evidence(root, folder, key, entry, status, rule, quote)
        clk = clock or Clock()
        checked = _summary(folder, key, status, by, summary, clk.today())
        row = {"at": at or clk.stamp(), "date": (at or clk.stamp())[:10], "key": key, "company": entry["company"],
               "title": entry["title"], "verdict": status, "reason": note, "by": by, "record_only": True}
        row.update({k: v for k, v in (("rule", rule_id), ("quote", quote), ("summary", checked)) if v})
        if checked:  # shown on the page; the verdict on the posting stays as it is
            entry["summary"] = checked
            folder.save_postings(state)
        folder.log_decision(row)
        return row
    decisions = folder.read_decisions()
    earlier = [d for d in decisions if d.get("key") == key and not d.get("record_only")]
    mine = last_user_decision(decisions, key)
    if by != "user" and mine and not force:
        raise Refused(f"the user already decided this one ({mine.get('verdict')} on {mine.get('date')}); "
                      "their decision stands")
    if by == "claude" and entry.get("status") == "applied" and not force:
        raise Refused("the user applied to this one: record Claude's verdict with --record-only, which leaves it applied")
    if evidence and by == "claude":
        rule_id = _check_evidence(root, folder, key, entry, status, rule, quote)
    clk = clock or Clock()
    if status == "on_hold":
        until, then = _check_hold(root, entry, until, then, clk)
    checked = _summary(folder, key, then if status == "on_hold" else status, by, summary, clk.today())
    reversal = ""
    if by == "user" and earlier and status in OPPOSED.get(earlier[-1].get("verdict"), set()):
        reversal = earlier[-1].get("verdict")
    at = at or clk.stamp()
    entry["status"] = status
    entry["triaged"] = at[:10]
    if status == "on_hold":
        entry["hold_until"], entry["hold_then"] = until, then
    else:
        entry.pop("hold_until", None)
        entry.pop("hold_then", None)
    if note:
        entry["note"] = note
    if rule_id:
        entry["rule"] = rule_id
    if checked:
        entry["summary"] = checked
    folder.save_postings(state)
    row = {"at": at, "date": at[:10], "key": key, "company": entry["company"], "title": entry["title"],
           "verdict": status, "reason": note, "by": by}
    if reversal:
        row["reverses"] = reversal
    if status == "on_hold":
        row.update({"until": until, "then": then})
    if choice:
        row["choice"] = choice
    row.update({k: v for k, v in (("rule", rule_id), ("quote", quote), ("summary", checked)) if v})
    if candidate_rule and by == "user":
        row["candidate_rule"] = True
    folder.log_decision(row)
    return row


def release_holds(root, clock):
    """Jobs whose wait ended by today become what they were held as, decided by whoever held them.
    Returns them, for Claude to say in a line."""
    folder = store.Folder(root)
    state = folder.load_postings()
    today = clock.today()
    due = [(k, v) for k, v in state["postings"].items()
           if v.get("status") == "on_hold" and (v.get("hold_until") or "9999") <= today]
    if not due:
        return []
    held_by = {}
    for d in folder.read_decisions():
        if d.get("verdict") == "on_hold":
            held_by[d.get("key")] = d.get("by", "claude")
    out, at = [], clock.stamp()
    for k, v in due:
        then, until = v.get("hold_then") or "worth_applying", v.get("hold_until", "")
        v["status"], v["triaged"] = then, at[:10]
        v.pop("hold_until", None)
        v.pop("hold_then", None)
        folder.log_decision({"at": at, "date": at[:10], "key": k, "company": v.get("company", ""),
                             "title": v.get("title", ""), "verdict": then, "by": held_by.get(k, "claude"),
                             "reason": f"the wait at {v.get('company', '')} ended on {until}", "released": until})
        out.append({"key": k, "num": v.get("num"), "company": v.get("company", ""), "title": v.get("title", ""),
                    "url": v.get("url", ""), "now": then, "gone": v.get("gone", "")})
    folder.save_postings(state)
    return out


def hold_candidates(root, clock):
    """Claude's Not a fit at a company whose cooldown hasn't ended yet, still on its board: turned away,
    perhaps, only for the wait, from before on_hold existed. Each is offered once (data/kit.json)."""
    from . import queue, track
    s = settings.load(root)
    folder = store.Folder(root)
    postings = folder.load_postings()["postings"]
    applications = [track.normalize(a) for a in folder.load_applications()]
    today = dt.date.fromisoformat(clock.today())
    path = os.path.join(folder.data, "kit.json")
    kit = folder.read_json(path) or {}
    offered = set(kit.get("holds_offered", []))
    last_by = {}
    for d in folder.read_decisions():
        if not d.get("record_only"):
            last_by[d.get("key")] = d.get("by", "")
    out = []
    for k, v in postings.items():
        if v.get("status") != "not_a_fit" or last_by.get(k) != "claude" or v.get("gone") or k in offered:
            continue
        recent = queue.recent_applications(v.get("company", ""), applications, postings, today, s.cooldown_days)
        reopens = max((r["reopens"] for r in recent if r.get("reopens")), default="")
        if reopens and reopens > today.isoformat():
            out.append({"key": k, "num": v.get("num"), "company": v.get("company", ""), "title": v.get("title", ""),
                        "url": v.get("url", ""), "note": v.get("note", ""), "reopens": reopens})
    if out:
        folder.write_json(path, {**kit, "holds_offered": sorted(offered | {x["key"] for x in out})})
    return out
