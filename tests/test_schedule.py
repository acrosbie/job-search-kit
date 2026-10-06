"""Scan health, and when a scheduled check is overdue, for catching up."""

import datetime as dt
import unittest

from jobkit import configure, health, net, scan, schedule, settings, store
from jobkit.clock import Clock
from tests.test_scan import FIXED, Fake, ScanBase, answers


def at(days, hour=18):
    return Clock("", fixed=FIXED + dt.timedelta(days=days, hours=hour - 18))


class HealthTest(ScanBase):
    def scan_on(self, days):
        self.addCleanup(net.use, net.use(Fake(answers())))
        return scan.run(self.root, clock=at(days), workers=2)

    def test_a_board_failing_three_scans_in_a_row(self):
        self.assertEqual(self.scan_on(0)["health"]["failing"], [])
        self.scan_on(1)
        out = self.scan_on(2)
        self.assertEqual([(b["board"], b["fails"]) for b in out["health"]["failing"]], [("Broken", 3)])

    def test_a_board_silent_for_30_days(self):
        self.assertEqual(self.scan_on(0)["health"]["silent"], [])
        out = self.scan_on(31)  # Globex has answered with no jobs since the first scan
        self.assertEqual([b["slug"] for b in out["health"]["silent"]], ["globex"])
        self.assertNotIn("acme", [b["slug"] for b in out["health"]["silent"]])

    def test_a_workday_board_at_its_cap(self):
        s = settings.load(self.root)
        boards = {"big": {"ats": "workday", "jobs": s.workday["max_total"], "error": ""},
                  "small": {"ats": "workday", "jobs": 12, "error": ""}}
        out = health.boards(boards, [{"slug": "big", "name": "Big Co"}], s, "2026-09-24")
        self.assertEqual(out["at_cap"], [{"board": "Big Co", "slug": "big", "jobs": s.workday["max_total"]}])


class ScheduleTest(ScanBase):
    def setUp(self):
        super().setUp()
        self.folder.log_run({"at": "2026-09-25T09:00:00-06:00"})  # a Friday

    def overdue(self, every, when):
        configure.set_value(self.root, "schedule.scan", every)
        clock = Clock("", fixed=dt.datetime.fromisoformat(when))
        return schedule.scan_overdue(settings.load(self.root), self.folder.read_runs(limit=1), clock)

    def test_scan_overdue(self):
        self.assertFalse(self.overdue("daily", "2026-09-25T20:00:00-06:00"))
        self.assertTrue(self.overdue("daily", "2026-09-26T20:00:00-06:00"))
        self.assertFalse(self.overdue("weekdays", "2026-09-27T20:00:00-06:00"))  # Sunday: Friday's scan counts
        self.assertTrue(self.overdue("weekdays", "2026-09-28T20:00:00-06:00"))   # Monday
        self.assertFalse(self.overdue("weekly", "2026-10-01T20:00:00-06:00"))
        self.assertTrue(self.overdue("weekly", "2026-10-02T20:00:00-06:00"))
        self.assertFalse(self.overdue("", "2026-12-25T20:00:00-06:00"))  # nothing scheduled, nothing overdue

    def test_a_choice_of_words_is_checked(self):
        with self.assertRaises(configure.Refused):
            configure.set_value(self.root, "schedule.scan", "hourly")

    def test_review_ready_and_due(self):
        configure.set_value(self.root, "schedule.review", "weekly")
        s = settings.load(self.root)
        clock = Clock("", fixed=dt.datetime.fromisoformat("2026-10-01T12:00:00-06:00"))
        self.assertEqual(schedule.review_state(self.root, s, clock), ("", False))  # 6 days since the first scan
        later = Clock("", fixed=dt.datetime.fromisoformat("2026-10-03T12:00:00-06:00"))
        self.assertEqual(schedule.review_state(self.root, s, later), ("", True))
        self.folder.log_review({"at": "2026-10-03T07:00:00-06:00", "date": "2026-10-03", "kind": "prepared"})
        self.assertEqual(schedule.review_state(self.root, s, later)[0], "2026-10-03")
        self.folder.log_review({"at": "2026-10-03T11:00:00-06:00", "date": "2026-10-03", "kind": "done"})
        self.assertEqual(schedule.review_state(self.root, s, later), ("", False))


if __name__ == "__main__":
    unittest.main()
