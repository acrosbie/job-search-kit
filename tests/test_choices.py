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

    def test_what_happened_to_each_click_is_kept_for_the_page(self):
        # A page opened from the folder can't be told directly; it reads these back (page.json `handled`).
        from jobkit import page
        clicks = [click("c-1", "want", key="greenhouse-acme-1", at="2026-09-24T17:00:00Z"),
                  click("c-2", "skip", key="greenhouse-acme-1", at="2026-09-24T17:00:01Z"),
                  click("c-3", "want", key="greenhouse-nowhere-9", at="2026-09-24T17:00:02Z")]
        choices.record(self.root, CLOCK, clicks)
        choices.record(self.root, CLOCK, clicks[1:2])  # sent again: already recorded
        rows = sorted((r["id"], r["outcome"]) for r in self.folder.read_choices())
        self.assertEqual(rows, [("c-1", "superseded"), ("c-2", "already"), ("c-2", "recorded"), ("c-3", "unknown")])
        choices.record(self.root, CLOCK, clicks)  # nothing new to log
        self.assertEqual(len(self.folder.read_choices()), 4)
        handled = page.build(self.root, CLOCK)["handled"]
        self.assertEqual({k: v["outcome"] for k, v in handled.items()}, {"c-1": "superseded", "c-2": "already", "c-3": "unknown"})
        self.assertIn("greenhouse-nowhere-9", handled["c-3"]["why"])

    def test_the_page_keeps_claude_s_reason_apart_from_the_user_s_words(self):
        # A want with no note used to show Claude's rejection under "You said".
        from jobkit import page
        reason = 'Rule 2 (Owns the queue): "Lead the Denver team."'
        verdicts.mark(self.root, "greenhouse-acme-1", "not_a_fit", "claude", note=reason, clock=CLOCK)
        choices.record(self.root, CLOCK, [click("c-1", "want", key="greenhouse-acme-1")])
        j = next(j for j in page.build(self.root, CLOCK)["waiting"] if j["key"] == "greenhouse-acme-1")
        self.assertEqual((j["by"], j["claude_said"], j["you_said"]), ("user", reason, ""))
        choices.record(self.root, CLOCK, [click("c-2", "want", key="greenhouse-acme-1", note="it's remote really",
                                                at="2026-09-24T17:30:00Z")])
        j = next(j for j in page.build(self.root, CLOCK)["waiting"] if j["key"] == "greenhouse-acme-1")
        self.assertEqual((j["claude_said"], j["you_said"]), (reason, "it's remote really"))

    def test_once_only(self):
        one = [click("c-1", "skip", key="greenhouse-acme-1")]
        choices.record(self.root, CLOCK, one)
        again = choices.record(self.root, CLOCK, one)
        self.assertEqual(([c["id"] for c in again["already"]], again["recorded"]), (["c-1"], []))
        self.assertEqual(sum(1 for d in self.folder.read_decisions() if d.get("choice") == "c-1"), 1)

    def test_only_the_last_click_on_a_job_counts(self):
        # Five clicks on one job in a few seconds, as when the page didn't show the first one landing.
        flips = [click(f"c-{i}", a, key="greenhouse-acme-1", at=f"2026-09-24T17:00:0{i}Z")
                 for i, a in enumerate(["want", "skip", "skip", "skip", "want"])]
        out = choices.record(self.root, CLOCK, flips + [click("c-9", "followed_up", app="x", at="2026-09-24T17:00:09Z")])
        self.assertEqual([c["id"] for c in out["recorded"]], ["c-4"])
        self.assertEqual([c["id"] for c in out["superseded"]], ["c-0", "c-1", "c-2", "c-3"])
        mine = [d for d in self.folder.read_decisions() if d["by"] == "user"]
        self.assertEqual([(d["verdict"], d.get("reverses", "")) for d in mine], [("worth_applying", "")])

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
