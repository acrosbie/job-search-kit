"""Recording a verdict on a posting: its status in postings.json, and a line in decisions.log.

The user's own decision always stands: Claude can't overwrite it unless the user asks (force). Only
the user marks a posting applied, and that goes through track.apply, which also records the
application, so a posting is never applied without one.
"""

from . import store
from .clock import Clock
from .errors import NotFound, Refused

# A verdict that contradicts an earlier one, for spotting when the user overturns Claude or a rule.
OPPOSED = {"worth_applying": {"not_a_fit", "skipped"}, "not_a_fit": {"worth_applying", "applied"}}


def last_user_decision(decisions, key):
    """The user's most recent verdict on this posting, or None."""
    mine = [d for d in decisions if d.get("key") == key and d.get("by") == "user"]
    return mine[-1] if mine else None


def mark(root, key, status, by, note="", force=False, clock=None, choice="", at=""):
    """Record one verdict and return the decisions.log row. `choice` is the id of a click on the jobs
    page, kept so the same click is never recorded twice, and `at` the time it was made (default now)."""
    folder = store.Folder(root)
    state = folder.load_postings()
    entry = state["postings"].get(key)
    if not entry:
        raise NotFound(f"unknown key {key}")
    if status == "applied" and by != "user":
        raise Refused("only the user marks a posting applied")
    decisions = folder.read_decisions()
    earlier = [d for d in decisions if d.get("key") == key]
    mine = last_user_decision(decisions, key)
    if by != "user" and mine and not force:
        raise Refused(f"the user already decided this one ({mine.get('verdict')} on {mine.get('date')}); "
                      "their decision stands")
    clk = clock or Clock()
    reversal = ""
    if by == "user" and earlier and status in OPPOSED.get(earlier[-1].get("verdict"), set()):
        reversal = earlier[-1].get("verdict")
    at = at or clk.stamp()
    entry["status"] = status
    entry["triaged"] = at[:10]
    if note:
        entry["note"] = note
    folder.save_postings(state)
    row = {"at": at, "date": at[:10], "key": key, "company": entry["company"], "title": entry["title"],
           "verdict": status, "reason": note, "by": by}
    if reversal:
        row["reverses"] = reversal
    if choice:
        row["choice"] = choice
    folder.log_decision(row)
    return row
