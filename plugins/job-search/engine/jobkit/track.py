"""Applications: what the user applied to, and what happened next.

data/applications.json holds one record per application:

    id              the posting's key, or app-<company>-<role> when there's no saved posting
    key             the posting's key, or ""
    company, role, urls
    applied_date    the user's local date; applied_date_estimated when they only knew it roughly
    channel         how they applied: company_site, linkedin, referral or other ("" if not known)
    top_pick        whether it's one of their top picks: true, false, or null if not asked
    level           the level word the title matched in settings.toml [titles] level
    posted_pay      the pay the posting stated
    contact         a named person at the company, only ever one the user gave
    followed_up     the date of the last follow-up
    status          applied, replied, screen, interview, offer, rejected, presumed_rejected, withdrawn, closed
    history         every change: date, at, status or event, by (user or engine), note, choice
    note

Only the user records an application or a change to one. The engine makes one change by itself: an
application still at plain "applied" [tracking] presume_after_days (21) after it was sent becomes
presumed_rejected. Nothing else is ever touched by that, so a reply, screen, interview, offer,
rejection or withdrawal is never overwritten, and a reply that arrives later replaces it.

A follow-up is an event with a date, not a status, so it neither stops the day-21 count nor hides a
later reply. Routing a due follow-up is ported from the reference scanner: a follow-up needs someone
to receive it, so one with a recorded contact is sent, a top pick with nobody known becomes a search
for a person, and the rest are left to close at day 21.
"""

import copy
import datetime as dt
import hashlib
import re

from . import schedule, settings, store, verdicts
from .errors import NotFound, Refused

STATUSES = ("applied", "replied", "screen", "interview", "offer", "rejected", "presumed_rejected", "withdrawn", "closed")
CHANNELS = ("company_site", "linkedin", "referral", "other")
ROUTES = ("send", "find_person", "close")

# The tracker's older free-text statuses ("reply 2026-09-20", "**presumed rejected**"), first match wins.
_LEGACY = (("presumed", "presumed_rejected"), ("withdr", "withdrawn"), ("dead", "closed"), ("closed", "closed"),
           ("offer", "offer"), ("interview", "interview"), ("screen", "screen"), ("reject", "rejected"),
           ("repl", "replied"))
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def _slug(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n].strip("-")


def app_id(company, role):
    """The id of an application with no saved posting. A role too long to spell out whole keeps a
    short fingerprint of all of it, so "... Strategic Accounts (East)" and "(West)" stay two."""
    ident = f"app-{_slug(company, 30)}-{_slug(role)}"
    if len(_slug(role, 1000)) > 40:
        ident += "-" + hashlib.sha1(_slug(role, 1000).encode("utf-8")).hexdigest()[:6]
    return ident


def _legacy_app_id(company, role):
    return f"app-{_slug(company, 30)}-{_slug(role)}"  # before 0.8.0: long roles were cut off


# How recent an application recorded by name must be for a newly saved posting to join it on its own.
JOIN_WITHIN_DAYS = 60


def _date(s):
    m = _ISO.search(s or "")
    try:
        return dt.date.fromisoformat(m.group(0)) if m else None
    except ValueError:
        return None


def _check_date(text, today):
    d = _date(text)
    if d is None or not _ISO.fullmatch(text.strip()):
        raise Refused(f"give the date as YYYY-MM-DD, not {text!r}")
    if d > dt.date.fromisoformat(today):
        raise Refused(f"{text} is after today ({today})")
    return d.isoformat()


def _legacy_status(text):
    t = re.sub(r"[*`~]", "", text or "").strip().lower()
    if t in STATUSES:
        return t
    for word, status in _LEGACY:
        if word in t:
            return status
    return "applied"


def normalize(a):
    """One record in the current shape. Rows imported from the reference tracker, and any written
    before this version, gain the fields above; nothing already there is changed."""
    a = dict(a)
    if a.get("status") not in STATUSES:
        if a.get("status"):
            a["status_was"] = a["status"]  # the tracker's own words, kept
        a["status"] = _legacy_status(a.get("status"))
    a.setdefault("key", "")
    a.setdefault("urls", [])
    if not a.get("id"):
        a["id"] = a["key"] or app_id(a.get("company", ""), a.get("role", ""))
    if not a.get("applied_date"):
        d = _date(a.get("applied"))
        a["applied_date"] = d.isoformat() if d else ""
    if "top_pick" not in a:
        fit = re.sub(r"[*`]", "", a.get("fit") or "").strip().lower()
        a["top_pick"] = True if fit.startswith("strong") else (False if fit else None)
    for k, v in (("applied_date_estimated", False), ("channel", ""), ("level", ""), ("posted_pay", ""),
                 ("contact", ""), ("followed_up", ""), ("note", "")):
        if a.get(k) is None:
            a[k] = v
    if not a.get("history"):
        a["history"] = [{"date": a["applied_date"], "status": a["status"], "by": "import"}]
    return a


