"""A job's summary: Claude's account of a posting, written to the user, checked by the engine before it
is saved. Found in real use (2026-10-09): the page showed notes like "Re-triaged on the loosened years
rule (rule 11, short by 1 of 3 allowed). Tilt: ... hands-on Snowflake not his"."""

import contextlib
import io
import json
import os

from jobkit import cli, page, summary, verdicts
from jobkit.clock import Clock
from jobkit.errors import Refused
from tests.test_scan import FIXED, ScanBase

CLOCK = Clock("", fixed=FIXED)
KEY = "greenhouse-acme-1"  # "Lead the Denver team."
GOOD = {"headline": "A close match, and near home.",
        "fits": ["You'd \"Lead the Denver team\", the kind of team you ran at Peakline."],
        "enjoy": "Building a team from the ground up, which you said you like best.",
        "watch": ["Pay isn't stated, so ask early whether it reaches your $120K ask."],
        "ask": "How big is the team today? Ask on the first call.",
        "tailor": ["Lead with the team you grew from 2 to 6."],
        "mirror": ["Denver team"]}


class SummaryTest(ScanBase):
    def setUp(self):
        super().setUp()
        self.scan()

    def refused(self, status="worth_applying", **changes):
        with self.assertRaises(Refused) as e:
            summary.check({**GOOD, **changes}, status, self.folder.read_description(KEY))
        return str(e.exception)

    def test_a_good_one_is_saved_on_the_posting_and_shown_on_the_page(self):
        row = verdicts.mark(self.root, KEY, "worth_applying", "claude", note="Tailor: lead with the team", clock=CLOCK,
                            summary=GOOD)
        self.assertEqual(row["summary"]["headline"], GOOD["headline"])
        saved = self.folder.load_postings()["postings"][KEY]["summary"]
        self.assertEqual((saved["mirror"], saved["date"]), (["Denver team"], "2026-09-24"))
        job = next(j for j in page.build(self.root, CLOCK)["waiting"] if j["key"] == KEY)
        self.assertEqual(job["summary"]["fits"], GOOD["fits"])

    def test_the_old_habits_are_refused_by_name(self):
        self.assertIn("rule by number", self.refused(headline="Re-triaged on the loosened years rule (rule 11)."))
        self.assertIn('"his"', self.refused(watch=["Hands-on Snowflake is not his."]))
        self.assertIn('"the user"', self.refused(fits=["It suits the user's background."]))
        self.assertIn("lower-case", self.refused(tailor=["lead with your two migrations framed as programs"]))
        self.assertIn("label", self.refused(headline="Tailor: lead with the migrations."))
        self.assertIn("everyday words", self.refused(headline="Squarely in lane for you."))
        self.assertIn("isn't in the posting", self.refused(fits=['You\'d "own the global support budget" there.']))

    def test_someone_named_in_the_sentence_can_be_she_or_he(self):
        out = summary.check({**GOOD, "ask": "Ask Hannah about her team, on the first call."}, "worth_applying",
                            self.folder.read_description(KEY))
        self.assertEqual(out["ask"], "Ask Hannah about her team, on the first call.")
        self.assertIn('"his"', self.refused(watch=["Hands-on Snowflake is not his."]))  # about the user: still refused
        self.assertIn('"the user"', self.refused(ask="Ask Hannah whether the user fits."))

    def test_what_each_verdict_needs(self):
        self.assertIn("ask:", self.refused("your_call", ask=""))
        self.assertIn("tailor:", self.refused("worth_applying", tailor=[]))
        self.assertIn("headline:", self.refused(headline=""))
        self.assertIn("fits: 1 to 3", self.refused(fits=["One.", "Two.", "Three.", "Four."]))
        self.assertIn("has no", self.refused(verdict="Worth applying"))
        self.assertIn("under 100", self.refused(headline="A " + "very " * 30 + "long headline."))

    def test_only_claude_writes_one(self):
        with self.assertRaises(Refused):
            verdicts.mark(self.root, KEY, "worth_applying", "user", clock=CLOCK, summary=GOOD)

    def test_written_again_on_a_job_the_user_decided_with_no_new_verdict(self):
        verdicts.mark(self.root, KEY, "skipped", "user", note="too far", clock=CLOCK)
        logged = len(self.folder.read_decisions())
        out = verdicts.summarize(self.root, KEY, {**GOOD, "tailor": []}, clock=CLOCK)
        self.assertEqual(out["status"], "skipped")
        self.assertEqual(len(self.folder.read_decisions()), logged)
        self.assertEqual(self.folder.load_postings()["postings"][KEY]["status"], "skipped")

    def test_from_the_command_line(self):
        path = os.path.join(self.root, "summary.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({**GOOD, "headline": "his kind of job"}, f)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["mark", "--folder", self.root, KEY, "worth_applying", "--by", "claude",
                             "--note", "Tailor: lead with the team", "--summary", path])
        self.assertEqual(code, 3)
        self.assertIn("needs another look", err.getvalue())
        with open(path, "w", encoding="utf-8") as f:
            json.dump(GOOD, f)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["summarize", "--folder", self.root, KEY, "--summary", path]), 0)
