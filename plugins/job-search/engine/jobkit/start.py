"""The start of every conversation, in one command: what the first minute needs to know.

`start` answers in one short JSON: the engine and Python, whether the folder is set up, anything wrong
with the records, the last scan, and a list `next` of what only Claude can do now, in order: read the
jobs page's clicks, bring the page up to date, offer a scan or the weekly review, ask for an
interview's time, and so on. Each skill runs it first and works down `next`; nothing else is read to
get started.

It changes nothing a user would notice. It doesn't run the day-21 close: news the user brings ("Acme
replied") is recorded first, then `due` closes what's left, as before. It does write the jobs page's
files, so whether the page in their Claude account is behind is judged on the records as they are.

`doctor` is the same checks in full, for when something is wrong, with `probe` if asked.
"""

import datetime as dt
import json
import os
import sys

from . import __fingerprint__, __version__, fingerprint, interviews, news, page, resume, schedule, settings, store, track

PROFILE = ("profile/settings.toml", "profile/companies.toml", "profile/rules.md", "profile/about-me.md",
           "profile/what-i-want.md")
OPEN = ("applied", "replied", "screen", "interview", "offer")
ASK_CHANNELS = 3  # how many applications to ask about at once


def _python_ok():
    return sys.version_info >= (3, 10)


def _bad_lines(path):
    """Lines in an append-only log that can't be read (the engine skips them; a few after a crash are
    harmless, many mean the file was broken)."""
    if not os.path.exists(path):
        return 0
    bad = 0
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except ValueError:
                bad += 1
    return bad


def checks(root):
    """What's wrong with the records, each as {"what", "detail", "fix"} in plain words. Reading the
    applications also puts right any id two of them shared (track.load)."""
    folder = store.Folder(root)
    problems = []
    for path, backup, name in ((folder.applications_json, folder.applications_backup_json, "applications"),
                               (folder.postings_json, folder.backup_json, "saved jobs")):
        if not os.path.exists(path):
            continue
        try:
            _, from_backup = folder._read_json_or_backup(path, backup)
        except ValueError:
            problems.append({"what": f"{name} file unreadable", "detail": os.path.relpath(path, root),
                             "fix": "restore it from a snapshot (run.py snapshots), with the user's yes"})
            continue
        if from_backup:
            problems.append({"what": f"{name} file was half-written", "detail": os.path.relpath(path, root),
                             "fix": "its backup is being read instead; the next change writes it whole again"})
    try:
        apps = track.load(root)
        postings = folder.load_postings()["postings"]
    except ValueError:
        return problems, {}
    repaired = [a for a in apps if a.get("id_was")]
    nameless = [a for a in apps if (a.get("company") or "").strip().lower() in ("", "unknown")]
    no_company = [a for a in nameless if a["status"] in OPEN]  # a closed one can stay as it is
    no_date = [a for a in apps if not a.get("applied_date")]
    keys = {}
    for a in apps:
        if a.get("key"):
            keys.setdefault(a["key"], []).append(a["id"])
    shared_keys = {k: v for k, v in keys.items() if len(v) > 1}
    orphans = [a for a in apps if a.get("key") and a["key"] not in postings]
    unknown_status = [k for k, v in postings.items() if v.get("status") not in store.STATUSES]
    if no_company:
        problems.append({"what": "open applications with no company name", "detail": [a["id"] for a in no_company],
                         "fix": "ask the user which company each was, and record it"})
    if shared_keys:
        problems.append({"what": "two applications joined to one saved job", "detail": shared_keys,
                         "fix": "ask the user which application the job belongs to"})
    if unknown_status:
        problems.append({"what": "saved jobs with a status the kit doesn't have", "detail": unknown_status[:10],
                         "fix": "they show nowhere; restore postings.json from a snapshot, or ask the user"})
    for log in ("decisions_log", "runs_log", "choices_log", "changes_log", "reviews_log"):
        bad = _bad_lines(getattr(folder, log))
        if bad > 1:
            problems.append({"what": f"{os.path.basename(getattr(folder, log))} has {bad} unreadable lines",
                             "detail": os.path.relpath(getattr(folder, log), root),
                             "fix": "they are skipped; nothing to do unless the user edited the file by hand"})
    facts = {"applications": len(apps), "saved_jobs": len(postings), "ids_repaired": len(repaired),
             "no_company": len(nameless), "no_applied_date": len(no_date), "linked_to_missing_job": len(orphans)}
    return problems, facts


def _closing_today(root, clock):
    """Applications the day-21 close would close if `due` ran now."""
    s = settings.load(root)
    today = dt.date.fromisoformat(clock.today())
    out = []
    for a in track.load(root):
        d = track._date(a.get("applied_date"))
        if a["status"] == "applied" and d and (today - d).days >= s.presume_after_days:
            out.append(track.brief(a))
    return out


