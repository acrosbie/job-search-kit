"""Changing the user's triage rules in rules.md: the evidence for a change, saving it only with its
replay, and its history. The made-up Denver support manager and Acme board from test_scan."""

import json
import os
import shutil
import tempfile

from jobkit import rules, store, verdicts
from jobkit.clock import Clock
from jobkit.errors import NotFound, Refused
from tests.test_scan import FIXED, ScanBase

CLOCK = Clock("", fixed=FIXED)

RULES = """# My screening rules

## Rules: any one makes a posting Not a fit
Checked in order. Numbers never change; a retired rule keeps its number, marked retired.

### Rule 1: Location
- Not a fit when: outside Denver and not remote.
- Why: "Denver", 2026-09-20

### Rule 2: Owns the queue
- Not a fit when: the role owns the support queue rather than leading the team.
- Doesn't count: a lead who covers the queue now and then.
- Why: "I don't want to work tickets", 2026-09-20

### Rule 3: Hours
- Not a fit when: on-call rotation.
- Why: "no on-call", 2026-09-20

## Flags: noted, never reject on their own

### Contract or temporary
- When: contract work.
- What to do: note it.

## Rules the scan applies before triage
- Location.
"""


class RuleBase(ScanBase):
    def setUp(self):
        super().setUp()
        self.scan()
        with open(rules.path(self.root), "w", encoding="utf-8") as f:
            f.write(RULES)
        self.folder = store.Folder(self.root)
        # Claude turned two jobs away on Rule 2, and the user overturned both.
        for k, line in (("greenhouse-acme-1", "Lead the Denver team"), ("greenhouse-acme-4", "This role is remote")):
            verdicts.mark(self.root, k, "not_a_fit", "claude", note=f'Rule 2 (Owns the queue): "{line}"', clock=CLOCK)
            verdicts.mark(self.root, k, "worth_applying", "user", note="leading the queue is fine", clock=CLOCK)
        verdicts.mark(self.root, "greenhouse-acme-9", "worth_applying", "claude", note="Tailor: ...", clock=CLOCK)

    def file(self, name, content):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        return p

    def rules_text(self):
        return rules.read(self.root)


class EvidenceTest(RuleBase):
    def test_what_a_change_could_touch(self):
        e = rules.evidence(self.root, 2, words="support operations")
        self.assertEqual(e["name"], "Owns the queue")
        self.assertTrue(e["text"].startswith("### Rule 2: Owns the queue"))
        self.assertEqual(sorted(f["key"] for f in e["fired"]), ["greenhouse-acme-1", "greenhouse-acme-4"])
        self.assertEqual([(o["key"], o["their_words"]) for o in e["overturned"]],
                         [("greenhouse-acme-1", "leading the queue is fine"), ("greenhouse-acme-4", "leading the queue is fine")])
        self.assertEqual([c["key"] for c in e["candidates"]], ["greenhouse-acme-9"])
        self.assertIn("support operations", e["candidates"][0]["lines"][0].lower())

    def test_rule_1_is_not_rule_10(self):
        self.assertTrue(rules.cites("Rule 1 (Location): far", 1))
        self.assertFalse(rules.cites("Rule 10 (Cooldown): far", 1))

    def test_an_unknown_rule(self):
        with self.assertRaises(NotFound):
            rules.evidence(self.root, 9)


