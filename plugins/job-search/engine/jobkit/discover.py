"""Which public job board a company uses: try its name against each hiring system the scanner reads,
and optionally read its careers page (or a board's own address) for an embedded board. A result is a
lead, not a fact: each board found comes with four of its titles, to read before adding it, because
the same name can belong to a different company.

Found in real use (2026-10-14): nothing was found for NVIDIA (Workday, which the scanner reads), Retool
(moved to Gem), Mistral AI (an Ashby board named "mistral.ai"), Deel, Etsy, Gladly or Chewy, and a
network that refused every request looked the same as a company with no board.
"""

import re
import urllib.error

from . import net
from .net import fetch, fetch_json

_PAGE_TOKENS = [
    ("greenhouse", re.compile(r"(?:job-boards|boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-z0-9][a-z0-9.\-]*[a-z0-9])", re.I)),
    ("ashby", re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([a-z0-9][a-z0-9.\-]*[a-z0-9])", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([a-z0-9\-]+)", re.I)),
    ("smartrecruiters", re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9]+)")),
    ("rippling", re.compile(r"ats\.rippling\.com/([a-z0-9\-]+)", re.I)),
    ("gem", re.compile(r"(?:jobs\.gem\.com|api\.gem\.com/job_board/v0)/([a-z0-9\-]+)", re.I)),
]
# host, tenant (the subdomain) and site, with the optional language part ("/en-US/") skipped.
_WORKDAY = re.compile(r"([a-z0-9\-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:wday/cxs/[a-z0-9\-]+/)?(?:[a-z]{2}-[A-Z]{2}/)?"
                      r"([A-Za-z0-9_\-]+)")
_PAGE_HINTS = re.compile(r"icims|phenom|eightfold|successfactors|taleo|oraclecloud|jobvite|workable|bamboohr|recruitee|"
                         r"teamtailor|breezy", re.I)

# Where Workday tenants live, and what their sites are called, most common first: measured on the 28
# Workday boards a real search reads (2026-10-15). Site names don't care about case.
WD_HOSTS = (5, 1, 12, 3, 10, 103, 501, 503, 108, 115, 2, 4)
WD_SITES = ("{t}", "{t}_careers", "{t}careers", "careers", "external", "external_career_site", "{t}externalcareersite",
            "{t}_external", "{t}_external_careers", "externalcareers", "{t}externalcareers", "external_careers",
            "{t}jobs", "jobs", "search", "global_external_site", "ext")
SAMPLE = 4


def _titles(items, key="title"):
    return [x.get(key) or "" for x in items if isinstance(x, dict)][:SAMPLE]


def _greenhouse(s):
    jobs = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs").get("jobs") or []
    return len(jobs), _titles(jobs)


def _ashby(s):
    jobs = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{s}").get("jobs") or []
    return len(jobs), _titles(jobs)


def _lever(s):
    jobs = fetch_json(f"https://api.lever.co/v0/postings/{s}?mode=json")
    jobs = jobs if isinstance(jobs, list) else []
    return len(jobs), _titles(jobs, "text")


def _smartrecruiters(s):
    d = fetch_json(f"https://api.smartrecruiters.com/v1/companies/{s}/postings?limit={SAMPLE}")
    return d.get("totalFound", 0), _titles(d.get("content") or [], "name")


def _rippling(s):
    d = fetch_json(f"https://api.rippling.com/platform/api/ats/v1/board/{s}/jobs")
    jobs = d if isinstance(d, list) else d.get("items", [])
    return len(jobs), _titles(jobs, "name")


def _gem(s):
    d = fetch_json(f"https://api.gem.com/job_board/v0/{s}/job_posts/")
    jobs = d if isinstance(d, list) else []
    return len(jobs), _titles(jobs)


CHECKS = [("greenhouse", _greenhouse), ("ashby", _ashby), ("lever", _lever), ("smartrecruiters", _smartrecruiters),
          ("rippling", _rippling), ("gem", _gem)]


def _workday_jobs(host, tenant, site):
    d = fetch_json(f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
                   data={"appliedFacets": {}, "limit": SAMPLE, "offset": 0, "searchText": ""},
                   headers={"Accept": "application/json"})
    return d.get("total", 0), _titles(d.get("jobPostings") or [])


