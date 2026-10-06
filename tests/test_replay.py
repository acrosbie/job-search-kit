"""Replaying a change to the scan's rules over every saved posting, and the guard that won't save
one without its replay. Real postings from the recorded public boards, for the made-up New York job
seeker whose pay line is $100K."""

import contextlib
import datetime as dt
import io
import json
import os
import shutil
import tempfile
import unittest

from jobkit import cli, configure, init, replay, store, verdicts
from jobkit.clock import Clock
from jobkit.errors import Refused
from tests.test_recorded import replay_sample

CLOCK = Clock("America/New_York", fixed=dt.datetime(2026, 9, 25, 15, 0, tzinfo=dt.timezone.utc))
INSTRUMENTL = "himalayas-instrumentl-customer-support-operations-"
DUTCH = "lever-dutch-ebb3eab7-4d59-4144-b814-f572cb590c6f"


class ScannedBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scanned, _, _ = replay_sample()  # one scan of the recordings, copied for each test
        cls.addClassCleanup(shutil.rmtree, os.path.dirname(cls.scanned))

    def setUp(self):
        self.root = os.path.join(tempfile.mkdtemp(), "Job Search")
        self.addCleanup(shutil.rmtree, os.path.dirname(self.root))
        shutil.copytree(self.scanned, self.root)
        self.folder = store.Folder(self.root)
        self.keys = {k[:50]: k for k in self.folder.load_postings()["postings"]}

    def key(self, prefix):
        return next(k for k in self.keys.values() if k.startswith(prefix))


class ReplayTest(ScannedBase):
    def test_a_higher_pay_line(self):
        rep = replay.settings_change(self.root, CLOCK, sets=[("pay.reject_if_top_below", "120000")])
        self.assertEqual([f["key"] for f in rep["flips"]], [self.key(INSTRUMENTL)])  # $95K to $115K
        flip = rep["flips"][0]
        self.assertEqual((flip["before"], flip["after"]), ("passes", "turned away (pay)"))
        self.assertIn("$115K", flip["reason"])
        self.assertEqual(rep["rejected_after"], rep["rejected_before"] + 1)
        self.assertEqual(rep["wanted"], [])  # nobody has decided it yet
        on_disk = self.folder.read_json(self.folder.replay_json)
        self.assertEqual(on_disk["change"]["set"], [["pay.reject_if_top_below", 120000]])

    def test_a_new_place_lets_a_job_through(self):
        hybrid = configure.show(self.root)["places"]["hybrid_ok"] + "|oakland"
        rep = replay.settings_change(self.root, CLOCK, sets=[("places.hybrid_ok", hybrid)])
        self.assertEqual([f["key"] for f in rep["flips"]], [DUTCH])
        self.assertEqual(rep["would_pass"], [DUTCH])  # turned away by a rule, never decided by the user

    def test_only_the_scans_rules(self):
        with self.assertRaises(Refused):
            replay.settings_change(self.root, CLOCK, sets=[("labels.flag_unknown", "where?")])
        with self.assertRaises(Refused):
            replay.settings_change(self.root, CLOCK)


