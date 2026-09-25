#!/usr/bin/env python3
"""
Score the kit's triage against an answer key from tools/make_triage_test.py. A development tool.

    python tools/compare_triage.py --folder <Job Search folder> --answer-key <file> [--out <results dir>]

For each held-out posting: the right answer (the user's final call), the kit's verdict (Claude's
latest verdict in decisions.log), whether they agree, and for not-a-fit, whether the same rule
number was cited. Disagreements are listed with both reasons, for the user to fix or accept.
Exit code 0 when every verdict agrees.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "plugins", "job-search", "engine"))
sys.dont_write_bytecode = True

from jobkit import store  # noqa: E402

LABEL = {"worth_applying": "Worth applying", "your_call": "Your call", "not_a_fit": "Not a fit",
         "skipped": "Skipped", "applied": "Applied", None: "(no verdict)"}


def rule_number(text):
    m = re.search(r"\b[Rr]ule (\d+)\b", text or "")
    return m.group(1) if m else ""


def score(folder, key):
    decisions = store.Folder(folder).read_decisions()
    latest = {}
    for d in decisions:
        if d.get("by") == "claude":
            latest[d["key"]] = d
    rows = []
    for c in key["postings"]:
        kit = latest.get(c["key"])
        verdict = kit["verdict"] if kit else None
        row = {**c, "kit_verdict": verdict, "kit_reason": (kit or {}).get("reason", ""),
               "agrees": verdict == c["right_answer"]}
        if c["right_answer"] == "not_a_fit" and c["decided_by"] == "claude" and verdict == "not_a_fit":
            row["same_rule"] = rule_number(c["claude_reason"]) == rule_number(row["kit_reason"])
        rows.append(row)
    return rows


def report(rows):
    agree = sum(r["agrees"] for r in rows)
    ruled = [r for r in rows if "same_rule" in r]
    lines = [f"# Triage check: {agree} of {len(rows)} verdicts agree", "",
             f"Not-a-fit postings citing the same rule: {sum(r['same_rule'] for r in ruled)} of {len(ruled)}.", "",
             "| # | Posting | Right answer | Kit | Agrees |", "|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        who = " (user)" if r["decided_by"] == "user" else ""
        lines.append(f"| {i} | {r['company']}: {r['title']} | {LABEL[r['right_answer']]}{who} | "
                     f"{LABEL.get(r['kit_verdict'], r['kit_verdict'])} | {'yes' if r['agrees'] else '**no**'} |")
    lines += ["", "## Disagreements", ""]
    for i, r in enumerate(rows, 1):
        if r["agrees"] and r.get("same_rule", True):
            continue
        lines += [f"### {i}. {r['company']}: {r['title']}", "",
                  f"- Right answer: **{LABEL[r['right_answer']]}**, decided by {r['decided_by']}",
                  f"- Reference triage said: {LABEL.get(r['claude_verdict'])}: {r['claude_reason']}"]
        if r["user_reason"]:
            lines.append(f"- The user said: {r['user_reason']}")
        lines += [f"- The kit said: **{LABEL.get(r['kit_verdict'], r['kit_verdict'])}**: {r['kit_reason']}",
                  f"- Key: `{r['key']}`", ""]
    return "\n".join(lines) + "\n", agree


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--folder", required=True)
    p.add_argument("--answer-key", required=True)
    p.add_argument("--out")
    a = p.parse_args(argv)
    with open(a.answer_key, encoding="utf-8") as f:
        key = json.load(f)
    rows = score(a.folder, key)
    text, agree = report(rows)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.answer_key)), "results")
    if os.path.commonpath([os.path.abspath(out), REPO]) == REPO:
        print("refusing to write inside the repository: this is personal data", file=sys.stderr)
        return 3
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"triage-check-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(text.split("\n## Disagreements")[0])
    print(f"full result: {path}")
    return 0 if agree == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
