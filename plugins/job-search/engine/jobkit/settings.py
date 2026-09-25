"""The user's settings (profile/settings.toml) and watched companies (profile/companies.toml).

Setup writes both from the user's answers, and Claude changes them through the tune skill; the
user never edits them. Every pattern is a case-insensitive regular expression. A missing or empty
pattern matches nothing, so a half-written file can't wave every job through.

    [you]          timezone
    [titles]       function, level, exclude: a title needs a function word AND a level word, and no exclusion
    [places]       remote, hybrid_ok, remote_only, in_country, country_wide, abroad (tested on the listed location)
    [description]  remote_language, contract, onsite_days, onsite_place (tested on the description)
    [[phrase_rejects]]  name, phrases, min_distinct, same_as, reason: reject when enough distinct phrases appear
    [pay]          reject_if_top_below (0 turns it off)
    [workday]      country_facet, max_total
    [labels]       wording for every flag and reason (defaults below)
"""

import os
import re
from dataclasses import dataclass, field

from .toml import load_file

# Plain words for someone who has never seen the rules. {placeholders} are filled in per posting.
DEFAULT_LABELS = {
    "flag_in_country": "outside your area, check it's remote",
    "flag_remote_only": "near you, but only if it's remote",
    "flag_country_wide": "in the country, no city named",
    "flag_unknown": "location not stated",
    "flag_contract": "contract or temporary ({phrase})",
    "flag_onsite": 'in the office 4 or 5 days a week ("{quote}")',
    "flag_applied": "you already applied here on {applied}",
    "reason_in_country": "Not a fit: it's in {location}, outside where you'd commute, and the posting doesn't say it's remote.",
    "reason_remote_only": "Not a fit: {location} only works for you if the job is remote, and the posting doesn't say it is.",
    "reason_phrase": "Not a fit: the posting talks about {hits}, which you said to avoid.",
    "reason_pay": "Not a fit: the posted pay tops out at ${top_k}K (${low_k}K to ${top_k}K), below your ${line_k}K line.",
}


def _rx(pattern):
    return re.compile(pattern, re.I) if pattern else None


@dataclass
class PhraseReject:
    name: str
    phrases: object          # compiled pattern, or None
    min_distinct: int = 2
    same_as: dict = field(default_factory=dict)
    reason: str = ""


@dataclass
class Settings:
    raw: dict
    timezone: str
    function: object
    level: object
    exclude: object
    remote: object
    hybrid_ok: object
    remote_only: object
    in_country: object
    country_wide: object
    abroad: object
    remote_language: object
    contract: object
    onsite_days: object
    onsite_place: object
    phrase_rejects: list
    pay_top_below: int
    workday: dict
    labels: dict

    def label(self, name, **values):
        return self.labels[name].format(**values)


def parse(raw):
    t, p, d = raw.get("titles", {}), raw.get("places", {}), raw.get("description", {})
    rejects = [PhraseReject(name=r.get("name", "phrases"), phrases=_rx(r.get("phrases", "")),
                            min_distinct=int(r.get("min_distinct", 2)), same_as=dict(r.get("same_as", {})),
                            reason=r.get("reason", ""))
               for r in raw.get("phrase_rejects", [])]
    wd = raw.get("workday", {})
    return Settings(
        raw=raw,
        timezone=raw.get("you", {}).get("timezone", ""),
        function=_rx(t.get("function")), level=_rx(t.get("level")), exclude=_rx(t.get("exclude")),
        remote=_rx(p.get("remote")), hybrid_ok=_rx(p.get("hybrid_ok")), remote_only=_rx(p.get("remote_only")),
        in_country=_rx(p.get("in_country")), country_wide=_rx(p.get("country_wide")), abroad=_rx(p.get("abroad")),
        remote_language=_rx(d.get("remote_language")), contract=_rx(d.get("contract")),
        onsite_days=_rx(d.get("onsite_days")), onsite_place=_rx(d.get("onsite_place")),
        phrase_rejects=rejects,
        pay_top_below=int(raw.get("pay", {}).get("reject_if_top_below", 0)),
        workday={"country_facet": wd.get("country_facet", ""), "max_total": int(wd.get("max_total", 2000))},
        labels={**DEFAULT_LABELS, **raw.get("labels", {})},
    )


def load(folder):
    return parse(load_file(os.path.join(folder, "profile", "settings.toml")))


def load_companies(folder):
    path = os.path.join(folder, "profile", "companies.toml")
    return load_file(path).get("company", []) if os.path.exists(path) else []
