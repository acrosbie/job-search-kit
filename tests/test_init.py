"""Starting a folder from the starter data, and the starter data itself."""

import contextlib
import io
import os
import re
import shutil
import tempfile
import unittest

from jobkit import cli, init, net, scan, settings
from jobkit.clock import Clock
from tests.test_recorded import AS_OF, SAMPLE


class InitTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.join(tempfile.mkdtemp(), "Job Search")
        self.addCleanup(shutil.rmtree, os.path.dirname(self.root))

    def test_support_pack(self):
        out = init.init(self.root, field="support-cx", timezone="America/Denver")
        self.assertEqual((out["boards"], out["titles_set"]), (590, True))
        s = settings.load(self.root)
        self.assertEqual(s.timezone, "America/Denver")
        self.assertTrue(s.function.search("Senior Manager, Customer Support"))
        self.assertEqual(s.hybrid_ok, None)  # setup fills the commute in
        self.assertEqual(s.phrase_rejects[0].name, "quota and renewals")
        companies = settings.load_companies(self.root)
        self.assertEqual(companies[-1]["ats"], "himalayas")
        self.assertEqual(len({c["slug"] for c in companies}), len(companies))

    def test_custom_field_matches_nothing_yet(self):
        init.init(self.root)
        s = settings.load(self.root)
        self.assertIsNone(s.function)
        self.assertEqual(len(settings.load_companies(self.root)), 589)

    def test_never_overwrites(self):
        init.init(self.root)
        with open(os.path.join(self.root, "profile", "settings.toml"), encoding="utf-8") as f:
            before = f.read()
        with self.assertRaises(init.AlreadySetUp):
            init.init(self.root, field="support-cx")
        with open(os.path.join(self.root, "profile", "settings.toml"), encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["init", "--folder", self.root]), 3)
            self.assertEqual(cli.main(["init", "--folder", self.root + "-2", "--field", "plumbing"]), 2)

    def test_a_started_folder_scans(self):
        """Started from the support pack, the folder scans the recorded public boards it has answers for."""
        init.init(self.root, field="support-cx", timezone="America/New_York")
        replay = net.Replay(SAMPLE)
        previous = net.use(replay)
        try:
            out = scan.run(self.root, clock=Clock("America/New_York", fixed=AS_OF))
        finally:
            net.use(previous)
        self.assertGreater(out["read"], 4000)      # the 29 recorded boards answered
        self.assertGreater(out["matched"], 0)
        self.assertGreater(out["failed"], 500)     # the rest aren't in the recording, and fail cleanly


class StarterDataTest(unittest.TestCase):
    def test_boards_carry_identifiers_only(self):
        with open(os.path.join(init.STARTER, "boards.toml"), encoding="utf-8") as f:
            text = f.read()
        keys = set(re.findall(r"^(\w+) = ", text, re.M))
        self.assertLessEqual(keys, {"name", "slug", "ats", "token", "host", "tenant", "site"})
        self.assertNotIn("manual", text)

    def test_places_pack_has_no_commute(self):
        s = settings.parse(init._merge({}, init.load_file(os.path.join(init.STARTER, "places", "us.toml"))))
        self.assertIsNone(s.hybrid_ok)
        self.assertIsNone(s.remote_only)
        self.assertTrue(s.in_country.search("Denver CO"))


if __name__ == "__main__":
    unittest.main()