def start(root, clock, expect=""):
    """Everything catching up needs, and what to do next, in order."""
    out = {"engine": {"version": __version__, "fingerprint": __fingerprint__,
                      "current": (not expect) or expect == __fingerprint__},
           "python": {"version": sys.version.split()[0], "ok": _python_ok()},
           "folder_ready": os.path.exists(os.path.join(root, "profile", "settings.toml"))}
    nxt = []
    if expect and expect != __fingerprint__:
        nxt.append({"do": "refresh_engine", "why": "the folder's engine isn't the plugin's; copy it, then run start again"})
    if not out["folder_ready"]:
        nxt.append({"do": "offer_setup", "why": "this folder hasn't been set up yet"})
        out["next"] = nxt
        return out

    s = settings.load(root)
    folder = store.Folder(root)
    problems, facts = checks(root)
    out["records"] = {**facts, "problems": len(problems)}

    try:  # so whether the page is behind is judged on the records as they are now
        page.refresh(root, clock)
    except Exception as e:
        out["page_error"] = f"{type(e).__name__}: {e}"
    runs = folder.read_runs()
    last_ok, last_try = schedule.last_scans(runs)
    out["scan"] = {"last_good_at": last_ok.get("at", ""), "last_attempt_at": last_try.get("at", ""),
                   "last_status": schedule.status_of(last_try), "overdue": schedule.scan_overdue(s, runs, clock),
                   "scheduled": s.schedule.get("scan", ""), "fresh": schedule.fresh(last_ok, clock)}
    ready, review_due = schedule.review_state(root, s, clock)
    soon = interviews.soon(root, clock)
    debrief = interviews.debrief_due(root, clock)
    stale = resume.stale(root)
    closing = _closing_today(root, clock)
    apps = track.load(root)
    open_no_channel = [a for a in apps if a["status"] in OPEN and not a.get("channel")]
    open_no_channel.sort(key=lambda a: a.get("applied_date") or "", reverse=True)
    route = s.page.get("route", "")
    data = folder.read_json(folder.page_json) or {}
    out["page"] = {"url": s.page.get("url", ""), "route": route,
                   "design_current": s.page.get("version", "") == data.get("design", ""),
                   "behind": schedule.page_behind(root, s)}

    # What only Claude can do, in the order to do it.
    if problems:
        nxt.append({"do": "tell_about_records", "why": "something in the records needs the user", "problems": problems})
    if route != "file":
        if out["page"]["url"]:
            nxt.append({"do": "read_clicks", "why": "the user may have marked jobs on their jobs page"})
            if not out["page"]["design_current"]:
                nxt.append({"do": "republish_page", "why": "the page has a new design"})
            elif out["page"]["behind"]:
                nxt.append({"do": "push_page", "why": "the page doesn't yet show what the folder holds"})
        else:
            nxt.append({"do": "publish_page", "why": "the user has no jobs page in their Claude account yet"})
    if closing:
        nxt.append({"do": "run_due_after_news", "why": "applications reach day 21 today; record any news the user "
                    "brings first, then run due", "applications": closing})
    if out["scan"]["overdue"]:
        nxt.append({"do": "offer_scan", "why": "a scheduled check didn't run", "last_good_at": out["scan"]["last_good_at"]})
    if out["scan"]["last_status"] in ("blocked", "failed"):
        nxt.append({"do": "say_last_scan_failed", "why": "the last check reached no job board",
                    "status": out["scan"]["last_status"], "last_good_at": out["scan"]["last_good_at"]})
    if ready or review_due:
        nxt.append({"do": "offer_review", "why": "the weekly review is ready" if ready else "a week since the last review"})
    for x in soon:
        if x.get("time_unknown"):
            nxt.append({"do": "ask_interview_time", "why": "an interview soon with no time yet", "interview": _short(x)})
        nxt.append({"do": "offer_prep", "why": "an interview in the next few days", "interview": _short(x)})
    for x in debrief:
        nxt.append({"do": "offer_debrief", "why": "an interview held and not gone through", "interview": _short(x)})
    if open_no_channel:
        nxt.append({"do": "ask_channels", "why": "how these were sent isn't known, so outcomes can't be counted by it",
                    "applications": [track.brief(a) for a in open_no_channel[:ASK_CHANNELS]],
                    "more": max(0, len(open_no_channel) - ASK_CHANNELS)})
    if stale:
        nxt.append({"do": "offer_resume_update", "why": "a resume no longer matches", "resumes": stale})
    lines = news.unseen(root, has_history=bool(runs))
    if lines:
        nxt.append({"do": "say_whats_new", "why": "the kit was updated since this folder last used it", "lines": lines})
    out["next"] = nxt
    return out


def _short(x):
    return {k: x.get(k) for k in ("application", "num", "company", "role", "on", "stage", "with", "days", "time_unknown")}


def doctor(root, clock, probe=False):
    """The same checks in full: the engine's files, the profile, every record, the scan, snapshots, and
    (with `probe`) whether job boards can be reached from here."""
    out = {"engine": {"version": __version__, "fingerprint": __fingerprint__,
                      "files_match": fingerprint.compute() == __fingerprint__},
           "python": {"version": sys.version.split()[0], "ok": _python_ok()},
           "folder_ready": os.path.exists(os.path.join(root, "profile", "settings.toml")),
           "profile": {rel: os.path.exists(os.path.join(root, *rel.split("/"))) for rel in PROFILE}}
    if not out["folder_ready"]:
        return out
    problems, facts = checks(root)
    out["records"] = facts
    out["problems"] = problems
    folder = store.Folder(root)
    runs = folder.read_runs()
    last_ok, last_try = schedule.last_scans(runs)
    out["scan"] = {"last_good_at": last_ok.get("at", ""), "last_attempt_at": last_try.get("at", ""),
                   "last_status": schedule.status_of(last_try), "runs": len(runs)}
    snaps = folder.list_snapshots()
    out["snapshots"] = {"kept": len(snaps), "newest": snaps[0]["at"] if snaps else ""}
    if probe:
        from . import scan
        out["network"] = scan.probe(root)
    out["ok"] = not problems and out["engine"]["files_match"] and out["python"]["ok"]
    return out