class Records(list):
    """The applications as loaded, remembering the file's records (`read`) and their current shape as
    first loaded (`base`), so that saving merges with anything another command wrote meanwhile."""
    read = None
    base = None


def load(root):
    raw = store.Folder(root).load_applications()
    out = Records(normalize(a) for a in raw)
    out.read, out.base = raw, copy.deepcopy(list(out))
    return out


def save(root, applications):
    store.Folder(root).save_applications(list(applications), read=getattr(applications, "read", None),
                                         base=getattr(applications, "base", None))


def find(applications, ident):
    """By id, then by posting key."""
    for a in applications:
        if a["id"] == ident:
            return a
    for a in applications:
        if ident and a.get("key") == ident:
            return a
    return None


def unlinked(applications, posting, today=None):
    """An application recorded by company and role, with no saved posting, that is this posting
    (the same link, or the same company and the same title), or None. With `today`, a match by
    title only counts for an application sent in the last JOIN_WITHIN_DAYS days: the same title
    months later is likely a new opening, for the user to say."""
    loose = [a for a in applications if not a.get("key")]
    p = {"company": posting.get("company", ""), "title": posting.get("title", ""), "url": posting.get("url", "")}
    a = store.application_for(p, loose)
    if a is None or today is None:
        return a
    url = (p["url"] or "").rstrip("/")
    if url and url in {u.rstrip("/") for u in a.get("urls", [])}:
        return a
    d = _date(a.get("applied_date"))
    return a if d and (dt.date.fromisoformat(today) - d).days <= JOIN_WITHIN_DAYS else None


def link(root, clock, key):
    """When a posting is saved after the user said they applied to it, join the two: the application
    gains the posting's key, and the posting is marked applied, by the user, who told us so.
    Returns the application, or None if there's none to join."""
    folder = store.Folder(root)
    posting = folder.load_postings()["postings"].get(key)
    applications = load(root)
    a = unlinked(applications, posting, clock.today()) if posting else None
    if a is None:
        return None
    a["key"] = key
    if posting.get("url") and posting["url"] not in a["urls"]:
        a["urls"].append(posting["url"])
    a["history"].append(_event(clock, clock.today(), event="posting_saved", value=key))
    save(root, applications)
    if posting.get("status") != "applied":
        verdicts.mark(root, key, "applied", "user", note=f"applied on {a['applied_date']}, before this job was saved",
                      clock=clock)
    return a


def level_of(role, s):
    m = s.level.search(role or "") if s.level else None
    return m.group(0).strip().lower() if m else ""


def _event(clock, when, note="", choice="", at="", **what):
    e = {"date": when, "at": at or clock.stamp(), **what, "by": "user"}
    if note:
        e["note"] = note
    if choice:
        e["choice"] = choice
    return e


def apply(root, clock, key="", company="", role="", url="", date="", estimated=False, channel="", top_pick=None,
          contact="", note="", choice="", at=""):
    """Record that the user applied. With a posting's key, the posting is marked applied by the user
    as well. Saying so twice updates the one record rather than adding a second. `choice` and `at`
    are the id and time of a click on the jobs page this came from."""
    s = settings.load(root)
    folder = store.Folder(root)
    today = clock.today()
    if channel and channel not in CHANNELS:
        raise Refused(f"how they applied is one of {', '.join(CHANNELS)}, not {channel!r}")
    posting = None
    if key:
        posting = folder.load_postings()["postings"].get(key)
        if not posting:
            raise NotFound(f"unknown key {key}")
        company, role, url = posting["company"], posting["title"], url or posting.get("url", "")
        if not date and posting.get("status") == "applied" and posting.get("triaged"):
            date = posting["triaged"]  # marked applied before applications were recorded
    elif not (company and role):
        raise Refused("give the posting's key, or the company and the role")
    when = _check_date(date, today) if date else today

    applications = load(root)
    ident = key or app_id(company, role)
    a = find(applications, ident)
    if a is None and not key:
        old = find(applications, _legacy_app_id(company, role))  # recorded before ids kept long roles whole
        if old is not None and store._norm_title(old.get("role")) == store._norm_title(role):
            a = old
    if a is None and posting is not None:
        a = unlinked(applications, posting, today)  # recorded by name before the posting was saved
        if a is not None:
            a["key"] = key
    created = a is None
    if created:
        a = {"id": ident, "key": key, "company": company, "role": role, "urls": [url] if url else [],
             "applied_date": when, "applied_date_estimated": bool(estimated), "channel": channel,
             "top_pick": top_pick, "level": level_of(role, s),
             "posted_pay": (posting or {}).get("salary", ""), "contact": contact, "followed_up": "",
             "status": "applied", "history": [_event(clock, when, note, choice, at, status="applied")], "note": note}
        applications.append(a)
    else:
        # A click on the page says "I applied", not when: it never moves a date already recorded.
        if date and when != a["applied_date"] and not choice:
            a["applied_date"], a["applied_date_estimated"] = when, bool(estimated)
            a["history"].append(_event(clock, today, choice=choice, at=at, event="applied_date", value=when))
        for field, value in (("channel", channel), ("contact", contact)):
            if value:
                a[field] = value
        if top_pick is not None:
            a["top_pick"] = top_pick
        if url and url not in a["urls"]:
            a["urls"].append(url)

    if posting is not None and posting.get("status") != "applied":
        verdicts.mark(root, key, "applied", "user", note=note, clock=clock, choice=choice, at=at)
    save(root, applications)
    return {**a, "created": created}


