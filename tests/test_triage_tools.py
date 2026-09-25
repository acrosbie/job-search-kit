"""tools/make_triage_test.py and tools/compare_triage.py on a made-up search."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

from jobkit import store

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import compare_triage  # noqa: E402
import make_triage_test  # noqa: E402

# key: (Claude's verdict, rule, the user's later verdict or None)
MADE_UP = {
    "gh-acme-1": ("not_a_fit", "rule_1", None),
    "gh-acme-2": ("not_a_fit", "rule_6", None),
    "gh-acme-3": ("worth_applying", "", None),
    "gh-acme-4": ("your_call", "", None),
    "gh-acme-5": ("worth_applying", "", "not_a_fit"),   # the user overruled Claude
    "gh-acme-6": ("not_a_fit", "rule_11", None),
}


class TriageToolsTest(unittest.TestCase):
    def setUp(self):
        self.top = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.top)
        self.folder = os.path.join(self.top, "Job Search")
        f = store.Folder(self.folder)
        state = {"postings": {}, "boards": {}}
        for k, (verdict, rule, user) in MADE_UP.items():
            state["postings"][k] = {"company": "Acme", "title": f"Job {k[-1]}", "status": user or verdict,
                                    "file": f"{k}.md", "note": "old", "triaged": "2026-09-23"}
            f.save_description({"key": k, "title": f"Job {k[-1]}", "company": "Acme", "location": "", "url": "",
                                "posted": "", "ats": "greenhouse"}, "Text.", "2026-09-23")
            f.log_decision({"date": "2026-09-23", "key": k, "verdict": verdict, "by": "claude",
                            "reason": f"Rule {rule.split('_')[1]}: quoted" if rule else "fits", "rule": rule})
            if user:
                f.log_decision({"date": "2026-09-24", "key": k, "verdict": user, "by": "user", "reason": "page: too far"})
        f.log_decision({"date": "2026-09-20", "key": "gh-acme-9", "verdict": "not_a_fit", "by": "claude", "reason": "old"})
        f.save_postings(state)
        self.key = os.path.join(self.top, "answer-key.json")

    def run_tool(self, module, args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return module.main(args)

    def test_hold_out_then_score(self):
        args = ["--folder", self.folder, "--answer-key", self.key, "--worth", "1", "--call", "1",
                "--not-a-fit", "3", "--min-overridden", "1"]
        self.assertEqual(self.run_tool(make_triage_test, args), 0)
        with open(self.key, encoding="utf-8") as fh:
            chosen = json.load(fh)["postings"]
        keys = {c["key"] for c in chosen}
        self.assertEqual(len(chosen), 5)
        self.assertIn("gh-acme-5", keys)  # the overruled one
        self.assertEqual(next(c for c in chosen if c["key"] == "gh-acme-5")["right_answer"], "not_a_fit")

        f = store.Folder(self.folder)
        postings = f.load_postings()["postings"]
        for k in keys:
            self.assertEqual(postings[k]["status"], "new")
            self.assertNotIn("note", postings[k])
        self.assertFalse(any(d["key"] in keys for d in f.read_decisions()))  # the answers left the folder

        # The kit's triage: right on everything except the overruled one, and one rule cited differently.
        for c in chosen:
            verdict = "worth_applying" if c["key"] == "gh-acme-5" else c["right_answer"]
            reason = "Rule 3: quoted" if c["key"] == "gh-acme-1" else c["claude_reason"]
            f.log_decision({"key": c["key"], "verdict": verdict, "by": "claude", "reason": reason})
        rows = compare_triage.score(self.folder, {"postings": chosen})
        self.assertEqual(sum(r["agrees"] for r in rows), 4)
        self.assertFalse(next(r for r in rows if r["key"] == "gh-acme-1")["same_rule"])
        text, agree = compare_triage.report(rows)
        self.assertIn("4 of 5 verdicts agree", text)
        self.assertIn("The user said: page: too far", text)

    def test_answer_key_must_be_outside_the_folder(self):
        inside = os.path.join(self.folder, "answer-key.json")
        self.assertEqual(self.run_tool(make_triage_test, ["--folder", self.folder, "--answer-key", inside]), 3)
        self.assertFalse(os.path.exists(inside))


if __name__ == "__main__":
    unittest.main()
