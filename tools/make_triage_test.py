#!/usr/bin/env python3
"""
Hold out postings from a real search so the kit's triage can be checked against the decisions
already made on them. A development tool, not part of the kit.

    python tools/make_triage_test.py --folder <Job Search folder> --answer-key <file outside it> \
        [--since 2026-09-23] [--worth 4] [--call 4] [--not-a-fit 12] [--min-overridden 4] [--seed 7]

The folder must already hold the imported search (tools/import_reference.py with --seen and
--triage-log). Candidates are postings with a Claude verdict on or after --since and a saved
description. Each one's right answer is the user's final call: their own verdict where they made
one, otherwise Claude's. The chosen postings go back to "new", their verdicts come out of
decisions.log, and the answers go to --answer-key, which must be outside the folder so the
session doing the triage can't read them.
"""

import argparse
import json
import os
import random
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "plugins", "job-search", "engine"))
sys.dont_write_bytecode = True

from jobkit import store  # noqa: E402

JUDGED = ("worth_applying", "your_call", "not_a_fit")
RULE_ORDER = ["rule_1", "rule_3", "rule_4", "rule_5", "rule_6", "rule_7", "rule_10", "rule_11"]


def candidates(folder, since):
    f = store.Folder(folder)
    postings = f.load_postings()["postings"]
    by_key = {}
    for d in f.read_decisions():
        by_key.setdefault(d["key"], []).append(d)
    out = []
    for key, ds in by_key.items():
        claude = [d for d in ds if d.get("by") == "claude"]
        user = [d for d in ds if d.get("by") == "user"]
        if not claude or claude[-1]["date"] < since or key not in postings or f.read_description(key) is None:
            continue
        final = user[-1] if user else claude[-1]
        if final["verdict"] not in JUDGED:
            continue
        out.append({"key": key, "company": postings[key]["company"], "title": postings[key]["title"],
                    "right_answer": final["verdict"], "decided_by": final["by"],
                    "claude_verdict": claude[-1]["verdict"], "claude_rule": claude[-1].get("rule", ""),
                    "claude_reason": claude[-1].get("reason", ""),
                    "user_reason": user[-1].get("reason", "") if user else "",
                    "overridden": bool(user) and user[-1]["verdict"] != claude[-1]["verdict"]})
    return sorted(out, key=lambda c: c["key"])


def choose(cands, worth, call, not_a_fit, min_overridden, seed):
    rng = random.Random(seed)
    pool = cands[:]
    rng.shuffle(pool)
    chosen = []

    def take(pred, n):
        for c in [c for c in pool if pred(c) and c not in chosen][:n]:
            chosen.append(c)

    take(lambda c: c["overridden"], min_overridden)
    for rule in RULE_ORDER:  # one not-a-fit per rule first, so every rule is exercised
        if sum(c["right_answer"] == "not_a_fit" for c in chosen) >= not_a_fit:
            break
        if not any(c["right_answer"] == "not_a_fit" and c["claude_rule"] == rule for c in chosen):
            take(lambda c, r=rule: c["right_answer"] == "not_a_fit" and c["claude_rule"] == r and not c["overridden"], 1)
    for verdict, n in (("worth_applying", worth), ("your_call", call), ("not_a_fit", not_a_fit)):
        have = sum(c["right_answer"] == verdict for c in chosen)
        take(lambda c, v=verdict: c["right_answer"] == v, max(0, n - have))
    return sorted(chosen, key=lambda c: (JUDGED.index(c["right_answer"]), c["key"]))


def hold_out(folder, chosen):
    f = store.Folder(folder)
    state = f.load_postings()
    keys = {c["key"] for c in chosen}
    for k in keys:
        p = state["postings"][k]
        for x in ("note", "rule", "triaged"):
            p.pop(x, None)
        p["status"] = "new"
    f.save_postings(state)
    kept = [d for d in f.read_decisions() if d["key"] not in keys]
    with open(f.decisions_log, "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(json.dumps(d, ensure_ascii=False) + "\n" for d in kept)


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--folder", required=True)
    p.add_argument("--answer-key", required=True)
    p.add_argument("--since", default="2026-09-23")
    p.add_argument("--worth", type=int, default=4)
    p.add_argument("--call", type=int, default=4)
    p.add_argument("--not-a-fit", type=int, default=12)
    p.add_argument("--min-overridden", type=int, default=4)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args(argv)
    folder, key_file = os.path.abspath(a.folder), os.path.abspath(a.answer_key)
    if os.path.commonpath([key_file, folder]) == folder:
        print("the answer key must be outside the folder, or the triage session could read it", file=sys.stderr)
        return 3
    for path in (folder, key_file):
        if os.path.commonpath([path, REPO]) == REPO:
            print("refusing to write inside the repository: this is personal data", file=sys.stderr)
            return 3
    cands = candidates(folder, a.since)
    chosen = choose(cands, a.worth, a.call, a.not_a_fit, a.min_overridden, a.seed)
    hold_out(folder, chosen)
    with open(key_file, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"since": a.since, "seed": a.seed, "postings": chosen}, fh, indent=1, ensure_ascii=False)
    counts = {v: sum(c["right_answer"] == v for c in chosen) for v in JUDGED}
    rules = sorted({c["claude_rule"] for c in chosen if c["right_answer"] == "not_a_fit" and c["claude_rule"]},
                   key=lambda r: int(re.sub(r"\D", "", r) or 0))
    print(f"held out {len(chosen)} of {len(cands)} candidates: {counts}, "
          f"{sum(c['overridden'] for c in chosen)} overridden by the user, not-a-fit rules {rules}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
