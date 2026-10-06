"""Every change to how postings are screened, with its evidence: data/changes.log.

No check changes a rule on its own. A change is proposed in plain words, replayed over the saved
postings, and saved only after the user says yes, with their words and the replay result, so the
rules carry their own history. A proposal the user turns down is logged too, so the weekly review
doesn't raise it again for four weeks.

The guard here is the engine's half of that promise. Once there are saved postings, a change to the
scan's rules or titles is refused unless the last replay was of exactly that change, made today;
and a change that would turn away a job the user applied to or wanted is refused unless each such
job is accepted by name. A triage rule in rules.md is replayed by Claude, who reads the postings
(rules.py), and comes through the same check.
"""

import datetime as dt
import os

from . import store
from .errors import Refused

SCAN_RULE_SECTIONS = ("places", "pay")
SCAN_RULE_KEYS = ("description.remote_language",)


def is_scan_rule(key):
    """A setting that decides which saved postings the scan turns away."""
    return key.split(".", 1)[0] in SCAN_RULE_SECTIONS or key in SCAN_RULE_KEYS


def guard_kind(key):
    """Which replay a change to this setting needs: "settings", "titles", or None for neither."""
    if key.startswith("titles."):
        return "titles"
    return "settings" if is_scan_rule(key) else None


# A job the user applied to, or wanted: turning it away needs their explicit yes.
WANTED_STATUSES = ("worth_applying", "applied")
DECLINED_QUIET_DAYS = 28


def wanted(posting, last_decision):
    if (posting or {}).get("status") in WANTED_STATUSES:
        return True
    d = last_decision or {}
    return d.get("by") == "user" and d.get("verdict") in WANTED_STATUSES


def last_decisions(folder):
    out = {}
    for d in folder.read_decisions():
        out[d.get("key")] = d
    return out


def active(root, kind):
    """Whether the guard applies yet: titles once a scan has saved its titles; everything else once
    there are saved postings. Setup's first settings come before either."""
    folder = store.Folder(root)
    if kind == "titles":
        return os.path.exists(folder.titles_tsv)
    return bool(folder.load_postings()["postings"])


def setup_allowed(root):
    """Setup builds the first rules from the user's answers, shown to them as it goes, and runs a
    one-board scan early to prove the network works. Until the user's first decision on a job (the
    first triage together, at the end of setup), its settings may skip the replay. After that, every
    change is a change to rules the user has seen working, and goes through the guard."""
    if any(d.get("by") == "user" for d in store.Folder(root).read_decisions()):
        raise Refused("setup is over: the user has decided jobs already, so change this the careful way, "
                      "with a replay (the tune skill)")
    return True


def summary(rep):
    """The replay, as it is kept with the change."""
    keep = ("kind", "at", "checked", "rejected_before", "rejected_after", "wanted", "would_pass")
    out = {k: rep.get(k) for k in keep if k in rep}
    out["flips"] = len(rep.get("flips", []))
    out["flipped"] = [f"{f.get('company', '')}, {f.get('title', '')}" for f in rep.get("flips", [])][:20]
    return out


def guard(root, kind, covers, accept, why, clock):
    """The replay summary for a change about to be saved, or None while the guard doesn't apply.
    `covers(replay)` says whether the last replay was of this change."""
    if not active(root, kind):
        return None
    folder = store.Folder(root)
    rep = folder.read_json(folder.replay_json)
    if not rep or rep.get("kind") != kind or not covers(rep.get("change") or {}):
        raise Refused("replay this exact change first, and show the user what it would change, before saving it")
    if (rep.get("at") or "")[:10] != clock.today():
        raise Refused("that replay is from an earlier day; replay the change again before saving it")
    missing = [k for k in rep.get("wanted", []) if k not in set(accept)]
    if missing:
        postings = folder.load_postings()["postings"]
        names = "; ".join(f"{postings.get(k, {}).get('company', '')}, {postings.get(k, {}).get('title', k)}" for k in missing)
        raise Refused(f"this change would turn away jobs the user applied to or wanted ({names}). Save it only if "
                      f"they accept that, naming each one with --accept-flips")
    if not (why or "").strip():
        raise Refused("give the user's own words for this change with --why")
    return summary(rep)


def log(root, clock, what, kind, was=None, now=None, why="", replay=None, accepted=()):
    row = {"at": clock.stamp(), "date": clock.today(), "what": what, "kind": kind}
    if was is not None or now is not None:
        row.update({"was": was, "now": now})
    if why:
        row["why"] = why
    if replay is not None:
        row["replay"] = replay
    if accepted:
        row["accepted_flips"] = list(accepted)
    store.Folder(root).log_change(row)
    return row


def last_change(changes, what):
    """The date `what` last changed (a rule or a setting), or ""."""
    dates = [c.get("at", "") for c in changes if c.get("what") == what and c.get("kind") in ("changed", "retired", "added")]
    return max(dates) if dates else ""


def declined_recently(changes, what, today):
    t = dt.date.fromisoformat(today)
    for c in changes:
        if c.get("what") == what and c.get("kind") == "declined":
            try:
                if (t - dt.date.fromisoformat(c.get("date", ""))).days < DECLINED_QUIET_DAYS:
                    return True
            except ValueError:
                continue
    return False
