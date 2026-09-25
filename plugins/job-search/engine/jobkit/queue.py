"""The triage queue: postings waiting for a verdict, with the facts the cooldown rule needs.

The rule is "one application per company per [triage] cooldown_days" (30 by default). Rather than
leave Claude to work that out from two files, each queued posting carries the recent applications
to its company and the other postings from that company waiting in the same queue.
"""

import datetime as dt

from . import settings, store


def _date(s):
    try:
        return dt.date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def recent_applications(company, applications, postings, today, days):
    """Applications to `company` within `days` of `today`: from applications.json (applied_date),
    and postings the user marked applied (their triaged date). An application whose date isn't
    known is listed with "date_known": false, so Claude can weigh it rather than miss it."""
    name = company.casefold()
    found = []
    for a in applications:
        if a.get("company", "").casefold() != name:
            continue
        d = _date(a.get("applied_date"))
        if d is None:
            found.append({"role": a.get("role", ""), "applied": a.get("applied", ""), "date_known": False})
        elif 0 <= (today - d).days <= days:
            found.append({"role": a.get("role", ""), "applied": d.isoformat(), "date_known": True,
                          "estimated": bool(a.get("applied_date_estimated"))})
    for k, v in postings.items():
        if v.get("status") == "applied" and v.get("company", "").casefold() == name:
            d = _date(v.get("triaged"))
            if d and 0 <= (today - d).days <= days and not any(f["role"] == v["title"] for f in found):
                found.append({"role": v["title"], "applied": d.isoformat(), "date_known": True, "key": k})
    return found


def queue(root, clock):
    s = settings.load(root)
    folder = store.Folder(root)
    postings = folder.load_postings()["postings"]
    applications = folder.load_applications()
    today = dt.date.fromisoformat(clock.today())
    waiting = sorted(((k, v) for k, v in postings.items() if v.get("status") == "new"),
                     key=lambda kv: (kv[1].get("company", "").casefold(), kv[1].get("title", "")))
    by_company = {}
    for k, v in waiting:
        by_company.setdefault(v.get("company", "").casefold(), []).append(k)
    out = []
    for k, v in waiting:
        out.append({
            "key": k,
            "company": v.get("company", ""),
            "title": v.get("title", ""),
            "location": v.get("location", ""),
            "flag": v.get("flag", ""),
            "salary": v.get("salary", ""),
            "url": v.get("url", ""),
            "first_seen": v.get("first_seen", ""),
            "gone": v.get("gone", ""),
            "description_file": f"data/postings/{v.get('file') or k + '.md'}",
            "applied_recently_at_company": recent_applications(v.get("company", ""), applications, postings,
                                                               today, s.cooldown_days),
            "same_company_in_queue": [x for x in by_company[v.get("company", "").casefold()] if x != k],
        })
    return {"count": len(out), "cooldown_days": s.cooldown_days, "today": today.isoformat(), "postings": out}
