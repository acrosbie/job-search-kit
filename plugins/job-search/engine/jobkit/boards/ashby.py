"""Ashby: the public posting API. Descriptions come with the list; pay is a separate field."""

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    token = company["token"]
    data = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true")
    out = []
    for j in data.get("jobs", []):
        comp = (j.get("compensation") or {}).get("scrapeableCompensationSalarySummary") or ""
        locs = [j.get("location") or ""]
        for s in j.get("secondaryLocations") or []:
            locs.append(s.get("location") or "")
        if j.get("isRemote"):
            locs.append("Remote")
        location = "; ".join(dict.fromkeys(x for x in locs if x))
        desc = j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", ""))
        if comp:  # Ashby keeps pay outside the description; put it where the pay parser will find it
            desc = f"Compensation: {comp}" + chr(10) + chr(10) + desc
        out.append(make_record("ashby", company, j["id"], j.get("title"), location, j.get("jobUrl"),
                               j.get("publishedAt"), description=desc))
    return out