class ChangeTest(RuleBase):
    NEW = "- Not a fit when: the role only works the queue and leads nobody.\n- Doesn't count: a lead who covers the queue.\n- Why: \"I don't want to work tickets\", 2026-09-20\n"

    def replay(self, flips=(), checked=("greenhouse-acme-1", "greenhouse-acme-4", "greenhouse-acme-9")):
        return self.file("replay.json", {"checked": list(checked), "flips": list(flips)})

    def test_saved_with_its_replay_and_history(self):
        flips = [{"key": "greenhouse-acme-1", "after": "passes", "quote": "Lead the Denver team"}]
        out = rules.change(self.root, CLOCK, n=2, text_file=self.file("r.md", self.NEW), why="leading the queue is fine",
                           replay_file=self.replay(flips))
        self.assertEqual(out["kind"], "changed")
        text = self.rules_text()
        section = text[text.index("### Rule 2"):text.index("### Rule 3")]
        self.assertIn("### Rule 2: Owns the queue\n- Not a fit when: the role only works the queue and leads nobody.", section)
        self.assertIn('- Changes: 2026-09-24: "leading the queue is fine". Replayed over 3 saved postings: 1 would change: Acme, Customer Support Manager (passes).', section)
        self.assertIn("### Rule 1: Location", text)  # nothing else moved
        self.assertIn("### Rule 3: Hours", text)
        row = self.folder.read_changes()[-1]
        self.assertEqual((row["what"], row["kind"], row["why"]), ("rule 2", "changed", "leading the queue is fine"))
        self.assertIn("work tickets", row["was"])
        # A second change keeps the first one's history line.
        rules.change(self.root, CLOCK, n=2, text_file=self.file("r.md", self.NEW), why="again", replay_file=self.replay())
        section = self.rules_text()[self.rules_text().index("### Rule 2"):self.rules_text().index("### Rule 3")]
        self.assertEqual(section.count("- Changes:"), 2)

    def test_refused_without_a_replay_or_the_users_words(self):
        with self.assertRaises(Refused):
            rules.change(self.root, CLOCK, n=2, text_file=self.file("r.md", self.NEW), why="fine")
        with self.assertRaises(Refused):
            rules.change(self.root, CLOCK, n=2, text_file=self.file("r.md", self.NEW), why=" ", replay_file=self.replay())
        self.assertEqual(self.rules_text(), RULES)

    def test_a_wanted_job_turned_away_needs_their_yes(self):
        flips = [{"key": "greenhouse-acme-9", "after": "not_a_fit", "quote": "Run support operations."}]
        with self.assertRaises(Refused) as no:
            rules.change(self.root, CLOCK, n=2, text_file=self.file("r.md", self.NEW), why="stricter", replay_file=self.replay(flips))
        self.assertIn("Head of Support Operations Manager", str(no.exception))
        self.assertEqual(self.rules_text(), RULES)
        rules.change(self.root, CLOCK, n=2, text_file=self.file("r.md", self.NEW), why="stricter",
                     replay_file=self.replay(flips), accept=["greenhouse-acme-9"])
        self.assertEqual(self.folder.read_changes()[-1]["accepted_flips"], ["greenhouse-acme-9"])

    def test_retire_into_a_flag(self):
        flag = self.file("f.md", "### On-call\n- When: an on-call rotation.\n- What to do: note it, and ask how often.\n")
        rules.change(self.root, CLOCK, n=3, why="never comes up", replay_file=self.replay(), retire=True, flag_file=flag)
        text = self.rules_text()
        self.assertIn("### Rule 3: Hours (retired 2026-09-24)\n- Retired: \"never comes up\".", text)
        self.assertLess(text.index("### On-call"), text.index("## Rules the scan applies"))
        self.assertGreater(text.index("### On-call"), text.index("## Flags"))
        self.assertEqual(self.folder.read_changes()[-1]["kind"], "retired")

    def test_a_new_rule_takes_the_next_number(self):
        rules.change(self.root, CLOCK, new_name="Travel", text_file=self.file("r.md", "- Not a fit when: travel over 25%.\n"),
                     why="no heavy travel", replay_file=self.replay())
        text = self.rules_text()
        self.assertIn("### Rule 4: Travel\n- Not a fit when: travel over 25%.", text)
        self.assertLess(text.index("### Rule 4"), text.index("## Flags"))

    def test_a_flip_names_a_saved_posting(self):
        with self.assertRaises(Refused):
            rules.change(self.root, CLOCK, n=2, text_file=self.file("r.md", self.NEW), why="x",
                         replay_file=self.replay([{"key": "nope", "after": "passes"}]))


class DeclineAndRequeueTest(RuleBase):
    def test_decline_is_logged(self):
        rules.decline(self.root, CLOCK, "rule 2", "not now", proposal="let leads cover the queue")
        row = self.folder.read_changes()[-1]
        self.assertEqual((row["what"], row["kind"], row["why"], row["now"]), ("rule 2", "declined", "not now", "let leads cover the queue"))

    def test_requeue_only_what_a_rule_turned_away(self):
        out = rules.requeue(self.root, CLOCK, ["greenhouse-acme-3", "greenhouse-acme-1", "greenhouse-acme-9", "nope"],
                            "Rule 1 now lets Austin through")
        self.assertEqual([r["key"] for r in out["requeued"]], ["greenhouse-acme-3"])
        self.assertEqual(len(out["refused"]), 3)
        p = self.folder.load_postings()["postings"]
        self.assertEqual(p["greenhouse-acme-3"]["status"], "new")
        self.assertEqual(p["greenhouse-acme-1"]["status"], "worth_applying")  # the user's decision stands


