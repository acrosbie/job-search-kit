"""The jobs page: what is waiting on the user, what is due, and every application, each job numbered.

One template (engine/page/jobs-page.html) is written out three ways after every change:

    data/page.json        the page's data, which Claude can write into the page's own storage
    data/jobs-page.html   the template with the data built in, ready for Claude to publish
    My jobs.html          the same as a complete web page, which opens from the folder with a double-click

As a Claude artifact the page saves each click in the user's own private storage, and Claude reads the
clicks back and records them (choices.py). Opened from the folder, it can't save, so it offers "Copy my
choices" for pasting into chat instead.

A job keeps its number for good, stored on its record ("num"), so "#12" means the same job on the page,
in chat, and next week. Numbers are given out here, the first time a job appears on the page.
"""

import datetime as dt
import hashlib
import json
import os
import re

from . import __version__, choices, interviews, schedule, settings, store, track

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "page", "jobs-page.html")
DATA_SLOT = "__JOBS_DATA__"
TITLE_SLOT = "__PAGE_TITLE__"
WAITING = ("worth_applying", "your_call", "new")
SCREENED_DAYS = 14
SCREENED_MAX = 60
MAX_BYTES = 200_000
# The skeleton a published artifact gets, so the file in the folder is a complete page too.
DOCUMENT = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>\n'
            '{content}\n</body></html>\n')


def _date(s):
    try:
        return dt.date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def _next_number(postings, applications):
    used = [v.get("num") or 0 for v in postings.values()] + [a.get("num") or 0 for a in applications]
    return max(used, default=0) + 1


def build(root, clock):
    """The page's data. Gives numbers to jobs appearing for the first time, saving them."""
    s = settings.load(root)
    folder = store.Folder(root)
    state = folder.load_postings()
    postings = state["postings"]
    applications = track.load(root)
    today = dt.date.fromisoformat(clock.today())
    since = (today - dt.timedelta(days=SCREENED_DAYS)).isoformat()

    waiting = [(k, v) for k, v in postings.items() if v.get("status") in WAITING]
    screened = sorted(((k, v) for k, v in postings.items()
                       if v.get("status") == "not_a_fit" and (v.get("triaged") or v.get("first_seen", "")) >= since),
                      key=lambda kv: (kv[1].get("triaged") or kv[1].get("first_seen", ""), kv[0]), reverse=True)[:SCREENED_MAX]
    linked = [(a["key"], postings[a["key"]]) for a in applications if a.get("key") in postings]

    # New numbers, oldest first, so the order reads naturally.
    n, posting_numbered, app_numbered = _next_number(postings, applications), False, False
    for k, v in sorted(dict(waiting + screened + linked).items(), key=lambda kv: (kv[1].get("first_seen", ""), kv[0])):
        if not v.get("num"):
            v["num"], n, posting_numbered = n, n + 1, True
    for a in sorted(applications, key=lambda a: (a.get("applied_date") or "", a["id"])):
        if a.get("key") not in postings and not a.get("num"):
            a["num"], n, app_numbered = n, n + 1, True
    if posting_numbered:
        folder.save_postings(state)
    if app_numbered:
        track.save(root, applications)

    # Who made the latest decision on each job, and what Claude (or a rule) and the user last said about
    # it, kept apart: a click with no note must never show Claude's reason as the user's words.
    decided_by, claude_said, claude_quote, you_said = {}, {}, {}, {}
    for d in folder.read_decisions():
        k = d.get("key")
        decided_by[k] = d.get("by", "")
        if d.get("by") in ("claude", "rule"):
            claude_said[k] = d.get("reason", "")
            claude_quote[k] = d.get("quote", "")
        elif d.get("by") == "user":
            you_said[k] = d.get("reason", "")

    def job(k, v):
        # `summary` is Claude's account for the user (summary.py); the note, rule and quote are the
        # audit trail, which the page folds away as "Behind the call".
        return {"num": v.get("num"), "key": k, "by": decided_by.get(k, ""), "company": v.get("company", ""),
                "title": v.get("title", ""), "location": v.get("location", ""), "url": v.get("url", ""), "salary": v.get("salary", ""),
                "status": v.get("status", ""), "note": v.get("note", ""), "flag": v.get("flag", ""),
                "claude_said": claude_said.get(k, ""), "quote": claude_quote.get(k, ""), "rule": v.get("rule", ""),
                "summary": v.get("summary") or None, "you_said": you_said.get(k, ""),
                "first_seen": v.get("first_seen", ""), "gone": v.get("gone", ""), "source": v.get("source", "")}

    order = {st: i for i, st in enumerate(WAITING)}
    waiting_out = [job(k, v) for k, v in sorted(waiting, key=lambda kv: (order[kv[1]["status"]],
                                                                         -(kv[1].get("num") or 0)))]
    apps_out, todo = [], []
    rank = {"applied": 1, "replied": 0, "screen": 0, "interview": 0, "offer": 0}
    for a in sorted(applications, key=lambda a: (rank.get(a["status"], 2), _neg_date(a.get("applied_date")))):
        st = track.state(a, today, s)
        p = postings.get(a.get("key") or "", {})
        last = a["history"][-1] if a.get("history") else {}
        item = {"num": p.get("num") or a.get("num"), "id": a["id"], "key": a.get("key", ""),
                "company": a.get("company", ""), "role": a.get("role", ""),
                "url": (a.get("urls") or [""])[0] or p.get("url", ""), "applied_date": a.get("applied_date", ""),
                "estimated": bool(a.get("applied_date_estimated")), "days": st["days"], "status": a["status"],
                "contact": a.get("contact", ""), "top_pick": a.get("top_pick"), "channel": a.get("channel", ""),
                "followed_up": a.get("followed_up", ""), "closes_on": st["closes_on"],
                "last": {"date": last.get("date", ""), "what": last.get("status") or last.get("event", "")}}
        apps_out.append(item)
        if st["due"]:
            todo.append({**{k: item[k] for k in ("num", "id", "company", "role", "days", "contact", "closes_on",
                                                 "applied_date")},
                         "route": st["route"],
                         "search": contact_search(item["company"], item["role"], s) if st["route"] == "find_person" else ""})
    route_order = {r: i for i, r in enumerate(track.ROUTES)}
    todo.sort(key=lambda t: (route_order[t["route"]], -(t["days"] or 0)))
    coming = [x for x in interviews.listing(root, clock) if -interviews.DEBRIEF_DAYS <= x["days"] <= 31]
    last_ok, last_try = schedule.last_scans(folder.read_runs())

    name = (s.raw.get("you", {}).get("name") or "").strip()
    return _fit({
        "version": __version__,
        "design": design(),
        "title": f"{name}'s job search" if name else "My job search",
        "as_of": clock.stamp(),
        "today": today.isoformat(),
        "counts": {"waiting": len(waiting_out), "to_do": len(todo),
                   "open": sum(1 for a in apps_out if a["status"] in ("applied", "replied", "screen", "interview", "offer")),
                   "applications": len(apps_out)},
        "tracking": {"follow_up_after_days": s.follow_up_after_days, "presume_after_days": s.presume_after_days},
        "review_ready": schedule.review_state(root, s, clock)[0],
        "handled": choices.handled(root, clock),
        "focus": focus(coming, todo, waiting_out),
        "funnel": funnel(postings, applications),
        "activity": activity(applications, today),
        "last_scan": {"good_at": last_ok.get("at", ""), "attempt_at": last_try.get("at", ""),
                      "status": schedule.status_of(last_try)},
        # Interviews from two weeks ago (not yet gone through) to a month ahead.
        "coming_up": coming,
        "waiting": waiting_out,
        "todo": todo,
        "applications": apps_out,
        "screened": [{**job(k, v), "date": v.get("triaged") or v.get("first_seen", "")} for k, v in screened],
        "more_waiting": 0,
    })


