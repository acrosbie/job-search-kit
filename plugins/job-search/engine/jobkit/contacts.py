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

import csv
import datetime as dt
import io
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


# ------------------------------------------------------------------ who you know there

_SUFFIX = re.compile(r"\b(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|gmbh|plc|sa|ag|the)\b\.?")


def company_key(name):
    """A company's name for matching people to jobs: "BCM One, Inc." and "bcm one" are one company."""
    s = re.sub(r"\(.*?\)", " ", (name or "").casefold())
    s = _SUFFIX.sub(" ", s)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def same_company(a, b):
    """The same company, or one name the other's first words ("Zoom" and "Zoom Video Communications").
    A lead for the user to judge by the names shown, never a fact."""
    ka, kb = company_key(a).split(), company_key(b).split()
    if not ka or not kb:
        return False
    short, long_ = sorted((ka, kb), key=len)
    return long_[:len(short)] == short and len(" ".join(short)) >= 3


def known_at(rows, company, limit=3):
    """The people kept at `company`, the ones touched most recently first."""
    hits = [c for c in rows if same_company(c.get("company", ""), company)]
    hits.sort(key=lambda c: (last_touch(c, "out") or last_touch(c, "in") or "", c.get("added", "")), reverse=True)
    return [{"id": c["id"], "name": c["name"], "title": c.get("title", ""), "kind": c.get("kind", ""),
             "how_known": c.get("how_known", "")} for c in hits[:limit]], len(hits)


# ------------------------------------------------------------------ the LinkedIn connections export

def import_connections(root, clock, path):
    """People from the Connections.csv the user downloaded from LinkedIn themselves: name, company,
    position and profile link, and when they connected. Email addresses are never kept (decision 4).
    Someone already kept keeps what the user said about them."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        text = f.read()
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("First Name")), None)
    if start is None:
        raise Refused("that isn't LinkedIn's connections file: it has no 'First Name' column")
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    rows = load(root)
    by_id = {c["id"]: c for c in rows}
    added = updated = skipped = 0
    for r in reader:
        name = " ".join(f"{r.get('First Name', '')} {r.get('Last Name', '')}".split())
        company = (r.get("Company") or "").strip()
        if not name or not company:
            skipped += 1
            continue
        cid = contact_id(name, company)
        profile = (r.get("URL") or "").strip()
        since = (r.get("Connected On") or "").strip()
        c = by_id.get(cid)
        if c is None:
            c = {"id": cid, "name": name, "company": company, "title": (r.get("Position") or "").strip(),
                 "kind": "other", "email": "", "profile": profile if profile.startswith("http") else "",
                 "how_known": f"LinkedIn connection since {since}" if since else "LinkedIn connection",
                 "source": "connections", "applications": [], "touches": [], "added": clock.today()}
            rows.append(c)
            by_id[cid] = c
            added += 1
        else:
            for field, value in (("title", (r.get("Position") or "").strip()),
                                 ("profile", profile if profile.startswith("http") else "")):
                if value and not c.get(field):
                    c[field] = value
            updated += 1
    save(root, rows)
    return {"added": added, "already_kept": updated, "skipped": skipped, "contacts": len(rows),
            "note": "Email addresses in the file aren't kept."}


# ------------------------------------------------------------------ outreach, counted

def outreach(root, clock, per_day=2, follow_up_days=5):
    """Messages sent today against the daily target, and the people whose last message from the user
    went `follow_up_days` or more ago with no reply since: follow-ups due, oldest first."""
    today = clock.today()
    rows = load(root)
    sent_today = sum(1 for c in rows for t in c.get("touches", []) if t.get("direction") == "out" and t.get("date") == today)
    cut = (dt.date.fromisoformat(today) - dt.timedelta(days=follow_up_days)).isoformat()
    due = []
    for c in rows:
        out_, in_ = last_touch(c, "out"), last_touch(c, "in")
        if out_ and out_ <= cut and in_ < out_:
            due.append({"id": c["id"], "name": c["name"], "company": c.get("company", ""), "sent": out_,
                        "email": c.get("email", "")})
    due.sort(key=lambda x: x["sent"])
    return {"per_day": per_day, "sent_today": sent_today, "follow_ups_due": due}


def week(root, clock, days=7):
    """The last week's messages and replies, for the weekly review."""
    since = (dt.date.fromisoformat(clock.today()) - dt.timedelta(days=days - 1)).isoformat()
    sent = replies = 0
    people = set()
    for c in load(root):
        for t in c.get("touches", []):
            if t.get("date", "") >= since:
                if t.get("direction") == "out":
                    sent += 1
                    people.add(c["id"])
                else:
                    replies += 1
    return {"since": since, "sent": sent, "people": len(people), "replies": replies}


# ------------------------------------------------------------------ a recruiter who writes first

FREE_MAIL = ("gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "ymail.com",
             "aol.com", "icloud.com", "me.com", "proton.me", "protonmail.com", "gmx.com", "mail.com", "zoho.com")


def check_sender(email, company=""):
    """The playbook's first scam check on a message from someone the user doesn't know: where it was
    sent from. Signs, never a verdict."""
    email = (email or "").strip().casefold()
    if not _EMAIL.match(email):
        raise Refused(f"{email!r} isn't an email address")
    domain = email.rsplit("@", 1)[1]
    flags = []
    if domain in FREE_MAIL:
        flags.append(f"sent from a personal address ({domain}), not a company's")
    words = company_key(company).split()
    stem = domain.split(".")[0]
    if company and domain not in FREE_MAIL:
        joined = "".join(words)
        if joined and joined not in domain.replace("-", "") and not any(len(w) > 3 and w in stem for w in words):
            flags.append(f"the address ({domain}) doesn't look like {company}'s")
        elif joined and stem.replace("-", "") != joined and any(x in stem for x in ("career", "jobs", "hr", "recruit", "hiring", "talent")):
            flags.append(f"the address ({domain}) adds words to {company}'s name, as lookalike addresses do")
    return {"email": email, "domain": domain, "free_mail": domain in FREE_MAIL, "flags": flags}