class GuardTest(ScannedBase):
    def save(self, value="120000", **kw):
        return configure.set_value(self.root, "pay.reject_if_top_below", value, clock=CLOCK, **kw)

    def test_no_save_without_its_replay(self):
        with self.assertRaises(Refused):
            self.save(why="lower jobs aren't worth it")
        replay.settings_change(self.root, CLOCK, sets=[("pay.reject_if_top_below", "110000")])
        with self.assertRaises(Refused):  # a replay of a different change
            self.save(why="lower jobs aren't worth it")
        self.assertEqual(configure.show(self.root)["pay"]["reject_if_top_below"], 100000)

    def test_the_users_words_and_an_explicit_yes_to_wanted_jobs(self):
        verdicts.mark(self.root, self.key(INSTRUMENTL), "worth_applying", "claude", clock=CLOCK)
        rep = replay.settings_change(self.root, CLOCK, sets=[("pay.reject_if_top_below", "120000")])
        self.assertEqual(rep["wanted"], [self.key(INSTRUMENTL)])
        with self.assertRaises(Refused) as no_yes:
            self.save(why="under $120K isn't worth it")
        self.assertIn("Instrumentl", str(no_yes.exception))
        with self.assertRaises(Refused):  # the user's words are part of the record
            self.save(accept=[self.key(INSTRUMENTL)])
        self.assertEqual(self.save(why="under $120K isn't worth it", accept=[self.key(INSTRUMENTL)]), (100000, 120000))
        row = self.folder.read_changes()[-1]
        self.assertEqual((row["what"], row["kind"], row["was"], row["now"]), ("setting pay.reject_if_top_below", "changed", 100000, 120000))
        self.assertEqual((row["why"], row["accepted_flips"], row["replay"]["flips"]), ("under $120K isn't worth it", [self.key(INSTRUMENTL)], 1))

    def test_a_replay_from_another_day_is_stale(self):
        replay.settings_change(self.root, CLOCK, sets=[("pay.reject_if_top_below", "120000")])
        tomorrow = Clock("America/New_York", fixed=dt.datetime(2026, 9, 26, 15, 0, tzinfo=dt.timezone.utc))
        with self.assertRaises(Refused):
            configure.set_value(self.root, "pay.reject_if_top_below", "120000", why="x", clock=tomorrow)

    def test_titles_need_try_titles(self):
        level = configure.show(self.root)["titles"]["level"] + "|\\blead\\b"
        with self.assertRaises(Refused):
            configure.set_value(self.root, "titles.level", level, why="leads too", clock=CLOCK)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["try-titles", "--folder", self.root, "--level", level]), 0)
        configure.set_value(self.root, "titles.level", level, why="leads too", clock=Clock("America/New_York"))
        self.assertEqual(self.folder.read_changes()[-1]["replay"]["kind"], "titles")

    def test_settings_that_dont_screen_need_nothing(self):
        configure.set_value(self.root, "you.name", "Sam", clock=CLOCK)
        configure.set_value(self.root, "schedule.scan", "daily", clock=CLOCK)
        self.assertEqual(self.folder.read_changes(), [])

    def test_the_command(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = cli.main(["replay", "--folder", self.root, "--set", "pay.reject_if_top_below", "125000"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out.getvalue())["flips"]), 2)  # HappyCo tops out at $120K too
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(["settings", "set", "--folder", self.root, "pay.reject_if_top_below", "130000"]), 3)
        self.assertIn("replay", err.getvalue())


class SetupTest(ScannedBase):
    def test_setup_until_the_users_first_decision(self):
        # Setup's one-board network check has saved postings and titles; its own settings still go in.
        configure.set_value(self.root, "places.hybrid_ok", "new york|brooklyn", setup=True)
        configure.set_value(self.root, "titles.level", "\\bdirector\\b", setup=True)
        configure.phrase_reject(self.root, "quota", "quota|book of business", setup=True)
        self.assertEqual(self.folder.read_changes(), [])
        verdicts.mark(self.root, self.key(INSTRUMENTL), "skipped", "user", clock=CLOCK)  # the first triage together
        with self.assertRaises(Refused) as over:
            configure.set_value(self.root, "places.hybrid_ok", "new york", setup=True)
        self.assertIn("setup is over", str(over.exception))


class SetupIsUnguardedTest(unittest.TestCase):
    def test_before_anything_is_saved(self):
        root = os.path.join(tempfile.mkdtemp(), "Job Search")
        self.addCleanup(shutil.rmtree, os.path.dirname(root))
        init.init(root, field="custom", timezone="America/Denver")
        configure.set_value(root, "places.hybrid_ok", "denver|aurora")
        configure.set_value(root, "titles.function", "accounting|controller")
        self.assertEqual(store.Folder(root).read_changes(), [])


if __name__ == "__main__":
    unittest.main()
