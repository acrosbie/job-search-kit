"""Replaying a proposed change to the scan's rules over every saved posting, before it is saved.

The scan screens a posting once, when it first finds it, so a change to settings.toml (places,
remote wording, pay, phrase rules) touches only postings found after it. Before one is saved, every
saved posting is screened again, under the current settings and under the proposed ones, and each
posting whose outcome differs is listed by name. The user sees, for example, "it would have turned
away 3 jobs, all already turned away, and nothing you applied to or wanted" before saying yes.

This is the reference system's habit: each of its rules carries the count it was replayed at.

The result is kept in data/replay-latest.json; saving the change checks it (changes.guard).
`try-titles` records its comparison the same way, for a change to the title patterns.
"""

import copy

from . import changes, configure, screen, settings, store
from .errors import Refused

def _outcome(posting, body, s):
    """(status, rule, reason) the scan's rules give this posting: status "new" means it passes."""
    keep, code = screen.location_ok(posting.get("location", ""), s)
    if not keep:
        return "not_a_fit", "location_abroad", s.label("reason_abroad", location=screen.norm_loc(posting.get("location")))
    status, rule, reason, _ = screen.assess(posting.get("location", ""), code, body, s)
    return status, rule, reason


def _says(o):
    return "passes" if o[0] == "new" else f"turned away ({o[1]})"


def settings_change(root, clock, sets=(), phrase=None):
    """Replay `sets` ([(key, value)]) and/or one phrase rule ({name, phrases, min_distinct, reason})."""
    raw = configure.show(root)
    now = settings.parse(raw)
    new_raw = copy.deepcopy(raw)
    change = {"set": [], "phrase_reject": None}
    for key, value in sets:
        if not changes.is_scan_rule(key):
            raise Refused(f"{key} isn't one of the scan's rules; replay covers places, remote wording, pay and "
                          "phrase rules (titles use try-titles)")
        section, name, v = configure.coerce(key, value)
        new_raw.setdefault(section, {})[name] = v
        change["set"].append([key, v])
    if phrase:
        rule = configure.phrase_rule(**phrase)
        new_raw["phrase_rejects"] = [r for r in new_raw.get("phrase_rejects", []) if r.get("name") != rule["name"]] + [rule]
        change["phrase_reject"] = rule
    if not change["set"] and not phrase:
        raise Refused("give a change to replay: --set KEY VALUE, or a phrase rule")
    proposed = settings.parse(new_raw)

    folder = store.Folder(root)
    postings = folder.load_postings()["postings"]
    last = changes.last_decisions(folder)
    flips, checked, before_rejected, after_rejected = [], 0, 0, 0
    for k, v in sorted(postings.items()):
        text = folder.read_description(k)
        if text is None:
            continue
        body = text.partition("\n---\n")[2] or text  # the description, without the header
        checked += 1
        before, after = _outcome(v, body, now), _outcome(v, body, proposed)
        before_rejected += before[0] != "new"
        after_rejected += after[0] != "new"
        if before[:2] != after[:2]:
            d = last.get(k, {})
            flips.append({"key": k, "num": v.get("num"), "company": v.get("company", ""), "title": v.get("title", ""),
                          "status": v.get("status", ""), "decided_by": d.get("by", ""), "before": _says(before),
                          "after": _says(after), "reason": after[2] or before[2]})
    rep = {
        "kind": "settings", "at": clock.stamp(), "change": change, "checked": checked,
        "rejected_before": before_rejected, "rejected_after": after_rejected, "flips": flips,
        # Turned away by the change, though the user applied to it or wanted it: needs their explicit yes.
        "wanted": [f["key"] for f in flips if f["after"] != "passes" and changes.wanted(postings[f["key"]], last.get(f["key"]))],
        # Passes with the change, though a rule turned it away and the user never decided it: can go back
        # on the waiting list, if they agree.
        "would_pass": [f["key"] for f in flips if f["after"] == "passes" and postings[f["key"]].get("status") == "not_a_fit"
                       and last.get(f["key"], {}).get("by") != "user"],
    }
    folder.write_json(folder.replay_json, rep)
    return rep


def record_titles(root, clock, patterns, result):
    """Keep a try-titles comparison as the replay of a title change."""
    rep = {"kind": "titles", "at": clock.stamp(), "change": {f"titles.{k}": v for k, v in patterns.items() if v is not None},
           "checked": result.get("titles_read"), "kept_before": result.get("kept_now"),
           "kept_after": result.get("kept_with_change"), "gained": result.get("gained"), "lost": result.get("lost"),
           "flips": [], "wanted": [], "would_pass": []}
    store.Folder(root).write_json(store.Folder(root).replay_json, rep)
    return rep
