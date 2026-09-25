"""Workday: the careers site's own job-list endpoint.

Its text search is an OR over words with junk ranked first, so it isn't used. Instead every posting
is paged through, 20 at a time, narrowed by a country facet when the tenant has one matching
settings.toml [workday] country_facet, and capped at [workday] max_total. Entries in
companies.toml carry host, tenant and site instead of a token.
"""

import re

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    host, tenant, site = company["host"], company["tenant"], company["site"]
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    hdrs = {"Accept": "application/json"}
    cap = ctx.workday["max_total"]
    country_re = re.compile(ctx.workday["country_facet"], re.I)

    def page(offset, facets):
        return fetch_json(f"{base}/jobs", data={"appliedFacets": facets, "limit": 20, "offset": offset, "searchText": ""},
                          headers=hdrs)

    first = page(0, {})
    facets = {}
    for f in first.get("facets", []):
        for v in f.get("values", []):
            if country_re.search(v.get("descriptor", "")):
                facets = {f["facetParameter"]: [v["id"]]}
                break
        if facets:
            break
    data = page(0, facets) if facets else first
    total = data.get("total", 0)  # only the first page reports total; later pages say 0

    seen, out, offset = set(), [], 0
    while True:
        items = data.get("jobPostings", [])
        if not items:
            break
        for j in items:
            path = j.get("externalPath", "")
            bullets = j.get("bulletFields") or []
            jid = bullets[0] if bullets else (path.rstrip("/").split("/")[-1] or path)
            if jid in seen:
                continue
            seen.add(jid)

            def detail(path=path):
                d = fetch_json(f"{base}{path}", headers=hdrs)
                info = d.get("jobPostingInfo") or {}
                locs = [info.get("location") or ""] + list(info.get("additionalLocations") or [])
                if info.get("remoteType"):
                    locs.append(str(info["remoteType"]))
                return {"description": html_to_text(info.get("jobDescription", "")),
                        "location": "; ".join(x for x in locs if x)}

            # The list view says "3 Locations" instead of naming them. Treat that as unknown so the
            # record survives the location filter; detail() fills in the real names.
            loc = j.get("locationsText") or ""
            if re.fullmatch(r"\d+ locations", loc.strip(), re.I):
                loc = ""
            posted = re.sub(r"^posted\s+", "", j.get("postedOn") or "", flags=re.I)
            out.append(make_record("workday", company, jid, j.get("title"), loc,
                                   f"https://{host}/{site}{path}", posted, detail=detail))
        offset += len(items)
        if offset >= min(total, cap):
            break
        data = page(offset, facets)
    return out
