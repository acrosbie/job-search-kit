"""The weekly review: what the user is asked to look at once a week, as one set of facts.

The reference system's lessons shape it. The user's overturns are the only ground truth a search
has, and a rule overturned twice is wrong. A rule that never fires is a flag, not a rule. The rule
doing most of the rejecting deserves a second look, and a sample of what the scan turned away
catches a rule that has drifted. Filters show diminishing returns, while what happens after an
application is where searches fail, so the pipeline and the outcomes are part of every review.

This module only gathers the facts. The review and tune skills ask the questions, and nothing
changes without the user's yes (changes.py).

    since            the last review gone through, or 7 days ago
    disagreements    the user's overturns, grouped by the rule they overturned; propose when a rule
                     has been overturned twice since it last changed, unless a proposal for it was
                     turned down in the last four weeks
    candidate_rules  reasons the user gave that sound like a rule ("candidate rule: ...")
    rule_activity    how often each rule fired in four weeks, the rules that never fired, the top rule
    spot_check       10 of the scan's automatic rejects, the same ones all day
    missed_titles    20 titles the title filter nearly kept
    pipeline         follow-ups due, by route, after the day-21 close (track.due)
    scan_health      boards failing, silent, or at their cap (health.py)
    monthly          once a month: outcomes, and the profile refresh
"""

import datetime as dt
import os
import random
import re

from . import changes, health, resume, rules, settings, store, titles, track

WINDOW_DAYS = 28
SPOT_CHECK = 10
MISSED_TITLES = 20
MONTH_DAYS = 28
ANSWERED = ("replied", "screen", "interview", "offer")

SCAN_RULE_NAMES = {
    "location_in_country": "Where the job is (scan): elsewhere in the country, not remote",
    "location_remote_only": "Where the job is (scan): too far to commute, not remote",
    "location_abroad": "Where the job is (scan): abroad",
    "pay": "Pay line (scan)",
}


def _date(s):
    try:
        return dt.date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def rule_of(d):
    """The rule a decision rests on: a scan rule's id, "rule N" from Claude's note, or Claude's verdict."""
    if d.get("by") == "rule":
        return d.get("rule", "")
    if d.get("by") == "claude":
        m = re.match(r"\s*Rule (\d+)(?!\d)", d.get("reason") or "")
        if d.get("verdict") == "not_a_fit" and m:
            return f"rule {m.group(1)}"
        return f"claude: {d.get('verdict', '')}"
    return ""


def what_changes(rule_id):
    """How changes.log names a change to this rule, as a test on its `what`."""
    if rule_id.startswith("rule "):
        return lambda w: w == rule_id
    if rule_id.startswith("location_"):
        return lambda w: w.startswith("setting places.") or w == "setting description.remote_language"
    if rule_id == "pay":
        return lambda w: w.startswith("setting pay.")
    if rule_id.startswith("phrases:"):
        return lambda w: w == f"phrase rule {rule_id.split(':', 1)[1]}"
    return lambda w: False


def _label(rule_id, names):
    if rule_id.startswith("rule "):
        n = int(rule_id.split()[1])
        return f"Rule {n} ({names.get(n, 'not in rules.md')})"
    if rule_id.startswith("phrases:"):
        return f"Phrase rule (scan): {rule_id.split(':', 1)[1]}"
    if rule_id.startswith("claude: "):
        return f"Claude's verdict: {rule_id.split(': ', 1)[1].replace('_', ' ')}"
    return SCAN_RULE_NAMES.get(rule_id, rule_id)


def _rule_names(root):
    try:
        found = rules.sections(rules.read(root).splitlines())
    except FileNotFoundError:
        return {}, set()
    retired = {n for n, (name, _, _) in found.items() if "(retired" in name}
    return {n: re.sub(r" [(]retired .*[)]$", "", name) for n, (name, _, _) in found.items()}, retired


