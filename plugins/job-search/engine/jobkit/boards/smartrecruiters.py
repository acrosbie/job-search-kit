"""SmartRecruiters: the public postings API, 100 a page. Descriptions are a second call."""

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    token = company["token"]
    base = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    out, offset, total = [], 0, None
    while total is None or offset < total:
        data = fetch_json(f"{base}?limit=100&offset={offset}")
        total = data.get("totalFound", 0)
        items = data.get("content", [])
        if not items:
            break
        for j in items:
            loc = j.get("location") or {}
            # SmartRecruiters gives a lowercase ISO country code ("in", "ca"), which collides with US state codes.
            country = (loc.get("country") or "").strip()
            country = "United States" if country.lower() == "us" else (f"non-US ({country.lower()})" if country else "")
            location = ", ".join(x for x in [loc.get("city"), loc.get("region"), country] if x)
            if loc.get("remote"):
                location += "; Remote"
            jid = j["id"]

            def detail(jid=jid):
                d = fetch_json(f"{base}/{jid}")
                secs = (d.get("jobAd") or {}).get("sections") or {}
                return "\n\n".join(html_to_text(secs[k].get("text", "")) for k in
                                   ("companyDescription", "jobDescription", "qualifications", "additionalInformation")
                                   if k in secs)

            out.append(make_record("smartrecruiters", company, jid, j.get("name"), location,
                                   f"https://jobs.smartrecruiters.com/{token}/{jid}", j.get("releasedDate"), detail=detail))
        offset += len(items)
    return out