# Words a title uses for its level, left out of the search for the person who'd manage the role.
_LEVEL = re.compile(r"\b(?:senior|sr|junior|jr|lead|principal|staff|head of|director of|director|vp of|vp|"
                    r"vice president of|vice president|manager of|manager|mgr|associate|chief|global|group|"
                    r"regional|team|specialist)\b\.?", re.I)


def contact_search(company, role, s):
    """What to search LinkedIn's people for, to find who'd manage this role: the company, the title's
    field without its level, and the leaders' titles ([page] contact_search, or director, head or VP).
    The page makes it a link the user opens; nobody is looked up for them."""
    title = re.sub(r"\s*\(.*$", "", role or "")
    parts = [" ".join(_LEVEL.sub(" ", p).split()) for p in title.split(",")]
    field = next((p for p in parts if p), "")
    leaders = (s.page.get("contact_search") or "").strip() or "director OR head OR VP"
    return f'{company} "{field}" ({leaders})' if field else f"{company} ({leaders})"


FOCUS_MAX = 3


def focus(coming, todo, waiting):
    """What to do today, most urgent first: the next interview, then up to three actions (prep for an
    interview in the next few days, its time, a debrief, a follow-up to send, top picks with nobody to
    follow up with, a job worth applying to), and the newest top picks."""
    upcoming = [x for x in coming if not x["past"]]
    actions = []
    for x in upcoming:
        if x["days"] <= 7 and x.get("time_unknown"):
            actions.append({"kind": "time", "num": x["num"], "company": x["company"], "stage": x["stage"], "on": x["on"]})
        if x["days"] <= interviews.SOON_DAYS and not x.get("prep"):
            actions.append({"kind": "prep", "num": x["num"], "company": x["company"], "stage": x["stage"], "on": x["on"]})
    for x in coming:
        if x["past"]:
            actions.append({"kind": "debrief", "num": x["num"], "company": x["company"], "stage": x["stage"], "on": x["on"]})
    for t in todo:
        if t["route"] == "send":
            actions.append({"kind": "follow_up", "num": t["num"], "id": t["id"], "company": t["company"],
                            "role": t["role"], "contact": t["contact"]})
    finds = [t for t in todo if t["route"] == "find_person"]
    if finds:
        actions.append({"kind": "find_person", "count": len(finds)})
    picks = [j for j in waiting if j["status"] == "worth_applying"]
    picks.sort(key=lambda j: (j["by"] != "user", -(j["num"] or 0)))  # the ones they want first
    for j in picks:
        actions.append({"kind": "apply", "num": j["num"], "key": j["key"], "company": j["company"], "title": j["title"]})
    return {"next_interview": upcoming[0] if upcoming else None, "actions": actions[:FOCUS_MAX],
            "more_actions": max(0, len(actions) - FOCUS_MAX),
            "top_picks": [{"num": j["num"], "key": j["key"], "company": j["company"], "title": j["title"],
                           "headline": (j.get("summary") or {}).get("headline", "")} for j in picks[:FOCUS_MAX]]}


