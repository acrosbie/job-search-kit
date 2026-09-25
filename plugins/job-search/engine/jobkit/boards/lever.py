"""Lever: the public postings API. Descriptions come with the list."""

import datetime as dt

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    token = company["token"]
    data = fetch_json(f"https://api.lever.co/v0/postings/{token}?mode=json")
    out = []
    for j in data:
        cats = j.get("categories") or {}
        locs = [cats.get("location") or ""] + list(cats.get("allLocations") or [])
        if j.get("workplaceType"):
            locs.append(j["workplaceType"])
        location = "; ".join(dict.fromkeys(x for x in locs if x))
        parts = [j.get("descriptionPlain") or html_to_text(j.get("description", ""))]
        for lst in j.get("lists") or []:
            parts.append(f"\n{lst.get('text', '')}\n{html_to_text(lst.get('content', ''))}")
        parts.append(j.get("additionalPlain") or "")
        posted = j.get("createdAt")
        if isinstance(posted, (int, float)):
            posted = dt.datetime.fromtimestamp(posted / 1000, dt.timezone.utc).date().isoformat()
        out.append(make_record("lever", company, j["id"], j.get("text"), location, j.get("hostedUrl"),
                               posted, description="\n".join(p for p in parts if p)))
    return out