if __name__ == "__main__":
    import unittest
    unittest.main()


class TriageEvidenceTest(RuleBase):
    """Claude's Not a fit names its rule and quotes the posting; the engine checks both. Found in an
    audit: the weekly review grouped overturns by the note's wording, so a note worded differently
    dropped out of it, and nothing showed the posting had been read."""

    def mark(self, *args):
        import contextlib
        import io
        from jobkit import cli
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["mark", "--folder", self.root, *args])
        return code, err.getvalue()

    def test_a_not_a_fit_needs_its_rule_and_a_quote_from_the_posting(self):
        k = "greenhouse-acme-9"
        self.assertIn("--rule", self.mark(k, "not_a_fit", "--by", "claude")[1])
        self.assertIn("--quote", self.mark(k, "not_a_fit", "--by", "claude", "--rule", "2")[1])
        code, err = self.mark(k, "not_a_fit", "--by", "claude", "--rule", "2", "--quote", "Answer tickets all day")
        self.assertEqual(code, 3)
        self.assertIn("isn't in the posting", err)
        self.assertIn("no rule 7", self.mark(k, "not_a_fit", "--by", "claude", "--rule", "7", "--quote", "Run support operations")[1])
        code, _ = self.mark(k, "not_a_fit", "--by", "claude", "--rule", "Rule 2", "--quote", "“run support operations.”",
                            "--note", "Owns the queue")
        self.assertEqual(code, 0)
        row = self.folder.read_decisions()[-1]
        self.assertEqual((row["rule"], row["quote"]), ("rule 2", "“run support operations.”"))

    def test_a_your_call_quotes_and_a_worth_applying_needs_neither(self):
        self.assertEqual(self.mark("greenhouse-acme-9", "your_call", "--by", "claude", "--note", "Question: remote?")[0], 3)
        self.assertEqual(self.mark("greenhouse-acme-3", "worth_applying", "--by", "claude", "--note", "Tailor: x")[0], 0)

    def test_the_review_groups_by_the_rule_named_however_the_note_reads(self):
        from jobkit import review
        for k in ("greenhouse-acme-3", "greenhouse-acme-9"):
            text = self.folder.read_description(k).split("---", 1)[1].strip().splitlines()[0]
            self.assertEqual(self.mark(k, "not_a_fit", "--by", "claude", "--rule", "2", "--quote", text,
                                       "--note", "It owns the queue, so no")[0], 0)
            self.assertEqual(self.mark(k, "worth_applying", "--by", "user", "--candidate-rule", "--note", "I'd do it")[0], 0)
        out = review.build(self.root, CLOCK)
        g = [x for x in out["disagreements"] if x["rule"] == "rule 2"]
        self.assertEqual(len(g), 1)
        self.assertLessEqual({"greenhouse-acme-3", "greenhouse-acme-9"}, {o["key"] for o in g[0]["overturns"]})
        self.assertEqual(sorted(c["key"] for c in out["candidate_rules"]), ["greenhouse-acme-3", "greenhouse-acme-9"])

    def test_claude_leaves_an_applied_job_applied(self):
        # Applied with no decision of the user's logged: brought over from an older tracker.
        state = self.folder.load_postings()
        state["postings"]["greenhouse-acme-3"]["status"] = "applied"
        self.folder.save_postings(state)
        code, err = self.mark("greenhouse-acme-3", "worth_applying", "--by", "claude", "--note", "Tailor: x")
        self.assertEqual(code, 3)
        self.assertIn("--record-only", err)
        self.assertEqual(self.mark("greenhouse-acme-3", "worth_applying", "--by", "claude", "--record-only")[0], 0)
        self.assertEqual(self.folder.load_postings()["postings"]["greenhouse-acme-3"]["status"], "applied")
