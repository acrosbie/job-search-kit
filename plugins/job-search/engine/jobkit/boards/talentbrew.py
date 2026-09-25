"""TalentBrew careers sites (verified on Intuit's, jobs.intuit.com). `/search-jobs/results`
returns JSON whose `results` field is the job list as HTML; the detail page carries the
description and the real places.

Two quirks. The query string must be sent in full: dropping the unused-looking parameters returns
an empty envelope rather than an error. And many list rows say "Multiple Locations", which the
detail page resolves into real cities. The same endpoint shape was tried on five other big
employers and none answered, so treat this as one site, not a family. Entries carry `host`.
"""

import re

from ..net import fetch, fetch_json
from ..text import html_to_text
from .common import make_record

_ITEM = re.compile(r"<li\s[^>]*data-job-id[^>]*>.*?</li>|<li\s[^>]*data-intuit-jobid[^>]*>.*?</li>", re.S | re.I)
_HREF = re.compile(r'href="(/job/[^"]+)"', re.I)
_JID = re.compile(r'data-(?:intuit-)?job-?id="(\d+)"', re.I)
_TITLE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S | re.I)
_LOC = re.compile(r'<span class="job-location">(.*?)</span>', re.S | re.I)
_DESC = re.compile(r'<div id="job-description-wrapper".*?(?:</section>|<div class="section9-content__left)', re.S | re.I)
_INFO = re.compile(r"job-description__job-info(.*?)</div>\s*</div>", re.S | re.I)
_INFO_LOC = re.compile(r"Location\s*\n(.+?)\n", re.I)

_PARAMS = ("ActiveFacetID=0&CurrentPage={page}&RecordsPerPage=100&Distance=50&RadiusUnitType=0"
           "&Keywords=&Location=&ShowRadius=False&IsPagination=False&CustomFacetName=&FacetTerm="
           "&FacetType=0&SearchResultsModuleName=Search+Results&SearchFiltersModuleName=Search+Filters"
           "&SortCriteria=0&SortDirection=0&SearchType=5&LocationType=0&OrganizationIds=&JobId=")


def read(company, ctx):
    host = company["host"]
    out, seen_ids, page = [], set(), 1
    while page <= 40:  # 4,000 roles
        data = fetch_json(f"https://{host}/search-jobs/results?{_PARAMS.format(page=page)}")
        items = _ITEM.findall(data.get("results") or "")
        if not items:
            break
        before = len(seen_ids)
        for it in items:
            jid = _JID.search(it)
            href = _HREF.search(it)
            title = _TITLE.search(it)
            if not (jid and href and title):
                continue
            if jid.group(1) in seen_ids:
                continue
            seen_ids.add(jid.group(1))
            url = f"https://{host}{href.group(1)}"
            loc = _LOC.search(it)
            loc = html_to_text(loc.group(1)).strip() if loc else ""

            def detail(url=url):
                page_html = fetch(url)
                m = _DESC.search(page_html)
                desc = html_to_text(m.group(0)) if m else ""
                info = _INFO.search(page_html)
                real = ""
                if info:
                    lm = _INFO_LOC.search(html_to_text(info.group(1)))
                    if lm:
                        real = lm.group(1).strip()
                return {"description": desc, "location": real, "posted": ""}

            out.append(make_record("talentbrew", company, jid.group(1), html_to_text(title.group(1)), loc,
                                   url, "", detail=detail))
        if len(seen_ids) == before:  # the site pages past the end by repeating the last page
            break
        page += 1
    return out