REACHED = {"screen": ("screen", "interview", "offer"), "interview": ("interview", "offer"), "offer": ("offer",)}


def funnel(postings, applications):
    """How far the search has come, in facts: jobs saved, applications sent, and how many got as far as
    a screen, an interview and an offer (at any point, so one turned down after an interview counts)."""
    def reached(a, stage):
        return a["status"] in REACHED[stage] or any(h.get("status") in REACHED[stage] for h in a.get("history", []))
    return {"saved": len(postings), "applied": len(applications),
            **{f"{stage}s": sum(1 for a in applications if reached(a, stage)) for stage in REACHED}}


def activity(applications, today, weeks=8):
    """Applications sent in each of the last `weeks` weeks (Monday to Sunday), oldest first."""
    monday = today - dt.timedelta(days=today.weekday())
    starts = [monday - dt.timedelta(weeks=n) for n in range(weeks - 1, -1, -1)]
    counts = {d: 0 for d in starts}
    for a in applications:
        d = _date(a.get("applied_date"))
        if d:
            start = d - dt.timedelta(days=d.weekday())
            if start in counts:
                counts[start] += 1
    return [{"week": d.isoformat(), "applied": counts[d]} for d in starts]


def design():
    """The page's design, as a short fingerprint of its template: the page in the user's Claude account
    is published again when this differs from the one it was published with ([page] version)."""
    with open(TEMPLATE, "rb") as f:
        return hashlib.sha1(f.read().replace(b"\r\n", b"\n")).hexdigest()[:12]


def digest(data):
    """What the page shows, as a short fingerprint that ignores when it was written, so Claude can tell
    whether the page in the user's Claude account is behind the folder (schedule.page_behind)."""
    body = {k: v for k, v in data.items() if k not in ("as_of", "digest")}
    return hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _size(data):
    return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def _fit(data):
    """Keep the page's data under MAX_BYTES, because the page's storage takes at most 256 KiB in one
    document. Screened-out jobs go first, then long notes are shortened, then the oldest jobs not yet
    gone through are left off (counted in more_waiting, and still in the folder)."""
    while _size(data) > MAX_BYTES and data["screened"]:
        data["screened"] = data["screened"][:len(data["screened"]) // 2]
    if _size(data) > MAX_BYTES:
        for item in data["waiting"]:
            item["note"] = item["note"][:280]
    unread = [j for j in data["waiting"] if j["status"] == "new"]
    while _size(data) > MAX_BYTES and unread:
        drop = unread[len(unread) // 2:] or unread
        dropped = {id(j) for j in drop}
        data["waiting"] = [j for j in data["waiting"] if id(j) not in dropped]
        data["more_waiting"] += len(drop)
        unread = unread[:len(unread) // 2]
    return data


def _neg_date(s):
    d = _date(s)
    return -d.toordinal() if d else 0


def _embed(data):
    """JSON that is safe inside a <script> element: no "<" at all, so nothing in a posting can close it."""
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def render(data, template_text):
    """The template with this data and title built in: the page's content, without a document skeleton."""
    title = data["title"].replace("&", "&amp;").replace("<", "&lt;")
    return template_text.replace(TITLE_SLOT, title, 1).replace(DATA_SLOT, _embed(data), 1)


def refresh(root, clock):
    """Write page.json, the publishable copy and My jobs.html. Returns a short summary."""
    folder = store.Folder(root)
    data = build(root, clock)
    data["digest"] = digest(data)
    with open(TEMPLATE, encoding="utf-8") as f:
        content = render(data, f.read())
    folder._write(folder.page_json, json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    folder._write(folder.page_publish_html, content)
    folder._write(folder.page_html, DOCUMENT.format(content=content))
    return {"page": "My jobs.html", "publish": "data/jobs-page.html", "data": "data/page.json",
            "bytes": os.path.getsize(folder.page_json), "version": data["version"], "digest": data["digest"],
            **data["counts"]}
