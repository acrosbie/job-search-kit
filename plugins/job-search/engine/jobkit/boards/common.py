"""What every board reader shares: the record shape, and the context a scan passes in."""

import re
from dataclasses import dataclass, field


@dataclass
class Context:
    """Settings a reader may need. `workday` is settings.toml [workday]; `watched` holds the
    normalised names of companies read from their own boards, which an aggregator skips."""
    workday: dict = field(default_factory=lambda: {"country_facet": "", "max_total": 2000})
    watched: set = field(default_factory=set)


def watched_names(companies):
    return {re.sub(r"[^a-z0-9]", "", c["name"].lower()) for c in companies if c.get("ats") != "himalayas"}


def make_record(system, company, jid, title, location, url, posted, description=None, detail=None):
    """One posting as a reader returns it. The key, <system>-<company slug>-<job id>, is what ties
    saved postings, verdicts and applications together, so its format never changes.
    `detail` fetches the description lazily, only for titles that pass the filter."""
    slug = re.sub(r"[^a-z0-9]+", "-", company["slug"].lower()).strip("-")
    return {
        "key": f"{system}-{slug}-{jid}",
        "ats": system,
        "company": company["name"],
        "title": re.sub(r"[  \s]+", " ", title or "").strip(),
        "location": (location or "").strip(),
        "url": url or "",
        "posted": posted[:10] if re.match(r"\d{4}-\d{2}-\d{2}", posted or "") else (posted or ""),
        "description": description,
        "detail": detail,
    }
