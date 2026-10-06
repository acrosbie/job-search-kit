"""Choices made on the jobs page, recorded as the user's own, once each."""

import os
import tempfile

from jobkit import choices, track, verdicts
from jobkit.clock import Clock
from tests.test_scan import FIXED, ScanBase

CLOCK = Clock("", fixed=FIXED)


def click(cid, action, at="2026-09-24T17:00:00.000Z", **kw):
    return {"id": cid, "at": at, "action": action, "num": 1, "label": "Acme, a job", "note": "", "channel": "",
            "top_pick": "", "contact": "", "recorded": "", **kw}


class ChoicesTest(ScanBase):
    def setUp(self):
        super().setUp()
        self.scan()
        self.folder.save_applications([])

    def test_each_kind_of_click(self):
        out = choices.record(self.root, CLOCK, [
            click("c-1", "want", key="greenhouse-acme-3", note="it's remote really"),
            click("c-2", "skip", key="greenhouse-acme-4", note="too far"),
            click("c-3", "applied", key="greenhouse-acme-1", channel="linkedin", top_pick="yes"),
        ])
        self.assertEqual([c["id"] for c in out["recorded"]], ["c-1", "c-2", "c-3"])
        d = {r["key"]: r for r in self.folder.read_decisions() if r["by"] == "user"}
        self.assertEqual((d["greenhouse-acme-3"]["verdict"], d["greenhouse-acme-3"]["reverses"]), ("worth_applying", "not_a_fit"))
        self.assertEqual((d["greenhouse-acme-4"]["verdict"], d["greenhouse-acme-4"]["reason"]), ("skipped", "too far"))
        a = track.find(track.load(self.root), "greenhouse-acme-1")
        self.assertEqual((a["channel"], a["top_pick"], a["history"][0]["choice"]), ("linkedin", True, "c-3"))

        replies = choices.record(self.root, CLOCK, [
            click("c-4", "replied", app="greenhouse-acme-1", contact="Dana Example", at="2026-09-24T17:05:00Z"),
            click("c-5", "contact", app="greenhouse-acme-1", contact="Lee Example", at="2026-09-24T17:06:00Z"),
        ])
        self.assertEqual(len(replies["recorded"]), 2)
        a = track.find(track.load(self.root), "greenhouse-acme-1")
        self.assertEqual((a["status"], a["contact"]), ("replied", "Lee Example"))

    def test_once_only(self):
        one = [click("c-1", "skip", key="greenhouse-acme-1")]
        choices.record(self.root, CLOCK, one)
        again = choices.record(self.root, CLOCK, one)
        self.assertEqual(([c["id"] for c in again["already"]], again["recorded"]), (["c-1"], []))
        self.assertEqual(sum(1 for d in self.folder.read_decisions() if d.get("choice") == "c-1"), 1)

    def test_a_later_word_in_chat_stands(self):
        verdicts.mark(self.root, "greenhouse-acme-1", "worth_applying", "user", clock=CLOCK)  # 18:00 UTC
        out = choices.record(self.root, CLOCK, [click("c-1", "skip", key="greenhouse-acme-1")])  # clicked at 17:00
        self.assertEqual([c["id"] for c in out["superseded"]], ["c-1"])
        self.assertEqual(self.folder.load_postings()["postings"]["greenhouse-acme-1"]["status"], "worth_applying")

    def test_what_cant_be_recorded(self):
        out = choices.record(self.root, CLOCK, [click("c-1", "skip", key="no-such-job"), click("c-2", "dance", key="x")])
        self.assertEqual([c["id"] for c in out["unknown"]], ["c-1", "c-2"])

    def test_the_pasted_text(self):
        text = ('My job choices:\n- #1 Acme, a job: Skip\n[choices: [{"id": "c-9", "at": "2026-09-24T17:00:00Z", '
                '"action": "skip", "key": "greenhouse-acme-1", "note": "too far"}]]\n')
        path = os.path.join(tempfile.mkdtemp(), "pasted.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.addCleanup(os.remove, path)
        out = choices.record_file(self.root, CLOCK, path)
        self.assertEqual([c["id"] for c in out["recorded"]], ["c-9"])


if __name__ == "__main__":
    import unittest
    unittest.main()
