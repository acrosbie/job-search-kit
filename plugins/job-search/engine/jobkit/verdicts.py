"""Recording a verdict on a posting: its status in postings.json, and a line in decisions.log.

The user's own decision always stands: Claude can't overwrite it unless the user asks (force). Only
the user marks a posting applied, and that goes through track.apply, which also records the
application, so a posting is never applied without one.
"""

import re

from . import store
from .clock import Clock
from .errors import NotFound, Refused

# A verdict that contradicts an earlier one, for spotting when the user overturns Claude or a rule.
OPPOSED = {"worth_applying": {"not_a_fit", "skipped"}, "not_a_fit": {"worth_applying", "applied"}}
_PLAIN = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
                        "\u00a0": " ", "*": " ", "`": " "})


def _plain(s):
    """Text as a quote is looked for: one case, plain dashes, no quote marks, bullets or emphasis."""
    s = (s or "").translate(_PLAIN)
    s = re.sub(r"(^|\n)\s*(?:[-•]|\d+[.)])\s+", " ", s)
    s = re.sub(r"[\"']", "", s)
    return re.sub(r"\s+", " ", s).strip().casefold()


def quote_found(quote, text):
    """True when every part of the quote (split at "..." or the ellipsis character) is in the text, in order."""
    body, pos = _plain(text), 0
    parts = [p for p in (_plain(x).strip(" .,;:") for x in re.split(r"\.\.\.|…", quote or "")) if p]
    if not parts:
        return False
    for p in parts:
        at = body.find(p, pos)
        if at < 0:
            return False
        pos = at + len(p)
    return True


def _rule_id(root, rule):
    """'rule N' for a rule rules.md has, from "N", "rule N" or "Rule N"."""
    m = re.fullmatch(r"\s*(?:rule\s*)?(\d+)\s*", rule or "", re.I)
    if not m:
        raise Refused(f"name the rule by its number in rules.md, as --rule N, not {rule!r}")
    n = int(m.group(1))
    try:
        from . import rules
        known = rules.sections(rules.read(root).splitlines())
    except FileNotFoundError:
        known = None
    if known is not None and n not in known:
        raise Refused(f"rules.md has no rule {n}")
    return f"rule {n}"


def _check_evidence(root, folder, key, entry, status, rule, quote):
    """Claude's Not a fit names its rule; a Not a fit or Your call quotes the posting line it rests on,
    and the quote must be in the saved posting: it shows the posting was read, and lets the weekly
    review group overturns by rule however the note is worded."""
    if status not in ("not_a_fit", "your_call"):
        return ""
    if status == "not_a_fit" and not rule:
        raise Refused("name the rule it rests on: --rule N, its number in rules.md")
    if not quote:
        raise Refused("quote the line from the posting this rests on, word for word: --quote \"...\"")
    if entry.get("unread"):
        raise Refused("this posting's description couldn't be read yet, so it can't be judged; the next scan reads it")
    text = folder.read_description(key) or ""
    if not quote_found(quote, text):
        raise Refused("that quote isn't in the posting as saved: copy the words exactly (show KEY prints it). "
                      "Use ... between two parts")
    return _rule_id(root, rule) if rule else ""


def last_user_decision(decisions, key):
    """The user's most recent verdict on this posting, or None."""
    mine = [d for d in decisions if d.get("key") == key and d.get("by") == "user"]
    return mine[-1] if mine else None


def mark(root, key, status, by, note="", force=False, clock=None, choice="", at="", record_only=False,
         rule="", quote="", evidence=False, candidate_rule=False):
    """Record one verdict and return the decisions.log row. `choice` is the id of a click on the jobs
    page, kept so the same click is never recorded twice, and `at` the time it was made (default now).

    `record_only` logs Claude's verdict without changing the posting: for a job the user had already
    applied to before Claude judged it, so the weekly review's outcomes can still compare the two.

    `evidence` (the command line sets it for Claude) requires a Not a fit to name its `rule` and a Not a
    fit or Your call to `quote` the posting; both are kept on the row. `candidate_rule` marks the
    user's reason as one that sounds like a rule, for the weekly review."""
    folder = store.Folder(root)
    state = folder.load_postings()
    entry = state["postings"].get(key)
    if not entry:
        raise NotFound(f"unknown key {key}")
    if status == "applied" and by != "user":
        raise Refused("only the user marks a posting applied")
    rule_id = ""
    if record_only:
        if by != "claude":
            raise Refused("only Claude's own verdict is recorded without changing the posting")
        if evidence:
            rule_id = _check_evidence(root, folder, key, entry, status, rule, quote)
        clk = clock or Clock()
        row = {"at": at or clk.stamp(), "date": (at or clk.stamp())[:10], "key": key, "company": entry["company"],
               "title": entry["title"], "verdict": status, "reason": note, "by": by, "record_only": True}
        row.update({k: v for k, v in (("rule", rule_id), ("quote", quote)) if v})
        folder.log_decision(row)
        return row
    decisions = folder.read_decisions()
    earlier = [d for d in decisions if d.get("key") == key and not d.get("record_only")]
    mine = last_user_decision(decisions, key)
    if by != "user" and mine and not force:
        raise Refused(f"the user already decided this one ({mine.get('verdict')} on {mine.get('date')}); "
                      "their decision stands")
    if by == "claude" and entry.get("status") == "applied" and not force:
        raise Refused("the user applied to this one: record Claude's verdict with --record-only, which leaves it applied")
    if evidence and by == "claude":
        rule_id = _check_evidence(root, folder, key, entry, status, rule, quote)
    clk = clock or Clock()
    reversal = ""
    if by == "user" and earlier and status in OPPOSED.get(earlier[-1].get("verdict"), set()):
        reversal = earlier[-1].get("verdict")
    at = at or clk.stamp()
    entry["status"] = status
    entry["triaged"] = at[:10]
    if note:
        entry["note"] = note
    if rule_id:
        entry["rule"] = rule_id
    folder.save_postings(state)
    row = {"at": at, "date": at[:10], "key": key, "company": entry["company"], "title": entry["title"],
           "verdict": status, "reason": note, "by": by}
    if reversal:
        row["reverses"] = reversal
    if choice:
        row["choice"] = choice
    row.update({k: v for k, v in (("rule", rule_id), ("quote", quote)) if v})
    if candidate_rule and by == "user":
        row["candidate_rule"] = True
    folder.log_decision(row)
    return row
