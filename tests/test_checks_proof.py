"""Phase 5's proof, in code: with two overturns seeded on one rule, the weekly review proposes a rewrite,
the rewrite is replayed, a "not now" changes nothing, and a yes saves it with its history. Builds on
the rules.md in test_rule_change, where Claude turned two jobs away on Rule 2 and the user overturned
both; here Claude also turned a third away on Rule 2, which the user never decided."""

import os
import sys

from jobkit import review, rules, store, verdicts
from tests.test_rule_change import CLOCK, RULES, RuleBase

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")


class ProofTest(RuleBase):
    def setUp(self):
        super().setUp()
        verdicts.mark(self.root, "greenhouse-acme-9", "not_a_fit", "claude", note='Rule 2 (Owns the queue): "Run support operations."',
                      clock=CLOCK, force=True)

    def test_the_weekly_review_proposes_replays_and_saves_only_after_a_yes(self):
        # The review proposes a rewrite of Rule 2.
        group = next(g for g in review.build(self.root, CLOCK)["disagreements"] if g["rule"] == "rule 2")
        self.assertTrue(group["propose"])
        self.assertEqual(group["since_last_change"], 2)

        # The replay: everything the rule turned away, and what the user said.
        e = rules.evidence(self.root, 2, words="queue")
        self.assertEqual(sorted(f["key"] for f in e["fired"]), ["greenhouse-acme-1", "greenhouse-acme-4", "greenhouse-acme-9"])
        self.assertEqual(len(e["overturned"]), 2)
        replay = self.file("replay.json", {"checked": [f["key"] for f in e["fired"]], "flips": [
            {"key": "greenhouse-acme-1", "after": "passes", "quote": "Lead the Denver team."},
            {"key": "greenhouse-acme-4", "after": "passes", "quote": "This role is remote."},
            {"key": "greenhouse-acme-9", "after": "passes", "quote": "Run support operations."}]})
        wording = self.file("rule.md", "- Not a fit when: the role only works the queue and leads nobody.\n"
                                       "- Doesn't count: a lead who covers the queue now and then.\n"
                                       "- Why: \"I don't want to work tickets\", 2026-09-20\n")

        # "No, leave it for now": nothing changes, and it isn't proposed again.
        rules.decline(self.root, CLOCK, "rule 2", "leave it for now", proposal="turn away only roles that lead nobody")
        self.assertEqual(rules.read(self.root), RULES)
        group = next(g for g in review.build(self.root, CLOCK)["disagreements"] if g["rule"] == "rule 2")
        self.assertFalse(group["propose"])

        # "Actually, yes": saved with its replay and the user's words, number and history kept.
        out = rules.change(self.root, CLOCK, n=2, text_file=wording, why="actually, yes: leading the queue is fine",
                           replay_file=replay)
        self.assertEqual(out["would_pass"], ["greenhouse-acme-9"])  # the one the user never decided
        text = rules.read(self.root)
        self.assertIn("### Rule 2: Owns the queue\n- Not a fit when: the role only works the queue and leads nobody.", text)
        self.assertIn('- Changes: 2026-09-24: "actually, yes: leading the queue is fine". Replayed over 3 saved postings: 3 would change', text)
        kinds = [c["kind"] for c in store.Folder(self.root).read_changes() if c["what"] == "rule 2"]
        self.assertEqual(kinds, ["declined", "changed"])

        # The job it now lets through goes back on the list, if the user agrees.
        self.assertEqual([r["key"] for r in rules.requeue(self.root, CLOCK, out["would_pass"], "Rule 2 changed")["requeued"]],
                         ["greenhouse-acme-9"])

        # And the Cowork run's checker agrees.
        sys.path.insert(0, TOOLS)
        import check_review
        failed = [what for ok, what in check_review.check(self.root, {"rule": 2}) if not ok]
        self.assertEqual(failed, [])


if __name__ == "__main__":
    import unittest
    unittest.main()
