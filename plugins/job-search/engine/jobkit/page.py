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
import json
import os

from . import __version__, schedule, settings, store, track

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

    decided_by = {d.get("key"): d.get("by", "") for d in folder.read_decisions()}  # who made the latest decision

    def job(k, v):
        return {"num": v.get("num"), "key": k, "by": decided_by.get(k, ""), "company": v.get("company", ""),
                "title": v.get("title", ""), "location": v.get("location", ""), "url": v.get("url", ""), "salary": v.get("salary", ""),
                "status": v.get("status", ""), "note": v.get("note", ""), "flag": v.get("flag", ""),
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
            todo.append({**{k: item[k] for k in ("num", "id", "company", "role", "days", "contact", "closes_on")},
                         "route": st["route"]})
    route_order = {r: i for i, r in enumerate(track.ROUTES)}
    todo.sort(key=lambda t: (route_order[t["route"]], -(t["days"] or 0)))

    name = (s.raw.get("you", {}).get("name") or "").strip()
    return _fit({
        "version": __version__,
        "title": f"{name}'s job search" if name else "My job search",
        "as_of": clock.stamp(),
        "today": today.isoformat(),
        "counts": {"waiting": len(waiting_out), "to_do": len(todo),
                   "open": sum(1 for a in apps_out if a["status"] in ("applied", "replied", "screen", "interview", "offer")),
                   "applications": len(apps_out)},
        "tracking": {"follow_up_after_days": s.follow_up_after_days, "presume_after_days": s.presume_after_days},
        "review_ready": schedule.review_state(root, s, clock)[0],
        "waiting": waiting_out,
        "todo": todo,
        "applications": apps_out,
        "screened": [{**job(k, v), "date": v.get("triaged") or v.get("first_seen", "")} for k, v in screened],
        "more_waiting": 0,
    })


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
    with open(TEMPLATE, encoding="utf-8") as f:
        content = render(data, f.read())
    folder._write(folder.page_json, json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    folder._write(folder.page_publish_html, content)
    folder._write(folder.page_html, DOCUMENT.format(content=content))
    return {"page": "My jobs.html", "publish": "data/jobs-page.html", "data": "data/page.json",
            "bytes": os.path.getsize(folder.page_json), "version": data["version"], **data["counts"]}
