"""Interviews: when they are, a calendar file for each, what's coming up and what needs a debrief, a
check that what the user plans to say traces to what they've confirmed, and the pay their saved
postings state.

An interview is kept on its application (applications.json), in `upcoming`:

    on         "YYYY-MM-DDTHH:MM" in the user's time zone, or a date alone
    kind       phone, video or onsite ("" if not said)
    with       who, in the user's words ("Dana, recruiter")
    minutes    how long, or 0 if not said
    link       the video call's link, if the user gave it
    stage      screen or interview, the application's status it belongs to
    asker      who's asking: recruiter, hiring_manager, head_of_function, executive, peer, panel or other
    for        what the round is for, in the user's words ("final round with the CEO")
    interviewers  the contacts met in it (contacts.py), each named by the user
    thanked    {contact id or "none": the day the thank-you went out, or the user said there'd be none}
    calendar   the .ics file written for it, under interviews/
    sequence   how many times that file has been written again (calendars take the highest as current)
    debriefed  the date the user went through how it went, or ""

Rounds the user knows are coming but has no day for yet ("two more rounds, then the CEO") are kept in
the application's `expected`: [{for, asker, with, noted}]. Recording a round with the same asker takes
the first such one off the list.

The prep sheet, the story bank and the quick reference are Claude's writing, in the user's folder
under interviews/ (the interview skill). Lines under an Opener, Answers, Stories, Gaps, Strengths or
Caveats heading are claims: each carries `from:` lines quoting about-me.md, and `interview check` holds them
to the same rules as a resume (resume.py). Everything else (the company, the role, logistics, comp,
questions to ask, what not to say, the debrief) is free text.
"""

import datetime as dt
import os
import re

from . import resume, settings, store, text, track
from .errors import BadFile, NotFound, Refused

FOLDER = "interviews"
KINDS = ("phone", "video", "onsite")
SOON_DAYS = 3        # an interview this close is offered prep when catching up
TIME_DAYS = 7        # one this close with no time yet: ask for it (the page's Today does the same)
DEBRIEF_DAYS = 14    # one held this recently, and not gone through, is offered a debrief
THANKS_DAYS = 3      # one held this recently: has the thank-you gone out?
ASKERS = ("recruiter", "hiring_manager", "head_of_function", "executive", "peer", "panel", "other")
CLAIM_SECTIONS = ("opener", "answer", "stor", "gap", "strength", "caveat")
CHEAT_LINES = 60     # a round's cheat sheet is one phone-length scroll (found in real use: a 10 KB one, 2026-10-14)
_SOURCED = re.compile(r"https?://\S+")
_DATED = re.compile(r"\b(19|20)\d{2}\b")

_WHEN = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{1,2}):(\d{2}))?$")


# ------------------------------------------------------------------ scheduling


def parse_on(value):
    """"2026-10-08T10:00", "2026-10-08 10:00" or "2026-10-08", checked, as "YYYY-MM-DD[THH:MM]"."""
    m = _WHEN.match((value or "").strip())
    if not m:
        raise Refused(f"give when as YYYY-MM-DD, or YYYY-MM-DDTHH:MM for a time, not {value!r}")
    day = m.group(1)
    try:
        dt.date.fromisoformat(day)
    except ValueError:
        raise Refused(f"{day} isn't a date") from None
    if m.group(2) is None:
        return day
    hour, minute = int(m.group(2)), int(m.group(3))
    if hour > 23 or minute > 59:
        raise Refused(f"{value} isn't a time of day")
    return f"{day}T{hour:02d}:{minute:02d}"


def _clean(s, n=60):
    """Text fit for a folder name: no markdown links, no characters Windows refuses, not too long."""
    s = re.sub(r"\(\[[^\]]*\]\([^)]*\)\)", "", s or "")       # "([posting](https://...))"
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)              # "[text](link)" -> "text"
    s = re.sub(r"\s*\(.*$", "", s)                              # "(United States; Remote)" and anything after
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:n].rstrip(" .") or "interview"