def track(root, clock, ident, status="", date="", note="", contact=None, top_pick=None, channel=None, choice="", at=""):
    """Record what happened to an application: a new status, a follow-up, a contact, or a correction."""
    applications = load(root)
    a = find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    today = clock.today()
    when = _check_date(date, today) if date else today
    if not (status or note or contact is not None or top_pick is not None or channel is not None):
        raise Refused("nothing to record: give a status, a contact, a top pick, how they applied, or a note")
    if status == "followed_up":
        a["followed_up"] = when
        a["history"].append(_event(clock, when, note, choice, at, event="followed_up"))
    elif status == "presumed_rejected":
        raise Refused("presumed rejected is set by the day-21 close; if they turned the user down, it's rejected")
    elif status:
        if status not in STATUSES:
            raise Refused(f"a status is one of {', '.join(STATUSES)}, or followed_up")
        a["status"] = status
        a["history"].append(_event(clock, when, note, choice, at, status=status))
    elif note:
        a["history"].append(_event(clock, when, note, choice, at, event="note"))
    if contact is not None:
        a["contact"] = contact.strip()
        a["history"].append(_event(clock, today, choice=choice, at=at, event="contact", value=a["contact"]))
    if top_pick is not None:
        a["top_pick"] = top_pick
        a["history"].append(_event(clock, today, choice=choice, at=at, event="top_pick", value=top_pick))
    if channel is not None:
        if channel not in CHANNELS:
            raise Refused(f"how they applied is one of {', '.join(CHANNELS)}, not {channel!r}")
        a["channel"] = channel
        a["history"].append(_event(clock, today, choice=choice, at=at, event="channel", value=channel))
    save(root, applications)
    return a


def state(a, today, s):
    """Where one application stands on `today`: days since applying; for one still at "applied", the
    date it closes, and whether a follow-up is due and by which route."""
    d = _date(a.get("applied_date"))
    out = {"days": (today - d).days if d else None, "closes_on": "", "due": False, "route": ""}
    if a["status"] != "applied" or d is None:
        return out
    out["closes_on"] = (d + dt.timedelta(days=s.presume_after_days)).isoformat()
    if not a.get("followed_up") and out["days"] >= s.follow_up_after_days:
        out["due"] = True
        out["route"] = "send" if a.get("contact") else ("find_person" if a.get("top_pick") else "close")
    return out


def close_due(root, clock):
    """The day-21 close: every application still at plain "applied" presume_after_days after it was
    sent becomes presumed_rejected. Returns the ones closed now."""
    s = settings.load(root)
    applications = load(root)
    today = dt.date.fromisoformat(clock.today())
    closed = []
    for a in applications:
        d = _date(a.get("applied_date"))
        if a["status"] != "applied" or d is None or (today - d).days < s.presume_after_days:
            continue
        a["status"] = "presumed_rejected"
        a["history"].append({"date": (d + dt.timedelta(days=s.presume_after_days)).isoformat(), "at": clock.stamp(),
                             "status": "presumed_rejected", "by": "engine",
                             "note": f"no reply {s.presume_after_days} days after applying"})
        closed.append(a)
    if closed:
        save(root, applications)
    return closed


def brief(a):
    return {k: a.get(k) for k in ("id", "key", "company", "role", "status", "applied_date", "contact", "top_pick")}


def listing(root, clock):
    """Every application with where it stands, newest first."""
    s = settings.load(root)
    today = dt.date.fromisoformat(clock.today())
    rows = [{**a, **state(a, today, s)} for a in load(root)]
    return sorted(rows, key=lambda r: r.get("applied_date") or "", reverse=True)


def due(root, clock):
    """Close what has reached day 21, then list the follow-ups due, by route."""
    closed = close_due(root, clock)
    s = settings.load(root)
    today = dt.date.fromisoformat(clock.today())
    out = {"today": today.isoformat(), "closed_now": [brief(a) for a in closed], "send": [], "find_person": [],
           "closing": [], "open": 0}
    for a in load(root):
        st = state(a, today, s)
        out["open"] += a["status"] == "applied"
        if st["due"]:
            out["closing" if st["route"] == "close" else st["route"]].append({**brief(a), **st})
    for route in ("send", "find_person", "closing"):
        out[route].sort(key=lambda r: -(r["days"] or 0))
    runs = store.Folder(root).read_runs(limit=1)
    out["last_scan_at"] = runs[-1].get("at", "") if runs else ""
    out.update(schedule.facts(root, s, clock))  # what catching up needs: an overdue scan, a review
    return out
