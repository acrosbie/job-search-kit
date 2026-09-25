"""The /api/jobs?page&limit shape some careers sites serve (verified on GitHub's and DocuSign's):
jobs[].data with title, location_name, apply_url, posted_date and the description inline.
Entries carry `host` instead of `token`. Keys use the system name "careers-api"."""

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    host = company["host"]
    out, page, total = [], 1, None
    while True:
        data = fetch_json(f"https://{host}/api/jobs?page={page}&limit=100")
        jobs = data.get("jobs") or []
        if not jobs:
            break
        total = data.get("totalCount", total)
        for j in jobs:
            x = j.get("data") or j
            locs = [x.get("location_name") or "", x.get("full_location") or ""]
            more = x.get("multipleLocations")  # a bool on these hosts; a list is handled in case another host sends one
            for m in more if isinstance(more, list) else []:
                locs.append(m if isinstance(m, str) else (m.get("location_name") or m.get("name") or ""))
            location = "; ".join(dict.fromkeys(loc for loc in locs if loc))
            desc = "\n\n".join(html_to_text(x.get(k, "")) for k in ("description", "responsibilities", "qualifications") if x.get(k))
            url = x.get("apply_url") or f"https://{host}/jobs/{x.get('slug', '')}"
            out.append(make_record("careers-api", company, x.get("req_id") or x.get("slug"), x.get("title"), location, url,
                                   x.get("posted_date") or x.get("create_date") or "", description=desc))
        page += 1
        if total is not None and len(out) >= total:
            break
    return out