def folder_for(a):
    """interviews/<Company> - <Role>, relative to the user's folder."""
    return f"{FOLDER}/{_clean(a.get('company', ''), 40)} - {_clean(a.get('role', ''))}"


def _start(entry, tz):
    """The interview's start as an aware datetime, or None for a date with no time."""
    day, _, hm = entry["on"].partition("T")
    if not hm:
        return None
    naive = dt.datetime.fromisoformat(f"{day}T{hm}")
    return naive.replace(tzinfo=tz) if tz else naive.astimezone()


def _fold(line):
    """An iCalendar content line folded at 75 octets, as the format asks."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    out, chunk = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(chunk) + len(b) > (75 if not out else 74):
            out.append(chunk.decode("utf-8"))
            chunk = b""
        chunk += b
    out.append(chunk.decode("utf-8"))
    return "\r\n ".join(out)


def _ics_text(s):
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar(a, entry, tz, stamp, cancel=False):
    """An .ics file's text for one interview: double-clicked, it opens in the user's calendar.

    Its UID is the application and the day, so the file written again when the time is known (or
    anything else changes) updates the same event rather than adding a second; SEQUENCE says which
    is newer. A day with no time yet is a tentative all-day event with no reminder: one 30 minutes
    before an all-day event would go off the evening before. `cancel` writes the same event cancelled:
    opened, it takes the interview off the calendar."""
    who = f" with {entry['with']}" if entry.get("with") else ""
    stage = {"screen": "screen", "interview": "interview"}.get(entry.get("stage"), "interview")
    summary = f"{a.get('company', '')}: {entry.get('kind') + ' ' if entry.get('kind') else ''}{stage}{who}"
    desc = f"{_clean(a.get('role', ''), 120)}. Prep: {folder_for(a)}/prep.md in your Job Search folder."
    if entry.get("link"):
        desc = f"Join: {entry['link']}\n{desc}"
    uid = f"{re.sub(r'[^a-z0-9-]+', '-', a['id'].lower())}-{entry['on'][:10]}@job-search-kit"
    start = _start(entry, tz)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//job-search-kit//interview//EN", "CALSCALE:GREGORIAN",
             f"METHOD:{'CANCEL' if cancel else 'PUBLISH'}", "BEGIN:VEVENT", f"UID:{uid}", f"SEQUENCE:{entry.get('sequence', 0)}",
             f"DTSTAMP:{stamp}"]
    if start is None:  # a date with no time: tentative, all day, and the day isn't shown as busy
        day = dt.date.fromisoformat(entry["on"])
        lines += [f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + dt.timedelta(days=1):%Y%m%d}",
                  "STATUS:TENTATIVE", "TRANSP:TRANSPARENT"]
        summary = f"Time to confirm: {summary}"
    else:
        utc = start.astimezone(dt.timezone.utc)
        end = utc + dt.timedelta(minutes=entry.get("minutes") or 30)
        lines += [f"DTSTART:{utc:%Y%m%dT%H%M%SZ}", f"DTEND:{end:%Y%m%dT%H%M%SZ}", "STATUS:CONFIRMED"]
    if cancel:
        lines = [x for x in lines if not x.startswith("STATUS:")] + ["STATUS:CANCELLED"]
        summary = f"Cancelled: {summary.replace('Time to confirm: ', '')}"
    lines += [f"SUMMARY:{_ics_text(summary)}", f"DESCRIPTION:{_ics_text(desc)}"]
    if entry.get("link"):
        lines += [f"LOCATION:{_ics_text(entry['link'])}", f"URL:{entry['link']}"]
    elif entry.get("kind"):
        lines.append(f"LOCATION:{_ics_text({'phone': 'Phone', 'video': 'Video call', 'onsite': 'On site'}[entry['kind']])}")
    if start is not None and not cancel:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-PT30M", f"DESCRIPTION:{_ics_text(summary)}", "END:VALARM"]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"


def schedule(root, clock, ident, on, kind="", who="", minutes=0, status="", note="", link="", asker="", purpose=""):
    """Record an interview on its application, and write its calendar file. `status` (screen or
    interview) moves the application on, as `track` would. Saying it again for the same day updates
    that interview rather than adding a second."""
    on = parse_on(on)
    if kind and kind not in KINDS:
        raise Refused(f"the kind of interview is one of {', '.join(KINDS)}, not {kind!r}")
    link = (link or "").strip()
    if link and not re.match(r"^https?://\S+$", link):
        raise Refused(f"the call's link is a web address starting https://, not {link!r}")
    if status and status not in ("screen", "interview"):
        raise Refused("an interview's stage is screen or interview")
    if asker and asker not in ASKERS:
        raise Refused(f"who's asking is one of {', '.join(ASKERS)}, not {asker!r}")
    applications = track.load(root)
    a = track.find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    stage = status or (a["status"] if a["status"] in ("screen", "interview") else "interview")
    # An interview booked moves an application that hadn't got that far, so day 21 can't close it.
    if a["status"] != stage and (status or a["status"] in ("applied", "replied", "presumed_rejected")):
        a["status"] = stage
        a["history"].append(track._event(clock, clock.today(), note, status=stage))
    elif note:
        a["history"].append(track._event(clock, clock.today(), note, event="note"))
    entries = a.setdefault("upcoming", [])
    entry = next((e for e in entries if e["on"][:10] == on[:10] and not e.get("debriefed") and not e.get("cancelled")), None)
    is_new = entry is None
    if entry is None:
        entry = {"on": on, "kind": "", "with": "", "minutes": 0, "stage": stage, "calendar": "", "debriefed": "",
                 "sequence": 0}
        entries.append(entry)
    else:
        entry["sequence"] = entry.get("sequence", 0) + 1  # the same event, written again
    entry.update({"on": on, "stage": stage})
    for field, value in (("kind", kind), ("with", (who or "").strip()), ("link", link), ("asker", asker),
                         ("for", (purpose or "").strip())):
        if value:
            entry[field] = value
    expected = a.get("expected") or []
    match = next((x for x in expected if asker and x.get("asker") == asker), None) or (expected[0] if expected and not asker else None)
    if is_new and match is not None and (asker or purpose):  # the round they were waiting for now has its day
        expected.remove(match)
        entry.setdefault("for", match.get("for", ""))
    if minutes:
        entry["minutes"] = int(minutes)
    entries.sort(key=lambda e: e["on"])
    a["history"].append(track._event(clock, clock.today(), event="interview_scheduled", value=on))

    folder = os.path.join(root, *folder_for(a).split("/"))
    os.makedirs(folder, exist_ok=True)
    name = f"{on[:10]} {stage}.ics"
    with open(os.path.join(folder, name), "w", encoding="utf-8", newline="") as f:
        # The zone itself, not today's offset: an interview after a clock change keeps its hour.
        f.write(calendar(a, entry, clock.tz, clock.now().astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    entry["calendar"] = f"{folder_for(a)}/{name}"
    track.save(root, applications)
    return {"application": a["id"], "company": a.get("company", ""), "role": a.get("role", ""), **entry,
            "prep": f"{folder_for(a)}/prep.md"}


def debriefed(root, clock, ident, on=""):
    """The user went through how an interview went: the last one held (or the one on `on`)."""
    applications = track.load(root)
    a = track.find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    today = clock.today()
    held = [e for e in a.get("upcoming", []) if not e.get("cancelled")
            and (e["on"][:10] == on[:10] if on else e["on"][:10] <= today)]
    if not held:
        raise Refused("there's no interview to debrief on that application" + (f" on {on}" if on else " yet"))
    # What they said is written down before it counts as gone through: one "## Debrief" section in the
    # prep sheet for every interview debriefed on this application.
    prep = os.path.join(root, *folder_for(a).split("/"), "prep.md")
    written = 0
    if os.path.exists(prep):
        with open(prep, encoding="utf-8-sig") as f:
            # a "## Debrief" heading with some words under it before the next heading
            written = len(re.findall(r"^## Debrief\b.*\n+(?!#)\S", f.read(), re.M))
    done = sum(1 for e in a.get("upcoming", []) if e.get("debriefed"))
    if written <= done:
        raise Refused(f"write the debrief first: add '## Debrief, {today}' with what they told you, in their words, to "
                      f"{folder_for(a)}/prep.md (make the file if there's no prep sheet), then run this again")
    entry = held[-1]
    entry["debriefed"] = today
    a["history"].append(track._event(clock, today, event="interview_debriefed", value=entry["on"]))
    track.save(root, applications)
    return {"application": a["id"], **entry}


def cancel(root, clock, ident, on):
    """An interview that was moved or called off: kept, marked cancelled, and no longer listed. Its
    calendar file is written again as the same event cancelled, so opening it takes the interview off
    the user's calendar. A moved one is then recorded again on its new day."""
    applications = track.load(root)
    a = track.find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    entry = next((e for e in a.get("upcoming", []) if e["on"][:10] == (on or "")[:10] and not e.get("cancelled")), None)
    if entry is None:
        raise Refused(f"there's no interview on {on} on that application")
    entry["cancelled"] = clock.today()
    a["history"].append(track._event(clock, clock.today(), event="interview_cancelled", value=entry["on"]))
    if entry.get("calendar"):
        entry["sequence"] = entry.get("sequence", 0) + 1
        with open(os.path.join(root, *entry["calendar"].split("/")), "w", encoding="utf-8", newline="") as f:
            f.write(calendar(a, entry, clock.tz, clock.now().astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                             cancel=True))
    track.save(root, applications)
    return {"application": a["id"], **entry}


