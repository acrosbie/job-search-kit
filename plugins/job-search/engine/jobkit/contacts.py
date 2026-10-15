"""People the user knows at companies: one record each, in data/contacts.json (decision 4).

Every name comes from the user: said in chat, met in an interview, or in a LinkedIn connections export
they downloaded themselves. Claude never looks a person up, opens a profile or guesses an email; an
email is kept only when the user gives it.

    id            "c-<name>-<company>", for good
    name          as the user gave it
    company       where they work
    title         their job, in the user's words ("Head of CX")
    kind          recruiter, hiring_manager, interviewer, referrer, colleague or other
    email         only one the user gave
    profile       a link the user gave, if any
    how_known     the user's words ("former colleague at Zoom")
    source        you (said in chat), interview (met in one) or connections (the export)
    applications  the application ids this person is part of
    touches       [{date, channel, direction (out or in), note}]: a thank-you, a message, a reply
    added         the day the record was made
"""

import datetime as dt
import os
import re

from . import store
from .errors import NotFound, Refused

KINDS = ("recruiter", "hiring_manager", "interviewer", "referrer", "colleague", "other")
CHANNELS = ("email", "linkedin", "phone", "in_person", "other")
SOURCES = ("you", "interview", "connections")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _path(root):
    return os.path.join(store.Folder(root).data, "contacts.json")


def load(root):
    data = store.Folder(root).read_json(_path(root)) or {}
    return data.get("contacts", [])


def save(root, rows):
    store.Folder(root).write_json(_path(root), {"contacts": rows})


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").casefold()).strip("-")


def contact_id(name, company):
    return "c-" + "-".join(p for p in (_slug(name), _slug(company)) if p)


def find(rows, ident):
    """By id, or by name (and company, when given as "Name, Company"). Two matches is never guessed."""
    if not ident:
        return None
    hits = [c for c in rows if c["id"] == ident]
    if not hits:
        name, _, company = ident.partition(",")
        hits = [c for c in rows if c["name"].casefold() == name.strip().casefold()
                and (not company.strip() or c.get("company", "").casefold() == company.strip().casefold())]
    if len(hits) > 1:
        raise Refused(f"{len(hits)} people match {ident!r}: " + ", ".join(c["id"] for c in hits) + "; give the id")
    return hits[0] if hits else None


def add(root, clock, name, company="", title="", kind="other", email="", profile="", how_known="", source="you",
        application=""):
    """Record a person the user named, or add what's new to the one already kept: the same name at the
    same company is one person. Fields left empty don't overwrite what's there."""
    name = " ".join((name or "").split())
    if not name:
        raise Refused("a contact needs the name the user gave")
    if kind not in KINDS:
        raise Refused(f"a contact's kind is one of {', '.join(KINDS)}, not {kind!r}")
    if source not in SOURCES:
        raise Refused(f"where a contact came from is one of {', '.join(SOURCES)}, not {source!r}")
    email = (email or "").strip()
    if email and not _EMAIL.match(email):
        raise Refused(f"{email!r} isn't an email address; keep only one the user gave, exactly")
    if profile and not re.match(r"^https?://\S+$", profile.strip()):
        raise Refused(f"a profile is a link the user gave, starting https://, not {profile!r}")
    rows = load(root)
    cid = contact_id(name, company)
    c = next((x for x in rows if x["id"] == cid), None)
    if c is None:
        c = {"id": cid, "name": name, "company": (company or "").strip(), "title": "", "kind": kind, "email": "",
             "profile": "", "how_known": "", "source": source, "applications": [], "touches": [],
             "added": clock.today()}
        rows.append(c)
    elif kind != "other":
        c["kind"] = kind
    for field, value in (("title", title), ("email", email), ("profile", profile), ("how_known", how_known)):
        if (value or "").strip():
            c[field] = value.strip()
    if application and application not in c["applications"]:
        c["applications"].append(application)
    save(root, rows)
    return c


def touch(root, clock, ident, channel="email", direction="out", note="", date=""):
    """A message to or from a person: a thank-you, a referral ask, their reply."""
    if channel not in CHANNELS:
        raise Refused(f"how it was sent is one of {', '.join(CHANNELS)}, not {channel!r}")
    if direction not in ("out", "in"):
        raise Refused("a touch is out (the user sent it) or in (they heard back)")
    day = date or clock.today()
    try:
        dt.date.fromisoformat(day)
    except ValueError:
        raise Refused(f"give the day as YYYY-MM-DD, not {day!r}") from None
    rows = load(root)
    c = find(rows, ident)
    if c is None:
        raise NotFound(f"no contact {ident}")
    c["touches"].append({"date": day, "channel": channel, "direction": direction, "note": (note or "").strip()})
    c["touches"].sort(key=lambda t: t["date"])
    save(root, rows)
    return c


def listing(root, company="", application=""):
    rows = load(root)
    if company:
        rows = [c for c in rows if c.get("company", "").casefold() == company.casefold()]
    if application:
        rows = [c for c in rows if application in c.get("applications", [])]
    return rows


def last_touch(c, direction="out"):
    days = [t["date"] for t in c.get("touches", []) if t.get("direction") == direction]
    return max(days) if days else ""
