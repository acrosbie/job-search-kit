"""The weekly work-search log: every job-search contact in a range of dates, as a spreadsheet the user
copies into their unemployment program's own form. Only what the user said; nothing filled in."""

import contextlib
import csv
import io
import json
import os

from jobkit import cli, export, interviews, track
from jobkit.errors import Refused
from tests.test_track import TrackBase, on


class WorklogTest(TrackBase):
    def setUp(self):
        super().setUp()
        self.folder.save_applications([])
        track.apply(self.root, on(14), key="greenhouse-acme-1", date="2026-09-14", channel="company_site", top_pick=True)
        track.apply(self.root, on(16), company="Globex", role="Support Lead", date="2026-09-15", estimated=True)
        track.apply(self.root, on(16), company="Initech", role="Head of Support", date="2026-09-08", channel="referral",
                    contact="Dana Example")
        track.track(self.root, on(16), "app-initech-head-of-support", "followed_up", date="2026-09-16")
        interviews.schedule(self.root, on(16), "greenhouse-acme-1", "2026-09-18T10:00", kind="phone",
                            who="Sam, recruiter", status="screen")
        interviews.schedule(self.root, on(16), "greenhouse-acme-1", "2026-09-25", status="interview")

    def rows(self, out):
        with open(os.path.join(self.root, *out["file"].split("/")), encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def test_one_week(self):
        out = export.worklog(self.root, on(20), "2026-09-13", "2026-09-19")
        self.assertEqual(out["file"], "exports/work-search 2026-09-13 to 2026-09-19.csv")
        rows = self.rows(out)
        self.assertEqual([(r["Date"], r["Employer"], r["Activity"]) for r in rows],
                         [("2026-09-14", "Acme", "Applied"), ("2026-09-15", "Globex", "Applied"),
                          ("2026-09-16", "Initech", "Followed up"), ("2026-09-18", "Acme", "Screen")])
        acme, globex, initech, screen = rows
        self.assertEqual((acme["How"], acme["Result so far"]), ("Online, on the company's website", "Interviewing"))
        self.assertEqual((globex["How"], globex["Note"]), ("Not recorded", "The date is approximate"))
        self.assertEqual(initech["Contact person"], "Dana Example")
        self.assertEqual((screen["How"], screen["Contact person"]), ("Phone", "Sam, recruiter"))
        self.assertEqual((out["rows"], out["not_recorded"], out["approximate_dates"]), (4, 1, 1))

    def test_an_interview_not_yet_held_says_so(self):
        rows = self.rows(export.worklog(self.root, on(20), "2026-09-20", "2026-09-26"))
        self.assertEqual([(r["Date"], r["Activity"], r["Note"]) for r in rows],
                         [("2026-09-25", "Interview", "Booked, not yet held")])

    def test_a_position_without_its_places(self):
        self.assertEqual(export.position("Director of Customer Support (United States; Remote)"), "Director of Customer Support")
        self.assertEqual(export.position("ServiceNow Admin (Blue Bell, PA (hybrid preferred; remote US considered))"),
                         "ServiceNow Admin")
        self.assertEqual(export.position("Customer Success Manager, Strategic Accounts (East)"),
                         "Customer Success Manager, Strategic Accounts (East)")

    def test_dates_are_checked(self):
        with self.assertRaises(Refused):
            export.worklog(self.root, on(20), "last week", "2026-09-19")
        with self.assertRaises(Refused):
            export.worklog(self.root, on(20), "2026-09-19", "2026-09-13")

    def test_from_the_command_line(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = cli.main(["export", "worklog", "--folder", self.root, "--from", "2026-09-01", "--to", "2026-09-30"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["by_activity"], {"Applied": 3, "Followed up": 1, "Screen": 1, "Interview": 1})