def disagreements(decisions, change_rows, postings, names, today):
    prior, groups = {}, {}
    for d in decisions:
        k = d.get("key")
        before = prior.get(k)
        if d.get("by") == "user" and d.get("reverses") and before and before.get("by") in ("rule", "claude"):
            rid = rule_of(before)
            groups.setdefault(rid, []).append({
                "key": k, "num": postings.get(k, {}).get("num"), "company": d.get("company", ""),
                "title": d.get("title", ""), "rule_said": before.get("reason", ""), "was": before.get("verdict"),
                "now": d.get("verdict"), "their_words": d.get("reason", ""), "date": d.get("date", ""), "at": d.get("at", "")})
        if d.get("by") in ("rule", "claude", "user") and not d.get("record_only"):
            prior[k] = d
    out = []
    for rid, items in groups.items():
        changed = [c.get("at", "") for c in change_rows if c.get("kind") in ("changed", "retired", "added")
                   and what_changes(rid)(c.get("what", ""))]
        last = max(changed) if changed else ""
        fresh = [i for i in items if i["at"] > last]
        what = rid if rid.startswith("rule ") else None
        quiet = bool(what) and changes.declined_recently(change_rows, what, today)
        out.append({"rule": rid, "label": _label(rid, names), "overturns": items, "since_last_change": len(fresh),
                    "last_changed": last[:10], "declined_recently": quiet,
                    "propose": len(fresh) >= 2 and not quiet and not rid.startswith("claude: ")})
    return sorted(out, key=lambda g: (-g["since_last_change"], g["label"]))


