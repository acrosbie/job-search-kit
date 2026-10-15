"""Gem: the public job-board API. Descriptions come with the list. Found in real use (2026-10-15):
Retool's careers page moved its jobs to Gem (jobs.gem.com/retool)."""

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    token = company["token"]
    data = fetch_json(f"https://api.gem.com/job_board/v0/{token}/job_posts/")
    out = []
    for j in data if isinstance(data, list) else []:
        locs = [(j.get("location") or {}).get("name") or ""]
        for o in j.get("offices") or []:
            locs.append((o.get("location") or {}).get("name") or "")
        if j.get("location_type") == "remote":
            locs.append("Remote")
        location = "; ".join(dict.fromkeys(x for x in locs if x))
        desc = j.get("content_plain") or html_to_text(j.get("content", ""))
        out.append(make_record("gem", company, j["id"], j.get("title"), location, j.get("absolute_url"),
                               j.get("first_published_at") or j.get("updated_at"), description=desc))
    return out
