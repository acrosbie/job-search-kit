"""Himalayas (himalayas.app), a remote-jobs aggregator with an official, keyless search API
(himalayas.app/docs/remote-jobs-api) that returns the full description, pay and location limits.
Remote roles only. The companies.toml entry carries `queries`.

Two differences from a company board. Jobs arrive from many companies, so a company already read
from its own board is skipped here and keeps coming from there. And a search page isn't a whole
board, so a posting missing from one run hasn't necessarily closed: gone-marking works by
system-and-company key prefix, which these keys never share with the source. Their terms ask for
a visible link back when the data is shown, so every record's url is its himalayas.app page.
"""

import datetime as dt
import re
import urllib.error
import urllib.parse

from ..net import fetch_json, pause
from ..text import html_to_text
from .common import make_record

# Each phrase is read newest first, page by page, until the jobs are older than the last good read
# (with OVERLAP days to spare), or FIRST_DAYS back the first time. Searches match loosely, so a broad
# phrase can list thousands: MAX_PAGES (20 jobs a page) stops one that keeps going. Read by relevance,
# as before 0.12, five pages missed most of what was new, and a short page was taken for the last.
MAX_PAGES = 25
OVERLAP = 1
FIRST_DAYS = 14


def _since(company, ctx):
    today = dt.date.fromisoformat(ctx.today) if ctx.today else dt.datetime.now(dt.timezone.utc).date()
    try:
        last = dt.date.fromisoformat((ctx.last_ok.get(company.get("slug", "")) or "")[:10])
        return last - dt.timedelta(days=OVERLAP)
    except ValueError:
        return today - dt.timedelta(days=FIRST_DAYS)


def read(company, ctx):
    out, got = [], set()
    since = _since(company, ctx)
    for q in company.get("queries") or []:
        for page in range(1, MAX_PAGES + 1):
            url = "https://himalayas.app/jobs/api/search?" + urllib.parse.urlencode(
                {"q": q, "country": "United States", "sort": "recent", "page": page})
            try:
                data = fetch_json(url)
            except urllib.error.HTTPError as e:
                if e.code == 429 and out:  # rate-limited part way: keep what arrived, the next run catches up
                    return out
                raise
            jobs = data.get("jobs") or []
            older = False
            for j in jobs:
                pub = str(j.get("pubDate") or "")
                if pub.isdigit() and dt.datetime.fromtimestamp(int(pub), dt.timezone.utc).date() < since:
                    older = True  # what's left of this phrase, the last good read already saw
                    continue
                co = j.get("companyName") or ""
                if re.sub(r"[^a-z0-9]", "", co.lower()) in ctx.watched:
                    continue
                link = j.get("guid") or j.get("applicationLink") or ""
                jid = link.rstrip("/").rsplit("/", 1)[-1]
                cslug = j.get("companySlug") or co
                if not jid or (cslug, jid) in got:
                    continue
                got.add((cslug, jid))
                locs = [x for x in (j.get("locationRestrictions") or []) if isinstance(x, str)]
                desc = html_to_text(j.get("description") or "") or (j.get("excerpt") or "")
                lo, hi = j.get("minSalary"), j.get("maxSalary")
                if lo and hi and (j.get("currency") or "USD") == "USD" and j.get("salaryPeriod") in (None, "annual", "year", "yearly"):
                    desc = f"Compensation: ${int(lo):,} - ${int(hi):,}" + chr(10) + chr(10) + desc
                pub = str(j.get("pubDate") or "")
                posted = dt.datetime.fromtimestamp(int(pub), dt.timezone.utc).date().isoformat() if pub.isdigit() else ""
                out.append(make_record("himalayas", {"name": co, "slug": cslug}, jid, j.get("title"),
                                       "; ".join(locs + ["Remote"]), link, posted, description=desc))
            # A page can hold fewer than 20 with hundreds still to come, so the end is the total it reports.
            if not jobs or older or page * (data.get("limit") or 20) >= (data.get("totalCount") or 0):
                break
            if page == MAX_PAGES:
                ctx.partial.add(company.get("slug", ""))  # stopped with more to read; the next run starts newest first again
            pause(0.5)
    return out
