"""A job's summary: what Claude says about a posting, written to the user, for the jobs page and chat.

A verdict's note was one line in the shape of an audit log ("Your call (rule 1 loosened): '3+ years
of...'"), and it showed on the page as it was: rule numbers, shorthand, the user in the third person.
A summary is how a friend who has read the posting would put it, in parts the page can lay out:

    headline   one plain sentence, the honest take ("Your strongest match this week")
    fits       why it fits: 1 to 3 points tying the job's real work to what the user has done
    enjoy      what they'd probably enjoy, from what they said they enjoy (optional)
    watch      watch-outs in everyday terms: pay against their ask in dollars, office days, gaps (0 to 4)
    ask        the one question that would change their mind, and when to ask it (Your call: required)
    tailor     the resume changes for this job (Worth applying: 1 to 3)
    mirror     the posting's own words worth using (up to 8 short phrases)

The rule, the quote and the old note stay on the verdict, for the weekly review and tuning: the page
shows them folded away, as "Behind the call". The engine checks a summary before it's saved and
refuses one that slips back into the old habits, naming the field.
"""

import json
import re

from .errors import BadFile, Refused

TEXT_FIELDS = ("headline", "enjoy", "ask")
LIST_FIELDS = ("fits", "watch", "tailor", "mirror")
LIMITS = {"headline": 100, "enjoy": 240, "ask": 220, "fits": 240, "watch": 240, "tailor": 220, "mirror": 48}
COUNTS = {"fits": (1, 3), "watch": (0, 4), "tailor": (0, 3), "mirror": (0, 8)}

_RULE = re.compile(r"\brules?\s*#?\d+", re.I)
_THIRD_PERSON = re.compile(r"\b(?:he|his|him|she|her|hers|the user|the candidate|the applicant|the job ?seeker)\b", re.I)
_LABEL = re.compile(r"^(?:tailor|question|tilt|your call|not a fit|worth applying|mirror|note)\s*[:(]", re.I)
_JARGON = re.compile(r"\b(?:in[- ]lane|off[- ]lane|on[- ]lane)\b", re.I)
_QUOTED = re.compile(r"[\"“]([^\"“”]{3,}?)[\"”]")


def read_file(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except ValueError as e:
        raise BadFile(f"the summary file isn't JSON: {e}") from None
    if not isinstance(data, dict):
        raise BadFile("the summary file holds one JSON object with headline, fits, watch, ...")
    return data


def _problems(field, text, posting_text, quote_found):
    out = []
    if _RULE.search(text):
        out.append("names a rule by number; that stays behind the call")
    if _THIRD_PERSON.search(text):
        out.append(f"says \"{_THIRD_PERSON.search(text).group(0)}\"; write to the user as \"you\"")
    if _LABEL.search(text):
        out.append("starts with a label; the page adds its own")
    if _JARGON.search(text):
        out.append(f"uses \"{_JARGON.search(text).group(0)}\"; say it in everyday words")
    if field != "mirror" and text[:1].isalpha() and text[:1].islower():
        out.append("starts with a lower-case letter")
    if field != "mirror" and posting_text is not None:
        for q in _QUOTED.findall(text):
            if len(q.split()) >= 3 and not quote_found(q, posting_text):
                out.append(f"quotes \"{q}\", which isn't in the posting as saved")
    return out


def check(summary, status, posting_text=None):
    """The summary tidied, or Refused naming each field that's wrong. `posting_text` (when there is
    one) is what quoted phrases must come from."""
    from .verdicts import quote_found
    if not isinstance(summary, dict):
        raise Refused("a summary is one object with headline, fits, watch, ...")
    unknown = set(summary) - set(TEXT_FIELDS) - set(LIST_FIELDS)
    if unknown:
        raise Refused(f"a summary has no {', '.join(sorted(unknown))}; its parts are "
                      f"{', '.join(TEXT_FIELDS + LIST_FIELDS)}")
    out, wrong = {}, []
    for field in TEXT_FIELDS:
        value = summary.get(field) or ""
        if not isinstance(value, str):
            wrong.append(f"{field}: one sentence of text")
            continue
        value = " ".join(value.split())
        if value:
            out[field] = value
    for field in LIST_FIELDS:
        value = summary.get(field) or []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            wrong.append(f"{field}: a list of short texts")
            continue
        value = [" ".join(v.split()) for v in value if v.strip()]
        lo, hi = COUNTS[field]
        if not lo <= len(value) <= hi:
            wrong.append(f"{field}: {lo} to {hi} of them, not {len(value)}")
        if value:
            out[field] = value
    if not out.get("headline"):
        wrong.append("headline: one plain sentence with the honest take")
    if status == "your_call" and not out.get("ask"):
        wrong.append("ask: the one question that decides it, and when to ask it")
    if status == "worth_applying" and not out.get("tailor"):
        wrong.append("tailor: the resume changes for this job")
    for field in TEXT_FIELDS + LIST_FIELDS:
        values = out.get(field)
        for text in ([values] if isinstance(values, str) else values or []):
            if len(text) > LIMITS[field]:
                wrong.append(f"{field}: \"{text[:40]}...\" is {len(text)} characters; keep it under {LIMITS[field]}")
            for p in _problems(field, text, posting_text, quote_found):
                wrong.append(f"{field}: \"{text[:40]}{'...' if len(text) > 40 else ''}\" {p}")
    if wrong:
        raise Refused("the summary needs another look: " + "; ".join(wrong))
    return out
