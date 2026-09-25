"""Atlassian's careers endpoint: one call, every posting with its description inline."""

import re

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    data = fetch_json("https://www.atlassian.com/endpoint/careers/listings")
    out = []
    for j in data:
        locs = j.get("locations") or []
        location = "; ".join(dict.fromkeys(x for x in locs if x)) if isinstance(locs, list) else str(locs)
        desc = "\n\n".join(html_to_text(j.get(k, "")) for k in ("overview", "responsibilities", "qualifications", "compensation") if j.get(k))
        posted = (j.get("portalJobPost") or {}).get("updatedDate") or ""
        m = re.match(r"(\d{4}-\d{2}-\d{2})", posted)
        out.append(make_record("atlassian", company, j.get("id"), j.get("title"), location, j.get("applyUrl"),
                               m.group(1) if m else "", description=desc))
    return out