def _when(entry, tz):
    start = _start(entry, tz)
    end_of_day = dt.datetime.fromisoformat(entry["on"][:10] + "T23:59")
    return start if start is not None else (end_of_day.replace(tzinfo=tz) if tz else end_of_day.astimezone())


def listing(root, clock, include_debriefed=False):
    """Every interview not yet gone through, soonest first, each with its application and files. Its
    number is the job's on the page: an application joined to a saved posting has the posting's."""
    tz = clock.tz
    now = clock.now()
    postings = store.Folder(root).load_postings()["postings"]
    out = []
    for a in track.load(root):
        for e in a.get("upcoming", []):
            if e.get("cancelled") or (e.get("debriefed") and not include_debriefed):
                continue
            when = _when(e, tz)
            prep = f"{folder_for(a)}/prep.md"
            num = postings.get(a.get("key") or "", {}).get("num") or a.get("num")
            out.append({"application": a["id"], "num": num, "company": a.get("company", ""),
                        "role": _clean(a.get("role", ""), 120), "status": a["status"], **e,
                        "time_unknown": "T" not in e["on"],
                        "days": (when.date() - now.date()).days, "past": when < now,
                        "prep": prep if os.path.exists(os.path.join(root, *prep.split("/"))) else ""})
    return sorted(out, key=lambda x: x["on"])


