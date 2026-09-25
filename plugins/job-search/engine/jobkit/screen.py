"""Screening one posting against the user's settings: the title and location filters, the
automatic rejects, and the flags. Ported from the reference scanner; its Bay Area tiers are the
general place lists in settings.toml [places].

Nothing here decides fit the way a person would. It narrows what Claude reads, rejects only on
rules the user agreed to, and always records the reason.
"""

import re

from .text import salary_range

# Location flag codes. Rendered to words by settings.toml [labels].
IN_COUNTRY = "in_country"        # somewhere else in the country: needs remote wording in the description
REMOTE_ONLY = "remote_only"      # near enough to visit, too far to commute: needs remote wording
COUNTRY_WIDE = "country_wide"    # the country with no city
UNKNOWN = "unknown"              # no usable place

_NONALNUM = re.compile(r"[^A-Za-z0-9]+")
ONSITE_WINDOW = 90


def _has(rx, s):
    return bool(rx and rx.search(s))


def title_ok(title, s):
    return _has(s.function, title) and _has(s.level, title) and not _has(s.exclude, title)


def norm_loc(location):
    """Punctuation and underscores to single spaces. Case is kept: case-sensitive groups such as
    (?-i:CA) in the place patterns depend on it. Boards write things like 'san_francisconew_york'."""
    return _NONALNUM.sub(" ", location or "").strip()


def location_ok(location, s):
    """(keep, flag code). An unrecognisable place is kept and flagged, because the description
    usually names it. A place abroad is dropped unless a place at home is also listed."""
    loc = norm_loc(location)
    if not loc:
        return True, UNKNOWN
    near, outer = _has(s.hybrid_ok, loc), _has(s.remote_only, loc)
    home, national = _has(s.in_country, loc), _has(s.country_wide, loc)
    if _has(s.abroad, loc) and not (near or outer or home or national):
        return False, ""
    if _has(s.remote, loc) or near:
        return True, ""
    if outer:  # checked after `near`, so "San Francisco; Oakland" passes clean on the near place
        return True, REMOTE_ONLY
    if home:
        return True, IN_COUNTRY
    if national:
        return True, COUNTRY_WIDE
    return True, UNKNOWN


def remote_ok(description, s):
    return _has(s.remote_language, description or "")


def phrase_hits(description, rule):
    """Distinct phrases found, lower-cased, with same_as merging two spellings of one idea."""
    if not rule.phrases:
        return []
    hits = {m.group(0).lower() for m in rule.phrases.finditer(description or "")}
    for spelling, same in rule.same_as.items():
        if spelling in hits:
            hits.discard(spelling)
            hits.add(same)
    return sorted(hits)


def contract_hit(description, s):
    """The phrase that says this is contract, fractional or interim work, or "". Never rejects."""
    m = s.contract.search(description or "") if s.contract else None
    return m.group(0).strip().lower() if m else ""


def onsite_hit(description, s):
    """The sentence saying the role is in the office four or five days a week, or "".

    A proximity test rather than one pattern, because real postings put the days and the place in
    different orders: find a days phrase, then a place phrase within ONSITE_WINDOW characters either
    side, and return the surrounding text so it can be quoted. Never rejects."""
    if not (s.onsite_days and s.onsite_place):
        return ""
    body = description or ""
    for m in s.onsite_days.finditer(body):
        lo, hi = max(0, m.start() - ONSITE_WINDOW), m.end() + ONSITE_WINDOW
        if s.onsite_place.search(body[lo:hi]):
            quote = body[max(0, m.start() - 60):m.end() + 60]
            return re.sub(r"\s+", " ", quote).strip()
    return ""


def location_flag(code, s):
    return {IN_COUNTRY: s.label("flag_in_country"), REMOTE_ONLY: s.label("flag_remote_only"),
            COUNTRY_WIDE: s.label("flag_country_wide"), UNKNOWN: s.label("flag_unknown")}.get(code, "")


def assess(location, location_code, body, s):
    """The automatic verdict for a newly matched posting, in the reference scanner's order:
    location, phrase rules, pay. Then the flags, which never reject.

    Returns (status, rule, reason, flags): status is "new" or "not_a_fit"; rule names what rejected
    it; flags is a list of (code, text) in the order they read."""
    status, rule, reason = "new", "", ""
    place = norm_loc(location)
    if location_code == IN_COUNTRY and not remote_ok(body, s):
        status, rule, reason = "not_a_fit", "location_in_country", s.label("reason_in_country", location=place)
    elif location_code == REMOTE_ONLY and not remote_ok(body, s):
        status, rule, reason = "not_a_fit", "location_remote_only", s.label("reason_remote_only", location=place)

    for pr in s.phrase_rejects:
        hits = phrase_hits(body, pr)
        if status == "new" and pr.phrases and len(hits) >= pr.min_distinct:
            template = pr.reason or s.labels["reason_phrase"]
            status, rule, reason = "not_a_fit", f"phrases:{pr.name}", template.format(hits=", ".join(hits))

    rng = salary_range(body)
    if status == "new" and rng and s.pay_top_below and rng[1] < s.pay_top_below:
        status, rule = "not_a_fit", "pay"
        reason = s.label("reason_pay", top_k=rng[1] // 1000, low_k=rng[0] // 1000, line_k=s.pay_top_below // 1000)

    flags = []
    if location_code:
        flags.append((location_code, location_flag(location_code, s)))
    ctr = contract_hit(body, s)
    if ctr:
        flags.append(("contract", s.label("flag_contract", phrase=ctr)))
    ons = onsite_hit(body, s)
    if ons:
        flags.append(("onsite", s.label("flag_onsite", quote=ons[:90])))
    return status, rule, reason, flags
