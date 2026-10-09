"""Snapshots: the records as they were before each command, in 30 slots written over in turn, so a bad
change (by a command, or a hand edit) can be put right. Nothing is ever deleted."""

import json
import os

from jobkit import store
from tests.test_track import TrackBase


class SnapshotTest(TrackBase):
    def apply(self, company, role):
        return self.run_cli("apply", "--company", company, "--role", role, "--channel", "other", "--top-pick", "no")

    def test_taken_before_a_command_that_changes_something(self):
        self.apply("Globex", "Support Lead")
        snaps = self.folder.list_snapshots()
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["before"], "apply")
        self.assertIn("data/applications.json", snaps[0]["files"])
        held = json.loads(self.folder.snapshot_file(snaps[0]["slot"], "data/applications.json"))
        self.assertNotIn("Globex", [a["company"] for a in held["applications"]])  # as it was before

    def test_none_when_nothing_changed(self):
        self.apply("Globex", "Support Lead")
        self.run_cli("applications")  # changes nothing it hadn't already
        self.run_cli("queue")
        self.assertEqual(len(self.folder.list_snapshots()), 2)  # before apply, and the state apply left

    def test_the_slots_are_written_over_in_turn(self):
        old = store.SNAPSHOT_SLOTS
        store.SNAPSHOT_SLOTS = 3
        self.addCleanup(setattr, store, "SNAPSHOT_SLOTS", old)
        for i in range(5):
            self.apply("Globex", f"Support Lead {i}")
        snaps = self.folder.list_snapshots()
        self.assertEqual(sorted(s["slot"] for s in snaps), [1, 2, 3])
        self.assertEqual(len(os.listdir(self.folder.snapshots)), 4)  # three slots and the index
        newest = json.loads(self.folder.snapshot_file(snaps[0]["slot"], "data/applications.json"))
        self.assertIn("Support Lead 3", [a["role"] for a in newest["applications"]])

    def test_a_file_is_put_back_and_what_was_there_is_kept(self):
        self.apply("Globex", "Support Lead")
        before = self.folder.list_snapshots()[-1]  # the oldest: before Globex
        with open(self.folder.applications_json, "w", encoding="utf-8") as f:
            f.write('{"applications": [{"company": "broken by hand"')
        code, out, _ = self.run_cli("restore", str(before["slot"]), "--file", "data/applications.json")
        self.assertEqual(code, 0)
        self.assertNotIn("Globex", [a["company"] for a in self.folder.load_applications()])
        kept = self.folder.list_snapshots()[0]
        self.assertEqual(kept["before"], "restore")
        self.assertIn(b"broken by hand", self.folder.snapshot_file(kept["slot"], "data/applications.json"))
        code, _, err = self.run_cli("restore", str(before["slot"]), "--file", "profile/nothing.toml")
        self.assertEqual(code, 1)
        self.assertIn("holds no", err)

    def test_working_on_a_copy_doesnt_carry_snapshots_back(self):
        self.apply("Globex", "Support Lead")
        code, out, _ = self.run_cli("changed", "--since", "2000-01-01T00:00:00+00:00")
        self.assertFalse([f for f in json.loads(out)["files"] if f.startswith("data/snapshots/")])