def soon(root, clock):
    """Interviews from now to SOON_DAYS days ahead."""
    return [x for x in listing(root, clock) if not x["past"] and x["days"] <= SOON_DAYS]


def debrief_due(root, clock):
    """Interviews held in the last DEBRIEF_DAYS days and not gone through yet."""
    return [x for x in listing(root, clock) if x["past"] and -x["days"] <= DEBRIEF_DAYS]


# ------------------------------------------------------------------ what the user will say


def _claims(section):
    return section.casefold().startswith(CLAIM_SECTIONS)


def parse(text_):
    """A prep sheet, story bank or quick reference as resume.check_items reads it: lines under a claim
    heading are "para" items, which must trace; everything else is a "note", which needn't."""
    items, section = [], ""
    for n, raw in enumerate(text_.splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        low = s.casefold()
        if low.startswith("tags:"):  # a story's skills, for finding it again: not a claim
            heads = [it for it in items if it["kind"] == "heading"]
            if heads:
                heads[-1]["tags"] = [x.strip().casefold() for x in s[5:].split(",") if x.strip()]
            continue
        if low.startswith(("from:", "flag:")):
            if not items or items[-1]["kind"] in ("heading",):
                raise BadFile(f"line {n}: a {low[:5]} line must come right under the line it is about")
            body = s[5:].strip()
            if low.startswith("from:"):
                items[-1]["from"].append(body)
            else:
                kind, _, detail = body.partition(":")
                items[-1]["flags"].append({"kind": kind.strip() or "claude", "detail": (detail or kind).strip(), "by": "claude"})
            continue
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            title = s.lstrip("#").strip()
            if level <= 2:
                section = title
            items.append({"kind": "heading", "text": title, "section": section, "line": n, "from": [], "flags": []})
            continue
        body = s[2:].strip() if s.startswith(("- ", "* ", "\u2022 ")) else s
        items.append({"kind": "para" if _claims(section) else "note", "text": body, "section": section, "line": n,
                      "from": [], "flags": []})
    return items


def check(root, path):
    """Every claim in a prep sheet, story bank, cheat sheet or quick reference, traced to about-me.md.
    A round's cheat sheet ("... cheat sheet.md") must also fit CHEAT_LINES lines. A company brief
    (company.md) has no claims about the user; each of its lines needs its source's link and a year.
    `ready` is all of it."""
    with open(path, encoding="utf-8-sig") as f:
        body = f.read()
    name = os.path.basename(path).casefold()
    parsed = parse(body)
    items = resume.check_items(parsed, resume.read_about(root))
    claims = [it for it in items if it["kind"] == "para"]
    kinds = {}
    for it in claims:
        for p in it["problems"]:
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    out = {"file": resume._rel(root, path), "lines": len(claims), "traced": sum(it["ok"] for it in claims),
           "flagged": sum(not it["ok"] for it in claims), "problems": kinds, "items": claims}
    ready = out["flagged"] == 0
    if name.endswith("cheat sheet.md"):
        n = sum(1 for line in body.splitlines() if line.strip() and not line.strip().casefold().startswith("from:"))
        out["length"] = {"lines": n, "max": CHEAT_LINES}
        ready = ready and n <= CHEAT_LINES
    if name == "company.md":
        unsourced = [n for n, line in enumerate(body.splitlines(), 1)
                     if line.strip().startswith(("- ", "* ")) and not (_SOURCED.search(line) and _DATED.search(line))]
        out["unsourced"] = unsourced
        ready = ready and not unsourced
    stories = [{"name": it["text"], "tags": it.get("tags", []), "line": it["line"]} for it in parsed
               if it["kind"] == "heading" and it["section"].casefold().startswith("stor") and it["text"] != it["section"]]
    if stories:
        out["stories"] = stories
    out["ready"] = ready
    return out


# ------------------------------------------------------------------ pay


def _pay(v):
    lo, hi = v.get("pay_low"), v.get("pay_high")
    if hi:
        return lo or hi, hi
    rng = text.salary_range(v.get("salary") or "")
    return rng if rng else None


def _quartiles(xs):
    """(lowest, lower quarter, middle, upper quarter, highest) by nearest rank."""
    xs = sorted(xs)

    def at(p):
        return xs[min(len(xs) - 1, max(0, round(p * (len(xs) - 1))))]
    return {"lowest": xs[0], "lower_quarter": at(0.25), "middle": at(0.5), "upper_quarter": at(0.75), "highest": xs[-1]}


def pay(root, ask=0):
    """What the user's saved postings state about pay: facts, never a prediction. Each posting's range
    as the scan read it ($ ranges only). With `ask`, how many ranges top out below it, and how many
    reach it."""
    postings = store.Folder(root).load_postings()["postings"]
    rows = [(k, v, _pay(v)) for k, v in postings.items()]
    rows = [(k, v, r) for k, v, r in rows if r]

    def summary(sel):
        if not sel:
            return {"with_pay": 0}
        tops, floors = [r[1] for _, _, r in sel], [r[0] for _, _, r in sel]
        out = {"with_pay": len(sel), "top": _quartiles(tops), "floor": _quartiles(floors)}
        if ask:
            out["tops_below_ask"] = sum(1 for t in tops if t < ask)
            out["tops_reaching_ask"] = sum(1 for t in tops if t >= ask)
            out["floors_at_or_above_ask"] = sum(1 for f in floors if f >= ask)
        return out

    wanted = [x for x in rows if x[1].get("status") in ("worth_applying", "applied", "your_call")]
    return {"postings": len(postings), "ask": ask, "all": summary(rows), "worth_a_look_or_applied": summary(wanted),
            "note": "Posted ranges only, as written in the postings. Not a prediction of an offer."}


def expect(root, clock, ident, purpose, asker="", who=""):
    """A round the user knows is coming, with no day yet."""
    if not (purpose or "").strip():
        raise Refused("say what the round is for, in the user's words")
    if asker and asker not in ASKERS:
        raise Refused(f"who's asking is one of {', '.join(ASKERS)}, not {asker!r}")
    applications = track.load(root)
    a = track.find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    a.setdefault("expected", []).append({"for": purpose.strip(), "asker": asker, "with": (who or "").strip(),
                                         "noted": clock.today()})
    a["history"].append(track._event(clock, clock.today(), event="round_expected", value=purpose.strip()))
    track.save(root, applications)
    return {"application": a["id"], "expected": a["expected"]}


def thanked(root, clock, ident, on="", contact="", none=False, channel="email"):
    """The thank-you after a round went out (to `contact`, a touch on their record), or the user said
    there'd be none."""
    from . import contacts
    applications = track.load(root)
    a = track.find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    today = clock.today()
    held = [e for e in a.get("upcoming", []) if not e.get("cancelled")
            and (e["on"][:10] == on[:10] if on else e["on"][:10] <= today)]
    if not held:
        raise Refused("there's no interview held on that application" + (f" on {on}" if on else " yet"))
    entry = held[-1]
    if none:
        key = "none"
    else:
        people = contacts.load(root)
        c = contacts.find(people, contact) if contact else None
        if c is None:
            raise Refused("name who it went to, as a contact (contact add), or say there'll be none with --none")
        key = c["id"]
        contacts.touch(root, clock, c["id"], channel=channel, direction="out",
                       note=f"thank-you after the {entry['on'][:10]} {entry.get('stage', 'interview')}", date=today)
    entry.setdefault("thanked", {})[key] = today
    track.save(root, applications)
    return {"application": a["id"], **entry}


def add_interviewer(root, clock, ident, on, contact_id):
    """A contact met in the round on `on`."""
    applications = track.load(root)
    a = track.find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    entry = next((e for e in a.get("upcoming", []) if e["on"][:10] == (on or "")[:10] and not e.get("cancelled")), None)
    if entry is None:
        raise Refused(f"there's no interview on {on} on that application")
    if contact_id not in entry.setdefault("interviewers", []):
        entry["interviewers"].append(contact_id)
    track.save(root, applications)
    return entry


def thanks_due(root, clock):
    """Rounds held in the last THANKS_DAYS days whose thank-you isn't recorded: who was met (with their
    email if the user gave one), and who hasn't been thanked."""
    from . import contacts
    people = {c["id"]: c for c in contacts.load(root)}
    out = []
    for x in listing(root, clock, include_debriefed=True):
        if not x["past"] or -x["days"] > THANKS_DAYS or "none" in (x.get("thanked") or {}):
            continue
        met = [people[i] for i in x.get("interviewers", []) if i in people]
        waiting = [c for c in met if c["id"] not in (x.get("thanked") or {})]
        if met and not waiting:
            continue
        if not met and x.get("thanked"):
            continue
        out.append({"application": x["application"], "num": x["num"], "company": x["company"], "on": x["on"],
                    "stage": x.get("stage", ""), "with": x.get("with", ""),
                    "to_thank": [{"id": c["id"], "name": c["name"], "title": c.get("title", ""),
                                  "email": c.get("email", "")} for c in waiting],
                    "nobody_recorded": not met})
    return out


def expected_rounds(root):
    """Rounds known to be coming with no day yet, on open applications."""
    out = []
    for a in track.load(root):
        if a["status"] not in ("applied", "replied", "screen", "interview", "offer"):
            continue
        for x in a.get("expected") or []:
            out.append({"application": a["id"], "company": a.get("company", ""), "role_title": _clean(a.get("role", ""), 120),
                        **x})
    return out
