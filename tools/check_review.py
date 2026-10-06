#!/usr/bin/env python3
"""Check a Job Search folder after phase 5's Cowork run: a rule rewrite proposed by the weekly review,
turned down once, then saved after a yes, with its replay and history.

    python tools/check_review.py "<folder>" expected.json

expected.json:  {"rule": 4}      # the rule the seeded overturns were on

Prints one line per check and exits 1 if any fails. Reads only; writes nothing.
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "plugins", "job-search", "engine"))
sys.dont_write_bytecode = True

from jobkit import rules, store  # noqa: E402


def check(folder, want):
    results = []

    def ok(passed, what):
        results.append((bool(passed), what))

    n = want["rule"]
    what = f"rule {n}"
    rows = [c for c in store.Folder(folder).read_changes() if c.get("what") == what]
    kinds = [c.get("kind") for c in rows]
    ok("declined" in kinds, f"{what}: the 'not now' was logged ({', '.join(kinds) or 'nothing logged'})")
    ok("changed" in kinds, f"{what}: the change was saved")
    if "declined" in kinds and "changed" in kinds:
        ok(kinds.index("declined") < kinds.index("changed"), f"{what}: turned down before it was saved, not after")
        ok(kinds.count("changed") == 1, f"{what}: saved once ({kinds.count('changed')} changes)")
    changed = next((c for c in rows if c.get("kind") == "changed"), None)
    if changed:
        rep = changed.get("replay") or {}
        ok((changed.get("why") or "").strip(), f"{what}: saved with the user's words: \"{changed.get('why', '')}\"")
        ok(rep.get("kind") == "rule" and (rep.get("checked") or 0) > 0,
           f"{what}: saved with a replay over {rep.get('checked', 0)} saved postings, {rep.get('flips', 0)} would change")
        text = rules.read(folder).splitlines()
        found = rules.sections(text)
        ok(n in found, f"{what}: still in rules.md, with its number")
        if n in found:
            name, start, end = found[n]
            section = "\n".join(text[start:end]).strip()
            ok(section == changed.get("now"), f"{what}: rules.md holds the wording that was saved")
            history = [line for line in text[start:end] if line.lstrip().startswith("- Changes:")]
            ok(any(changed["date"] in line and "Replayed over" in line for line in history),
               f"{what}: its dated Changes line, with the replay ({len(history)} in all)")
            ok(changed.get("was") and changed["was"] != changed.get("now"), f"{what}: the earlier wording is kept in the log")
    others = [c for c in store.Folder(folder).read_changes() if c.get("what") != what and c.get("kind") != "declined"]
    ok(not others, f"no other rule or setting changed ({', '.join(c['what'] for c in others) or 'none'})")
    return results


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        want = json.load(fh)
    results = check(argv[0], want)
    for passed, what in results:
        print(("PASS  " if passed else "FAIL  ") + what)
    failed = sum(1 for p, _ in results if not p)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