def _workday_guess(tenant, notes):
    """Find the tenant's host (a wrong one answers 422, the right one 404 for a site it hasn't), then
    its site among the common names."""
    host = ""
    for n in WD_HOSTS:
        h = f"{tenant}.wd{n}.myworkdayjobs.com"
        try:
            _workday_jobs(h, tenant, "no-such-site-x")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                host = h
                break
        except Exception as e:
            notes.append(e)
            return None
    if not host:
        return None
    for s in WD_SITES:
        site = s.format(t=tenant)
        try:
            n, titles = _workday_jobs(host, tenant, site)
        except Exception:
            continue
        if n:
            return {"ats": "workday", "host": host, "tenant": tenant, "site": site, "jobs": n, "titles": titles}
    return {"ats": "workday", "host": host, "tenant": tenant, "site": "", "jobs": 0, "titles": [],
            "note": "the company is on Workday here, but its site's name isn't a common one: find it in a job link "
                    "on their careers page (the part after myworkdayjobs.com/) and give that link"}


def _variants(name):
    low = name.strip().lower()
    words = re.sub(r"\s*\(.*?\)\s*", " ", low).strip()  # "grammarly (superhuman)" is grammarly too
    out = [name.strip(), low, name.strip().capitalize(), low.replace("-", ""), re.sub(r"[^a-z0-9]+", "", low),
           re.sub(r"[^a-z0-9]+", "-", low).strip("-"), re.sub(r"[^a-z0-9]+", "", words), words.split(" ")[0],
           re.sub(r"[^a-z0-9.]+", "", low)]
    return list(dict.fromkeys(v for v in out if v and " " not in v))


def discover(slug, page=None):
    """{"boards": [{ats, token or host/tenant/site, jobs, titles}], "embedded": [...], "unsupported": [names],
    "page_error": str, "blocked": bool}"""
    variants = _variants(slug)
    found = {"boards": [], "embedded": [], "unsupported": [], "page_error": "", "blocked": False}
    attempts, blocks = 0, 0
    for ats, count in CHECKS:
        for v in variants:
            attempts += 1
            try:
                n, titles = count(v)
            except Exception as e:
                blocks += net.is_network_block(net.failure_kind(e))
                continue
            if n:  # an empty board counts as not found: some systems answer for any name
                found["boards"].append({"ats": ats, "token": v, "jobs": n, "titles": titles})
                break
    if attempts and blocks == attempts:
        found["blocked"] = True  # nothing answered: say the network refused, not that there's no board
        return found
    if not found["boards"]:
        notes = []
        tenant = re.sub(r"[^a-z0-9]+", "", re.sub(r"\s*\(.*?\)\s*", " ", slug.lower()))
        wd = _workday_guess(tenant, notes) if tenant else None
        if wd:
            found["boards"].append(wd)
    if page:
        try:
            text = fetch(page) if not _WORKDAY.search(page) else ""
        except Exception as e:
            text = ""
            found["page_error"] = f"{type(e).__name__}: {e}"
        text = page + "\n" + text  # a board's own address counts as a page that names it
        seen = set()
        for ats, rx in _PAGE_TOKENS:
            for tok in rx.findall(text):
                if (ats, tok.lower()) in seen:
                    continue
                seen.add((ats, tok.lower()))
                lead = {"ats": ats, "token": tok}
                try:
                    lead["jobs"], lead["titles"] = dict(CHECKS)[ats](tok)
                except Exception as e:
                    lead["jobs"], lead["error"] = 0, f"{type(e).__name__}: {e}"
                found["embedded"].append(lead)
        for host_tenant, wdn, site in _WORKDAY.findall(text):
            host = f"{host_tenant}.{wdn}.myworkdayjobs.com"
            if ("workday", host) in seen:
                continue
            seen.add(("workday", host))
            lead = {"ats": "workday", "host": host, "tenant": host_tenant, "site": site}
            try:
                lead["jobs"], lead["titles"] = _workday_jobs(host, host_tenant, site)
            except Exception as e:
                lead["jobs"], lead["error"] = 0, f"{type(e).__name__}: {e}"
            found["embedded"].append(lead)
        found["unsupported"] = sorted({h.lower() for h in _PAGE_HINTS.findall(text)})
    return found
