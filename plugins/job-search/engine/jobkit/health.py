"""Scan health: boards to mention after a scan, and in the weekly review.

    failing   failed this many scans in a row; worth looking for the company's board again (discover)
    silent    answered, but listed no jobs at all for 30 days; the company may have moved boards
    at_cap    a Workday board that hit [workday] max_total, so some of its jobs weren't read
"""

import datetime as dt

FAILS_IN_A_ROW = 3
SILENT_DAYS = 30


def _date(s):
    try:
        return dt.date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def boards(state_boards, companies, s, today):
    names = {c["slug"]: c.get("name", c["slug"]) for c in companies}
    t = dt.date.fromisoformat(today)
    out = {"failing": [], "silent": [], "at_cap": []}
    for slug, b in sorted(state_boards.items()):
        name = names.get(slug, slug)
        if b.get("fails", 0) >= FAILS_IN_A_ROW:
            out["failing"].append({"board": name, "slug": slug, "fails": b["fails"], "error": b.get("error", "")})
        since = _date(b.get("last_listed")) or _date(b.get("first_read"))
        if not b.get("error") and b.get("jobs") == 0 and since and (t - since).days >= SILENT_DAYS:
            out["silent"].append({"board": name, "slug": slug, "since": since.isoformat()})
        if b.get("ats") == "workday" and isinstance(b.get("jobs"), int) and b["jobs"] >= s.workday["max_total"]:
            out["at_cap"].append({"board": name, "slug": slug, "jobs": b["jobs"]})
    return out
