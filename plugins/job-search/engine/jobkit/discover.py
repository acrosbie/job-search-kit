"""Which public job board a company uses: try its name against each hiring system, and optionally
read its careers page for an embedded board. A result is a lead, not a fact: read four of the
board's titles before adding it, because the same token can belong to a different company."""

import re

from .net import fetch, fetch_json

_PAGE_TOKENS = [
    ("greenhouse", re.compile(r"(?:job-boards|boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-z0-9]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-z0-9\-]+)", re.I)),
    ("ashby", re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([a-z0-9\-]+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([a-z0-9\-]+)", re.I)),
    ("smartrecruiters", re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([A-Za-z0-9]+)")),
    ("workday", re.compile(r"([a-z0-9]+\.wd\d+\.myworkdayjobs\.com/[A-Za-z0-9_\-]+)")),
    ("rippling", re.compile(r"ats\.rippling\.com/([a-z0-9\-]+)", re.I)),
]
_PAGE_HINTS = re.compile(r"icims|phenom|eightfold|successfactors|taleo|oraclecloud|jobvite|workable|bamboohr|recruitee|teamtailor|breezy", re.I)


def _smartrecruiters(s):
    return fetch_json(f"https://api.smartrecruiters.com/v1/companies/{s}/postings?limit=1").get("totalFound", 0)


def _rippling(s):
    d = fetch_json(f"https://api.rippling.com/platform/api/ats/v1/board/{s}/jobs")
    return len(d if isinstance(d, list) else d.get("items", []))


CHECKS = [
    ("greenhouse", lambda s: len(fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs").get("jobs"))),
    ("ashby", lambda s: len(fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{s}").get("jobs"))),
    ("lever", lambda s: len(fetch_json(f"https://api.lever.co/v0/postings/{s}?mode=json"))),
    ("smartrecruiters", _smartrecruiters),
    ("rippling", _rippling),
]


def discover(slug, page=None):
    """{"boards": [{ats, token, jobs}], "embedded": [{ats, token}], "unsupported": [names], "page_error": str}"""
    variants = list(dict.fromkeys([slug, slug.lower(), slug.capitalize(), slug.replace("-", "")]))
    found = {"boards": [], "embedded": [], "unsupported": [], "page_error": ""}
    for ats, count in CHECKS:
        for v in variants:
            try:
                n = count(v)
            except Exception:
                continue
            if n:  # an empty board counts as not found: some systems answer for any name
                found["boards"].append({"ats": ats, "token": v, "jobs": n})
                break
    if page:
        try:
            text = fetch(page)
        except Exception as e:
            text = ""
            found["page_error"] = f"{type(e).__name__}: {e}"
        seen = set()
        for ats, rx in _PAGE_TOKENS:
            for tok in rx.findall(text):
                if (ats, tok) not in seen:
                    seen.add((ats, tok))
                    found["embedded"].append({"ats": ats, "token": tok})
        found["unsupported"] = sorted({h.lower() for h in _PAGE_HINTS.findall(text)})
    return found
