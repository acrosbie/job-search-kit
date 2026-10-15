"""Scan health, and when a scheduled check is overdue, for catching up."""

import datetime as dt
import os
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

    def test_a_board_that_never_worked_is_named_at_once(self):
        # Found in real use (2026-10-14): two boards added on 10-12 answered 404 from their first scan.
        out = self.scan_on(0)["health"]["failing"]
        self.assertEqual([(b["board"], b["fails"], b["never_worked"]) for b in out], [("Broken", 1, True)])
        self.scan_on(1)
        out = self.scan_on(2)
        self.assertEqual([(b["board"], b["fails"]) for b in out["health"]["failing"]], [("Broken", 3)])

    def test_one_that_worked_is_named_after_three_failures_in_a_row(self):
        s = settings.load(self.root)
        companies = [{"slug": "acme", "name": "Acme", "careers_url": "https://acme.example/careers"}]
        two = health.boards({"acme": {"fails": 2, "last_ok": "2026-09-01", "error": "404"}}, companies, s, "2026-09-24")
        self.assertEqual(two["failing"], [])
        three = health.boards({"acme": {"fails": 3, "last_ok": "2026-09-01", "error": "404"}}, companies, s, "2026-09-24")
        self.assertEqual((three["failing"][0]["never_worked"], three["failing"][0]["careers_url"]),
                         (False, "https://acme.example/careers"))

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
        self.folder.log_run({"at": "2026-09-25T09:00:00-06:00", "boards": 3})  # a Friday

    def overdue(self, every, when):
        configure.set_value(self.root, "schedule.scan", every)
        clock = Clock("America/Denver", fixed=dt.datetime.fromisoformat(when))  # the times below are Denver's
        return schedule.scan_overdue(settings.load(self.root), self.folder.read_runs(limit=1), clock)

    def missed(self, when, at=""):
        configure.set_value(self.root, "schedule.scan", "weekdays")
        if at:
            configure.set_value(self.root, "schedule.scan_at", at)
        clock = Clock("America/Denver", fixed=dt.datetime.fromisoformat(when))
        return schedule.missed(settings.load(self.root), self.folder.read_runs(), clock)

    def test_the_mornings_missed_are_named(self):
        # Found in real use (2026-10-13 and 14): the 06:50 run couldn't reach the computer two days running.
        if Clock("America/Denver").tz is None:
            self.skipTest("no time zone data on this machine")  # the hours below are Denver's
        self.assertEqual(self.missed("2026-09-30T08:00:00-06:00"), ["2026-09-28", "2026-09-29", "2026-09-30"])
        # With its time saved, today's run isn't missed until it has had its chance.
        self.assertEqual(self.missed("2026-09-30T06:55:00-06:00", at="06:50"), ["2026-09-28", "2026-09-29"])
        self.assertEqual(self.missed("2026-09-30T07:30:00-06:00", at="06:50"), ["2026-09-28", "2026-09-29", "2026-09-30"])
        self.assertEqual(self.missed("2026-09-28T06:00:00-06:00", at="06:50"), [])  # Monday before 6:50: the weekend didn't count

    def test_the_time_is_checked(self):
        from jobkit.errors import Refused
        with self.assertRaises(Refused):
            configure.set_value(self.root, "schedule.scan_at", "7am")
        configure.set_value(self.root, "schedule.scan_at", "06:50")

    def test_scan_overdue(self):
        self.assertFalse(self.overdue("daily", "2026-09-25T20:00:00-06:00"))
        self.assertTrue(self.overdue("daily", "2026-09-26T20:00:00-06:00"))
        self.assertFalse(self.overdue("weekdays", "2026-09-27T20:00:00-06:00"))  # Sunday: Friday's scan counts
        self.assertTrue(self.overdue("weekdays", "2026-09-28T20:00:00-06:00"))   # Monday
        self.assertFalse(self.overdue("weekly", "2026-10-01T20:00:00-06:00"))
        self.assertTrue(self.overdue("weekly", "2026-10-02T20:00:00-06:00"))
        self.assertFalse(self.overdue("", "2026-12-25T20:00:00-06:00"))  # nothing scheduled, nothing overdue

    def test_a_scan_that_reached_no_board_isnt_the_last_scan(self):
        # Found in real use (2026-10-08): a scan where all 592 boards failed behind a proxy still set
        # the time of the last scan, so a missed morning check would have gone unnoticed.
        configure.set_value(self.root, "schedule.scan", "daily")
        self.folder.log_run({"at": "2026-09-26T09:00:00-06:00", "boards": 0, "failed": 592})  # before 0.9.0
        self.folder.log_run({"at": "2026-09-26T10:00:00-06:00", "status": "blocked", "boards": 0, "failed": 3})
        clock = Clock("America/Denver", fixed=dt.datetime.fromisoformat("2026-09-26T20:00:00-06:00"))
        s = settings.load(self.root)
        self.assertTrue(schedule.scan_overdue(s, self.folder.read_runs(), clock))
        facts = schedule.facts(self.root, s, clock)
        self.assertEqual((facts["last_scan_at"], facts["last_attempt_at"], facts["last_scan_status"]),
                         ("2026-09-25T09:00:00-06:00", "2026-09-26T10:00:00-06:00", "blocked"))

    def test_a_scan_in_the_last_few_hours_is_fresh(self):
        # A Windows task's scan at 06:45 is what the 07:00 Cowork run goes through, rather than scanning again.
        self.folder.log_run({"at": "2026-09-26T06:45:00-06:00", "status": "ok", "boards": 589, "failed": 3})
        self.folder.log_run({"at": "2026-09-26T08:00:00-06:00", "status": "blocked", "boards": 0, "failed": 3})
        last_ok, _ = schedule.last_scans(self.folder.read_runs())
        at = lambda t: Clock("America/Denver", fixed=dt.datetime.fromisoformat(t))
        self.assertTrue(schedule.fresh(last_ok, at("2026-09-26T07:00:00-06:00")))
        self.assertFalse(schedule.fresh(last_ok, at("2026-09-26T13:00:00-06:00")))
        self.assertFalse(schedule.fresh({}, at("2026-09-26T07:00:00-06:00")))

    def test_the_windows_task(self):
        from jobkit import wintask
        # A path of the system the tests run on: the task is only ever made on Windows, and elsewhere
        # a Windows path reads as a relative one.
        folder = r"C:\Users\Sam\Job Search" if os.name == "nt" else "/home/sam/Job Search"
        xml = wintask.task_xml(folder, "06:45", weekdays=True, today=dt.date(2026, 10, 13))
        self.assertIn("<StartBoundary>2026-10-13T06:45:00</StartBoundary>", xml)
        self.assertIn("<Monday />", xml)
        self.assertNotIn("<Saturday />", xml)
        self.assertIn("<StartWhenAvailable>true</StartWhenAvailable>", xml)  # catches up after the computer sleeps
        self.assertIn("<LogonType>InteractiveToken</LogonType>", xml)       # no password kept
        self.assertIn(f'scan --folder "{folder}" --out', xml)
        self.assertIn("scan-latest.json", xml)
        # A run that reaches no board exits 4 (--fail-if-unreached), and Windows tries again.
        self.assertIn("--fail-if-unreached", xml)
        self.assertIn(f"<Interval>PT{wintask.RETRY_MINUTES}M</Interval>", xml)
        self.assertIn(f"<Count>{wintask.RETRIES}</Count>", xml)
        self.assertIn("<ScheduleByDay>", wintask.task_xml(r"C:\Sam", "07:00", today=dt.date(2026, 10, 13)))
        with self.assertRaises(configure.Refused):
            wintask._check_time("7am")
        if os.name != "nt":
            with self.assertRaises(configure.Refused):
                wintask.create(self.root, "06:45")

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