def activity(decisions, names, retired, first_day, today):
    start = (today - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    fires = {}
    for d in decisions:
        if d.get("verdict") == "not_a_fit" and d.get("by") in ("rule", "claude") and d.get("date", "") >= start:
            rid = rule_of(d)
            if rid and not rid.startswith("claude: "):
                fires[rid] = fires.get(rid, 0) + 1
    total = sum(fires.values())
    top = max(fires.items(), key=lambda kv: kv[1]) if fires else None
    running_long_enough = first_day is not None and (today - first_day).days >= WINDOW_DAYS
    never = [{"rule": f"rule {n}", "label": _label(f"rule {n}", names)} for n in sorted(names)
             if n not in retired and f"rule {n}" not in fires] if running_long_enough else []
    return {"days": WINDOW_DAYS, "rejects": total,
            "fires": [{"rule": r, "label": _label(r, names), "count": c} for r, c in sorted(fires.items(), key=lambda kv: -kv[1])],
            "top": {"rule": top[0], "label": _label(top[0], names), "count": top[1],
                    "share": round(top[1] / total, 2)} if top else None,
            "never_fired": never}


def spot_check(decisions, postings, since, today):
    last = {}
    for d in decisions:
        last[d.get("key")] = d
    pool = sorted(k for k, d in last.items()
                  if d.get("by") == "rule" and d.get("date", "") >= since and postings.get(k, {}).get("status") == "not_a_fit")
    random.Random(today.isoformat()).shuffle(pool)
    return [{"key": k, "num": postings[k].get("num"), "company": postings[k].get("company", ""),
             "title": postings[k].get("title", ""), "location": postings[k].get("location", ""),
             "rule": last[k].get("rule", ""), "reason": last[k].get("reason", "")} for k in pool[:SPOT_CHECK]]


def outcomes(applications, decisions, tailored=()):
    """Counts only: what happened to the applications, by Claude's verdict, how they were sent, level,
    top pick, and whether a resume tailored to the job went with it (`tailored`: posting keys a copy
    was made for). The kit never turns these into odds."""
    verdict = {}
    for d in decisions:
        if d.get("by") == "claude":
            verdict[d.get("key")] = d.get("verdict", "")

    def bucket(a):
        st = a["status"]
        if st in ANSWERED:
            return "answered"
        return {"rejected": "turned_down", "presumed_rejected": "no_reply", "applied": "open"}.get(st, "ended")

    totals, by = {}, {"verdict": {}, "channel": {}, "level": {}, "top_pick": {}, "tailored_resume": {}}
    for a in applications:
        b = bucket(a)
        totals[b] = totals.get(b, 0) + 1
        keys = {"verdict": verdict.get(a.get("key"), "") or "none", "channel": a.get("channel") or "not known",
                "level": a.get("level") or "not known",
                "top_pick": {True: "yes", False: "no"}.get(a.get("top_pick"), "not asked"),
                "tailored_resume": "yes" if a.get("key") and a.get("key") in set(tailored) else "no"}
        for dim, val in keys.items():
            row = by[dim].setdefault(val, {})
            row[b] = row.get(b, 0) + 1
    return {"applications": len(applications), "totals": totals, "by": by}


def profile_refresh(root):
    out = {"unconfirmed": [], "answers": 0, "oldest_answer": ""}
    about = os.path.join(root, "profile", "about-me.md")
    if os.path.exists(about):
        with open(about, encoding="utf-8-sig") as f:
            text = f.read()
        m = re.search(r"^## Not confirmed yet.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
        if m:
            out["unconfirmed"] = [x.strip()[2:] for x in m.group(1).splitlines() if x.strip().startswith("- ")][:20]
    want = os.path.join(root, "profile", "what-i-want.md")
    if os.path.exists(want):
        with open(want, encoding="utf-8-sig") as f:
            rows = [x for x in f.read().splitlines() if x.startswith("|") and not set(x) <= set("|- :")]
        rows = rows[1:]  # the header row
        dates = sorted(d for r in rows for d in re.findall(r"\d{4}-\d{2}-\d{2}", r))
        out.update({"answers": len(rows), "oldest_answer": dates[0] if dates else ""})
    return out


def build(root, clock, monthly=None):
    s = settings.load(root)
    folder = store.Folder(root)
    postings = folder.load_postings()["postings"]
    decisions = folder.read_decisions()
    change_rows = folder.read_changes()
    reviews = folder.read_reviews()
    today = dt.date.fromisoformat(clock.today())
    done = [r for r in reviews if r.get("kind") == "done"]
    since = done[-1]["date"] if done else (today - dt.timedelta(days=7)).isoformat()
    names, retired = _rule_names(root)
    runs = folder.read_runs()
    first_day = _date(runs[0].get("at")) if runs else None
    if monthly is None:
        last_monthly = [r for r in done if r.get("monthly")]
        start = _date(last_monthly[-1]["date"]) if last_monthly else first_day
        monthly = start is not None and (today - start).days >= MONTH_DAYS

    try:
        near = titles.summary(root, sample=MISSED_TITLES, seed=today.toordinal())["near_sample"]
    except FileNotFoundError:
        near = []
    out = {
        "today": today.isoformat(), "since": since,
        "disagreements": disagreements(decisions, change_rows, postings, names, today.isoformat()),
        "candidate_rules": [{"key": d.get("key"), "company": d.get("company", ""), "title": d.get("title", ""),
                             "their_words": d.get("reason", ""), "date": d.get("date", "")}
                            for d in decisions if d.get("by") == "user" and d.get("date", "") >= since
                            and "candidate rule:" in (d.get("reason") or "").lower()],
        "rule_activity": activity(decisions, names, retired, first_day, today),
        "spot_check": spot_check(decisions, postings, since, today),
        "missed_titles": [{"title": t["title"], "company": t["board"], "location": t["location"], "count": t["count"]}
                          for t in near],
        "pipeline": track.due(root, clock),
        "scan_health": health.boards(folder.load_postings()["boards"], settings.load_companies(root), s, today.isoformat()),
        "monthly": monthly,
    }
    if monthly:
        tailored = {r.get("for") for r in resume.records(root) if r.get("for")}
        out["outcomes"] = outcomes(track.load(root), decisions, tailored)
        out["profile_refresh"] = profile_refresh(root)
    out["to_raise"] = sum(1 for g in out["disagreements"] if g["propose"]) + len(out["candidate_rules"])
    return out


def prepare(root, clock):
    """Build the review and keep it for the user to go through, from a scheduled check."""
    out = build(root, clock)
    folder = store.Folder(root)
    folder.write_json(folder.review_json, out)
    folder.log_review({"at": clock.stamp(), "date": clock.today(), "kind": "prepared", "to_raise": out["to_raise"],
                       "spot_check": len(out["spot_check"]), "monthly": out["monthly"]})
    return out


def finish(root, clock, monthly=False):
    """The user has gone through it: the next review starts from today."""
    row = {"at": clock.stamp(), "date": clock.today(), "kind": "done", "monthly": bool(monthly)}
    store.Folder(root).log_review(row)
    return row
