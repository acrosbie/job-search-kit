"""When a check is due, from settings.toml [schedule]: `scan` (daily, weekdays or weekly) and
`review` (weekly). Every conversation starts by catching up (running-the-engine.md): an overdue scan
runs first in scan and triage, and is offered elsewhere; a prepared review is offered.

Scheduled tasks run only while the computer is on and Claude is open (decision 3), so a check can
be missed; these facts are how the next conversation notices.
"""

import datetime as dt

from . import store

SCAN_DAYS = {"daily": 1, "weekdays": 1, "weekly": 7}
REVIEW_DAYS = 7


def _when(s):
    try:
        t = dt.datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _local_day(stamp, clock):
    t = _when(stamp)
    return t.astimezone(clock.now().tzinfo).date() if t else None


def scan_overdue(s, runs, clock):
    """True when the schedule says a scan should have run since the last one."""
    every = s.schedule.get("scan", "")
    if every not in SCAN_DAYS:
        return False
    full = [r for r in runs if not r.get("only")]  # a one-board check isn't the scan the schedule asks for
    last = _local_day(full[-1].get("at") if full else "", clock)
    if last is None:
        return True
    today = clock.now().date()
    if every == "weekdays":
        due = today
        while due.weekday() >= 5:  # the latest weekday on or before today
            due -= dt.timedelta(days=1)
        return last < due
    return (today - last).days >= SCAN_DAYS[every]


def review_state(root, s, clock):
    """(ready, due): the date a prepared review is waiting to be gone through, or ""; and whether a
    weekly review is due (scheduled, and none gone through for a week)."""
    rows = store.Folder(root).read_reviews()
    ready = ""
    for r in rows:
        if r.get("kind") == "prepared":
            ready = r.get("date", "")
        elif r.get("kind") == "done":
            ready = ""
    due = False
    if s.schedule.get("review") == "weekly":
        done = [_local_day(r.get("at"), clock) for r in rows if r.get("kind") == "done"]
        runs = store.Folder(root).read_runs()
        start = done[-1] if done else _local_day(runs[0].get("at") if runs else "", clock)
        due = start is not None and (clock.now().date() - start).days >= REVIEW_DAYS
    return ready, due


def page_behind(root, s):
    """True when the user has a jobs page and it doesn't yet show what the folder holds: the last
    data sent to it ([page] pushed) isn't the folder's page.json. A skipped update, or a scheduled
    check that couldn't reach the page, is then caught up by the next conversation."""
    if not s.page.get("url"):
        return False
    data = store.Folder(root).read_json(store.Folder(root).page_json) or {}
    return data.get("digest", "") != s.page.get("pushed", "")


def facts(root, s, clock):
    folder = store.Folder(root)
    ready, due = review_state(root, s, clock)
    return {"scan_overdue": scan_overdue(s, folder.read_runs(limit=1), clock), "review_ready": ready,
            "review_due": due}
