"""Exports from the records.

The work-search log: many unemployment programs ask people to keep a record of each week's job-search
contacts (the employer, the date, how, and what came of it). Everything for it is already in the
applications, so it is written as a spreadsheet the user can copy into their state's own form. It
holds only what the user told Claude: nothing is filled in that they didn't say, and a date they only
knew roughly says so. Whether it meets a program's rules is for the user to check; the kit doesn't say.
"""

import csv
import datetime as dt
import os
import re

from . import track
from .errors import Refused

FOLDER = "exports"
COLUMNS = ("Date", "Employer", "Position", "Activity", "How", "Contact person", "Result so far", "Note")
HOW = {"company_site": "Online, on the company's website", "linkedin": "Online, through LinkedIn",
       "referral": "Through someone I know", "other": "Other"}
RESULT = {"applied": "Applied, waiting to hear", "replied": "They replied", "screen": "Screening call",
          "interview": "Interviewing", "offer": "Offer", "rejected": "Not selected", "presumed_rejected": "No reply",
          "withdrawn": "I withdrew", "closed": "The job was closed"}
INTERVIEW = {"phone": "Phone", "video": "Video call", "onsite": "In person"}


def _day(text, what):
    try:
        return dt.date.fromisoformat(text)
    except (TypeError, ValueError):
        raise Refused(f"give {what} as YYYY-MM-DD, not {text!r}") from None


# A role as imported may end in its places, "(United States; Remote)": not part of the position's name.
_PLACES = re.compile(r"\s*\((?:[^()]|\([^()]*\))*\b(?:remote|united states|usa|hybrid|on-?site|(?-i:[A-Z]{2}))\b"
                     r"(?:[^()]|\([^()]*\))*\)\s*$", re.I)


def position(role):
    return _PLACES.sub("", role or "").strip() or (role or "")


def worklog_rows(root, start, end, today):
    """Every job-search contact from `start` to `end` (dates, both included), oldest first. `today`, the
    user's date: an interview after it is booked, not yet held."""
    rows = []
    for a in track.load(root):
        base = {"Employer": a.get("company", ""), "Position": position(a.get("role", "")),
                "Result so far": RESULT.get(a["status"], a["status"])}
        how = HOW.get(a.get("channel") or "", "Not recorded")
        d = track._date(a.get("applied_date"))
        if d and start <= d <= end:
            rows.append({**base, "Date": d.isoformat(), "Activity": "Applied", "How": how,
                         "Contact person": a.get("contact", ""),
                         "Note": "The date is approximate" if a.get("applied_date_estimated") else ""})
        for h in a.get("history", []):
            hd = track._date(h.get("date"))
            if h.get("event") == "followed_up" and hd and start <= hd <= end:
                rows.append({**base, "Date": hd.isoformat(), "Activity": "Followed up", "How": "",
                             "Contact person": a.get("contact", ""), "Note": h.get("note", "")})
        for e in a.get("upcoming", []):
            ed = track._date(e.get("on"))
            if e.get("cancelled") or not ed or not start <= ed <= end:
                continue
            rows.append({**base, "Date": ed.isoformat(), "Activity": "Screen" if e.get("stage") == "screen" else "Interview",
                         "How": INTERVIEW.get(e.get("kind") or "", ""), "Contact person": e.get("with", ""),
                         "Note": "" if ed <= today else "Booked, not yet held"})
    rows.sort(key=lambda r: (r["Date"], r["Employer"], r["Activity"]))
    return rows


def worklog(root, clock, start, end):
    """Write exports/work-search <start> to <end>.csv, a spreadsheet of the contacts in that range."""
    s, e = _day(start, "--from"), _day(end, "--to")
    if e < s:
        raise Refused(f"--to ({end}) is before --from ({start})")
    rows = worklog_rows(root, s, e, dt.date.fromisoformat(clock.today()))
    rel = f"{FOLDER}/work-search {s.isoformat()} to {e.isoformat()}.csv"
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # With a byte order mark, so Excel opens it with names like "Zoë" intact.
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by[r["Activity"]] = by.get(r["Activity"], 0) + 1
    return {"file": rel, "from": s.isoformat(), "to": e.isoformat(), "rows": len(rows), "by_activity": by,
            "not_recorded": sum(1 for r in rows if r["How"] == "Not recorded"),
            "approximate_dates": sum(1 for r in rows if r["Note"] == "The date is approximate")}
