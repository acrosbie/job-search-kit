"""Interviews: when they are, a calendar file for each, what's coming up and what needs a debrief, a
check that what the user plans to say traces to what they've confirmed, and the pay their saved
postings state.

An interview is kept on its application (applications.json), in `upcoming`:

    on         "YYYY-MM-DDTHH:MM" in the user's time zone, or a date alone
    kind       phone, video or onsite ("" if not said)
    with       who, in the user's words ("Dana, recruiter")
    minutes    how long (30 if not said)
    stage      screen or interview, the application's status it belongs to
    calendar   the .ics file written for it, under interviews/
    debriefed  the date the user went through how it went, or ""

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
DEBRIEF_DAYS = 14    # one held this recently, and not gone through, is offered a debrief
CLAIM_SECTIONS = ("opener", "answer", "stor", "gap", "strength", "caveat")

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


def calendar(a, entry, tz, stamp):
    """An .ics file's text for one interview: double-clicked, it opens in the user's calendar."""
    who = f" with {entry['with']}" if entry.get("with") else ""
    stage = {"screen": "screen", "interview": "interview"}.get(entry.get("stage"), "interview")
    summary = f"{a.get('company', '')}: {entry.get('kind') + ' ' if entry.get('kind') else ''}{stage}{who}"
    desc = f"{_clean(a.get('role', ''), 120)}. Prep: {folder_for(a)}/prep.md in your Job Search folder."
    uid = f"{re.sub(r'[^a-z0-9-]+', '-', a['id'].lower())}-{entry['on'].replace(':', '')}@job-search-kit"
    start = _start(entry, tz)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//job-search-kit//interview//EN", "CALSCALE:GREGORIAN",
             "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}"]
    if start is None:  # a date with no time: an all-day event
        day = dt.date.fromisoformat(entry["on"])
        lines += [f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + dt.timedelta(days=1):%Y%m%d}"]
    else:
        utc = start.astimezone(dt.timezone.utc)
        end = utc + dt.timedelta(minutes=entry.get("minutes") or 30)
        lines += [f"DTSTART:{utc:%Y%m%dT%H%M%SZ}", f"DTEND:{end:%Y%m%dT%H%M%SZ}"]
    lines += [f"SUMMARY:{_ics_text(summary)}", f"DESCRIPTION:{_ics_text(desc)}"]
    if entry.get("kind"):
        lines.append(f"LOCATION:{_ics_text({'phone': 'Phone', 'video': 'Video call', 'onsite': 'On site'}[entry['kind']])}")
    lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-PT30M", f"DESCRIPTION:{_ics_text(summary)}", "END:VALARM",
              "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"


def schedule(root, clock, ident, on, kind="", who="", minutes=0, status="", note=""):
    """Record an interview on its application, and write its calendar file. `status` (screen or
    interview) moves the application on, as `track` would. Saying it again for the same day updates
    that interview rather than adding a second."""
    on = parse_on(on)
    if kind and kind not in KINDS:
        raise Refused(f"the kind of interview is one of {', '.join(KINDS)}, not {kind!r}")
    if status and status not in ("screen", "interview"):
        raise Refused("an interview's stage is screen or interview")
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
    if entry is None:
        entry = {"on": on, "kind": "", "with": "", "minutes": 30, "stage": stage, "calendar": "", "debriefed": ""}
        entries.append(entry)
    entry.update({"on": on, "stage": stage})
    for field, value in (("kind", kind), ("with", (who or "").strip())):
        if value:
            entry[field] = value
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
    calendar file stays in the folder (the engine never deletes), so the user removes it from their
    calendar. A moved one is then recorded again on its new day."""
    applications = track.load(root)
    a = track.find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    entry = next((e for e in a.get("upcoming", []) if e["on"][:10] == (on or "")[:10] and not e.get("cancelled")), None)
    if entry is None:
        raise Refused(f"there's no interview on {on} on that application")
    entry["cancelled"] = clock.today()
    a["history"].append(track._event(clock, clock.today(), event="interview_cancelled", value=entry["on"]))
    track.save(root, applications)
    return {"application": a["id"], **entry}


def _when(entry, tz):
    start = _start(entry, tz)
    end_of_day = dt.datetime.fromisoformat(entry["on"][:10] + "T23:59")
    return start if start is not None else (end_of_day.replace(tzinfo=tz) if tz else end_of_day.astimezone())


def listing(root, clock):
    """Every interview not yet gone through, soonest first, each with its application and files."""
    tz = clock.tz
    now = clock.now()
    out = []
    for a in track.load(root):
        for e in a.get("upcoming", []):
            if e.get("debriefed") or e.get("cancelled"):
                continue
            when = _when(e, tz)
            prep = f"{folder_for(a)}/prep.md"
            out.append({"application": a["id"], "num": a.get("num"), "company": a.get("company", ""),
                        "role": _clean(a.get("role", ""), 120), "status": a["status"], **e,
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
    """Every claim in a prep sheet, story bank or quick reference, traced to about-me.md."""
    with open(path, encoding="utf-8-sig") as f:
        items = resume.check_items(parse(f.read()), resume.read_about(root))
    claims = [it for it in items if it["kind"] == "para"]
    kinds = {}
    for it in claims:
        for p in it["problems"]:
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    return {"file": resume._rel(root, path), "lines": len(claims), "traced": sum(it["ok"] for it in claims),
            "flagged": sum(not it["ok"] for it in claims), "problems": kinds,
            "items": [it for it in items if it["kind"] == "para"]}


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
