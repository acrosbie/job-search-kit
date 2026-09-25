"""The engine on real public job boards, replayed from tests/recorded/sample (29 boards recorded
live on 2026-09-24), for the made-up New York job seeker in tests/fixtures/sample-folder.

The expected results in tests/fixtures/sample-expected.json were produced by the engine after it
matched the reference scanner with 0 differences over 590 boards (docs/phase-1/equivalence.md).
A change here means the engine now treats real postings differently: find out why before
rebuilding the file with tools/make_sample_expected.py.
"""

import datetime as dt
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from jobkit import net, scan, store
from jobkit.clock import Clock

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "recorded", "sample")
FOLDER = os.path.join(HERE, "fixtures", "sample-folder")
EXPECTED = os.path.join(HERE, "fixtures", "sample-expected.json")
AS_OF = dt.datetime(2026, 9, 24, 19, 0, tzinfo=dt.timezone.utc)


def replay_sample():
    """Scan a fresh copy of the sample folder from the recording. Returns (folder, summary, misses)."""
    root = os.path.join(tempfile.mkdtemp(), "Job Search")
    shutil.copytree(FOLDER, root)
    replay = net.Replay(SAMPLE)
    previous = net.use(replay)
    try:
        summary = scan.run(root, clock=Clock("America/New_York", fixed=AS_OF))
    finally:
        net.use(previous)
    return root, summary, replay.misses


def expected_view(root, summary, misses):
    f = store.Folder(root)
    postings = f.load_postings()["postings"]
    digest = lambda text: hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return {
        "counts": {k: summary[k] for k in ("boards", "failed", "read", "dropped_title", "dropped_location",
                                           "matched", "new", "rejected_by_rule")},
        "failures": sorted(x["slug"] for x in summary["failures"]),
        "check_by_hand": [x["name"] for x in summary["check_by_hand"]],
        "jobs_read_per_board": {k: b.get("jobs") for k, b in f.load_postings()["boards"].items()},
        "misses": misses,
        "postings": {k: {"status": v["status"], "rule": v.get("rule", ""), "reason": v.get("note", ""),
                         "flag": v["flag"], "salary": v["salary"], "location": v["location"], "title": v["title"],
                         "description": digest(f.read_description(k))}
                     for k, v in postings.items()},
    }


class RecordedSampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root, summary, misses = replay_sample()
        cls.addClassCleanup(shutil.rmtree, os.path.dirname(root))
        cls.got = expected_view(root, summary, misses)
        with open(EXPECTED, encoding="utf-8") as f:
            cls.want = json.load(f)

    def test_the_recording_covers_every_request(self):
        self.assertEqual(self.got["misses"], [])

    def test_counts(self):
        self.assertEqual(self.got["counts"], self.want["counts"])
        self.assertEqual(self.got["failures"], ["no-such-board"])
        self.assertEqual(self.got["check_by_hand"], ["Initech"])

    def test_every_board_reads_the_same_jobs(self):
        # Catches a reader that breaks for boards with no match for this job seeker.
        self.assertEqual(self.got["jobs_read_per_board"], self.want["jobs_read_per_board"])

    def test_every_posting(self):
        self.assertEqual(sorted(self.got["postings"]), sorted(self.want["postings"]))
        for key, want in self.want["postings"].items():
            self.assertEqual(self.got["postings"][key], want, key)

    def test_every_board_system_answered(self):
        systems = {k.split("-")[0] if not k.startswith("careers-api") else "careers-api" for k in self.got["postings"]}
        self.assertGreaterEqual(self.got["counts"]["boards"], 29)
        # Not every system has a match for this job seeker, but the ones that do must keep matching.
        self.assertEqual(systems, {k.split("-")[0] if not k.startswith("careers-api") else "careers-api"
                                   for k in self.want["postings"]})


if __name__ == "__main__":
    unittest.main()
