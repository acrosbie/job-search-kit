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


# A place abroad written the way hiring systems write it, with a country code that is also a US state's
# code: "Berlin, DE", "Bengaluru, IN", "Tel Aviv, IL", or a Canadian province and CA: "Toronto, ON, CA".
_PROVINCE_CA = re.compile(r",\s*(?:ON|BC|QC|AB|MB|NS|NB|SK|NL|PE)\s*,\s*CA\s*$")
_STATE_LIKE_CODE = re.compile(r",\s*(?:DE|IN|IL)\s*$")


def _whole_word(rx, text):
    for m in (rx.finditer(text) if rx else ()):
        if (m.start() == 0 or text[m.start() - 1] == " ") and (m.end() == len(text) or text[m.end()] == " "):
            return True
    return False


def _abroad_by_code(place, s):
    """True for one listed place that is abroad by its country code. DE, IN and IL count only after a
    city the user's abroad list names as a whole word, so "Indianapolis, IN" stays in Indiana."""
    place = place.strip()
    if _PROVINCE_CA.search(place):
        return True
    m = _STATE_LIKE_CODE.search(place)
    return bool(m) and _whole_word(s.abroad, norm_loc(place[:m.start()]))


def _home_listed(loc, s):
    return any(_has(rx, loc) for rx in (s.hybrid_ok, s.remote_only, s.in_country, s.country_wide))


def location_ok(location, s):
    """(keep, flag code). An unrecognisable place is kept and flagged, because the description
    usually names it. A place abroad is dropped unless a place at home is also listed."""
    places = re.split(r"\s*[;|]\s*", location or "")
    if any(_abroad_by_code(p, s) for p in places):
        rest = "; ".join(p for p in places if p.strip() and not _abroad_by_code(p, s))
        if not _home_listed(norm_loc(rest), s):
            return False, ""
        location = rest
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


# A posting is a stranger's text, read by Claude. These find the few things in it that are warnings
# rather than facts about the job: words aimed at an AI that reads it, and the marks of a fake job. They
# only flag, never reject, and never change the text: a verdict quotes the posting word for word.
_INSTRUCTIONS = re.compile(
    r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+|your\s+)?(?:previous|prior|above|earlier|other)\s+"
    r"(?:instructions?|directions?|rules?|prompts?|guidance)"
    r"|\bif\s+you\s+are\s+an?\s+(?:ai|a\.i\.|llm|large\s+language\s+model|language\s+model|assistant|bot|automated)"
    r"|\b(?:ai|llm|assistant|chatbot|screening\s+tool|bot)s?\s+(?:reading|screening|reviewing|processing|evaluating)\s+this"
    r"|\b(?:note|instructions?|message)\s+(?:to|for)\s+(?:the\s+|any\s+)?(?:ai|llm|assistant|language\s+model)\b"
    r"|\bsystem\s+prompt\b"
    r"|\b(?:mark|rate|score|label|classify)\s+(?:this|the)\s+(?:job|posting|role|position|candidate|application)\s+as\b",
    re.I)
_OFF_PLATFORM = re.compile(
    r"\b(?:contact|text|message|reach|interview|apply|send|add|dm|chat\s+with)\b[^.\n]{0,50}\b(?:telegram|whatsapp|signal\s+app|"
    r"wickr|google\s+hangouts|hangouts|kik)\b"
    r"|\b(?:telegram|whatsapp|wickr|kik)\s*(?:at|:|number|no\.|id|handle|username)\b"
    r"|\b[\w.+-]+@(?:gmail|yahoo|hotmail|outlook|aol|icloud|protonmail|proton|gmx|mail)\.(?:com|me|net)\b",
    re.I)
_PAY_TO_WORK = re.compile(
    r"\b(?:you(?:'ll|\s+will)?\s+(?:need\s+to\s+|must\s+|be\s+required\s+to\s+|have\s+to\s+)|required\s+to\s+|must\s+)"
    r"(?:purchase|buy|pay\s+for)\b"
    r"|\b(?:deposit|cash)\w*\s+(?:a\s+|the\s+)?(?:check|cheque)s?\b|\b(?:check|cheque)s?\s+(?:for\s+you\s+)?to\s+(?:deposit|cash)\b"
    r"|\b(?:training|registration|application|onboarding|background[\s-]check|processing|starter[\s-]kit|equipment)\s+fee\b"
    r"|\bupfront\s+(?:fee|payment|cost)\b",
    re.I)
WARNINGS = (("instructions", _INSTRUCTIONS, "flag_instructions"), ("off_platform", _OFF_PLATFORM, "flag_off_platform"),
            ("pay_to_work", _PAY_TO_WORK, "flag_pay_to_work"))


# A sentence saying the employer will never do these ("we will never ask you to cash a check") is the
# opposite of a warning: many real postings carry such a notice about fake recruiters.
_NEGATED = re.compile(r"\b(?:never|not|won't|don't|doesn't|cannot|can't|no\s+legitimate|beware|scams?|fraud\w*)\b", re.I)


def _sentence_before(body, i):
    start = max(body.rfind(c, 0, i) for c in ".!?\n")
    return body[start + 1:i]


def _words_around(body, start, end, pad=30):
    """The match with a few words either side, cut at whole words."""
    lo, hi = max(0, start - pad), min(len(body), end + pad)
    while lo > 0 and lo < start and not body[lo - 1].isspace():
        lo += 1
    while hi < len(body) and hi > end and not body[hi].isspace():
        hi -= 1
    return re.sub(r"\s+", " ", body[lo:hi]).strip()


def warning_flags(body, s):
    """(code, text) for each warning sign in a posting, quoting its words, in the order above."""
    body = body or ""
    out = []
    for code, rx, label in WARNINGS:
        for m in rx.finditer(body):
            if _NEGATED.search(_sentence_before(body, m.start())):
                continue
            out.append((code, s.label(label, quote=_words_around(body, m.start(), m.end())[:120])))
            break
    return out


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
    flags += warning_flags(body, s)
    return status, rule, reason, flags
