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


def good(run):
    """A scan that read at least one board. One that reached none (a proxy, no connection) checked
    nothing, so it isn't the last scan, however recent."""
    return (run.get("boards") or 0) > 0 and run.get("status") not in ("blocked", "failed")


def last_scans(runs):
    """(the last full scan that read boards, the last full scan tried, whatever happened): run rows or {}.
    A one-board check (`only`) isn't the scan the schedule asks for."""
    full = [r for r in runs if not r.get("only")]
    ok = [r for r in full if good(r)]
    return (ok[-1] if ok else {}), (full[-1] if full else {})


def status_of(run):
    if not run:
        return ""
    if run.get("status"):
        return run["status"]
    return "failed" if not good(run) else ("partial" if run.get("failed") else "ok")  # rows from before 0.9.0


def scan_overdue(s, runs, clock):
    """True when the schedule says a scan should have run since the last one that read boards."""
    every = s.schedule.get("scan", "")
    if every not in SCAN_DAYS:
        return False
    last_ok, _ = last_scans(runs)
    last = _local_day(last_ok.get("at", ""), clock)
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
    runs = folder.read_runs()
    last_ok, last_try = last_scans(runs)
    return {"scan_overdue": scan_overdue(s, runs, clock), "last_scan_at": last_ok.get("at", ""),
            "last_attempt_at": last_try.get("at", ""), "last_scan_status": status_of(last_try),
            "review_ready": ready, "review_due": due}
