"""Interviews: scheduling one on its application, its calendar file, what's coming up and what needs
a debrief, the check on a prep sheet, and the pay the saved postings state. On test_scan's made-up
boards, with Morgan's about-me.md (the made-up accounting manager) for the check."""

import datetime as dt
import os
import shutil

from jobkit import interviews, page, review, track
from jobkit.clock import Clock
from jobkit.errors import Refused
from tests.test_scan import FIXED, ScanBase

CLOCK = Clock("", fixed=FIXED)  # 2026-09-24 18:00 UTC
PERSONA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "personas", "accounting-manager-denver")


class InterviewBase(ScanBase):
    def setUp(self):
        super().setUp()
        self.scan()
        self.folder.save_applications([])
        self.app = track.apply(self.root, CLOCK, key="greenhouse-acme-1", channel="company_site", top_pick=True)["id"]

    def read(self, rel):
        with open(os.path.join(self.root, *rel.split("/")), encoding="utf-8", newline="") as f:
            return f.read()


class ScheduleTest(InterviewBase):
    def test_a_screen_is_kept_on_its_application_with_a_calendar_file(self):
        out = interviews.schedule(self.root, CLOCK, self.app, "2026-09-26T10:00", kind="phone", who="Dana, recruiter",
                                  status="screen")
        self.assertEqual((out["on"], out["kind"], out["with"], out["minutes"], out["stage"]),
                         ("2026-09-26T10:00", "phone", "Dana, recruiter", 30, "screen"))
        self.assertEqual(out["calendar"], "interviews/Acme - Customer Support Manager/2026-09-26 screen.ics")
        self.assertEqual(out["prep"], "interviews/Acme - Customer Support Manager/prep.md")
        a = track.find(track.load(self.root), self.app)
        self.assertEqual(a["status"], "screen")
        self.assertEqual([h.get("event") or h.get("status") for h in a["history"]], ["applied", "screen", "interview_scheduled"])

        ics = self.read(out["calendar"])
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n"))
        start = dt.datetime(2026, 9, 26, 10, 0, tzinfo=CLOCK.now().tzinfo).astimezone(dt.timezone.utc)
        self.assertIn(f"DTSTART:{start:%Y%m%dT%H%M%SZ}\r\n", ics)
        self.assertIn(f"DTEND:{start + dt.timedelta(minutes=30):%Y%m%dT%H%M%SZ}\r\n", ics)
        self.assertIn("SUMMARY:Acme: phone screen with Dana\\, recruiter\r\n", ics)
        self.assertTrue(all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n")))

    def test_saying_it_again_updates_the_same_day(self):
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-26T10:00", status="screen")
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-26T11:30", kind="video", minutes=45)
        a = track.find(track.load(self.root), self.app)
        self.assertEqual([(e["on"], e["kind"], e["minutes"]) for e in a["upcoming"]], [("2026-09-26T11:30", "video", 45)])

    def test_a_date_alone_is_an_all_day_event(self):
        out = interviews.schedule(self.root, CLOCK, self.app, "2026-09-29")
        self.assertIn("DTSTART;VALUE=DATE:20260929\r\n", self.read(out["calendar"]))
        self.assertEqual(out["stage"], "interview")

    def test_what_isnt_a_time(self):
        for bad in ("tomorrow", "2026-09-31", "2026-09-26T25:00", "26/09/2026"):
            with self.assertRaises(Refused):
                interviews.parse_on(bad)
        with self.assertRaises(Refused):
            interviews.schedule(self.root, CLOCK, self.app, "2026-09-26", kind="carrier pigeon")

    def test_coming_up_and_debriefs(self):
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-20T09:00", status="screen")   # held, not gone through
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-26T10:00", status="interview")  # in two days
        soon = interviews.soon(self.root, CLOCK)
        self.assertEqual([(x["on"], x["days"]) for x in soon], [("2026-09-26T10:00", 2)])
        self.assertEqual([x["on"] for x in interviews.debrief_due(self.root, CLOCK)], ["2026-09-20T09:00"])

        # Found in phase 5b: a debrief was marked done with nothing written. Now it's written first.
        from jobkit.errors import Refused
        with self.assertRaises(Refused):
            interviews.debriefed(self.root, CLOCK, self.app)
        a = track.find(track.load(self.root), self.app)
        prep = os.path.join(self.root, *interviews.folder_for(a).split("/"), "prep.md")
        with open(prep, "w", encoding="utf-8") as f:
            f.write("# Prep\n\n## Debrief, 2026-09-24\n\n")
        with self.assertRaises(Refused):  # a heading with nothing under it isn't a debrief
            interviews.debriefed(self.root, CLOCK, self.app)
        with open(prep, "a", encoding="utf-8") as f:
            f.write("They asked about the month-end close. Next: a panel.\n")
        interviews.debriefed(self.root, CLOCK, self.app)
        self.assertEqual(interviews.debrief_due(self.root, CLOCK), [])
        self.assertEqual([x["on"] for x in page.build(self.root, CLOCK)["coming_up"]], ["2026-09-26T10:00"])

    def test_a_moved_interview(self):
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-26T10:00", status="interview")
        interviews.cancel(self.root, CLOCK, self.app, "2026-09-26")
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-29T14:00")
        self.assertEqual([x["on"] for x in interviews.listing(self.root, CLOCK)], ["2026-09-29T14:00"])

    def test_folder_names_lose_what_windows_refuses(self):
        self.assertEqual(interviews.folder_for({"company": "Glo/bex", "role": "Senior Manager, Customer Service "
                                                "(United States; Remote) ([posting](https://example.test/1))"}),
                         "interviews/Globex - Senior Manager, Customer Service")


class CheckTest(InterviewBase):
    def setUp(self):
        super().setUp()
        shutil.copy(os.path.join(PERSONA, "about-me.md"), os.path.join(self.root, "profile", "about-me.md"))

    def check(self, body):
        path = os.path.join(self.root, "prep.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return interviews.check(self.root, path)

    def test_claims_trace_and_the_rest_is_free(self):
        out = self.check(
            "# Acme: recruiter screen\n\n"
            "## The company\nAcme sells support software to 4,000 teams.\n\n"
            "## Opener\nI run a month-end close cut from 10 business days to 6, with a team of 4.\n"
            "from: Cut the month-end close from 10 business days to 6\nfrom: 4 direct reports at Peakline\n\n"
            "## Answers\n### Why NetSuite?\nI led a team of 8 through the move to NetSuite.\n"
            "from: Ran the QuickBooks to NetSuite migration\n"
            "- I partnered with the revenue accountant on ASC 606.\n"
            "  from: Worked alongside the revenue accountant on ASC 606\n\n"
            "## Gaps\nNo SOX: we're private.\n\n"
            "## Questions to ask\n- What does the first 90 days look like?\n")
        self.assertEqual((out["lines"], out["traced"], out["flagged"]), (4, 2, 2))
        bad = {it["text"][:20]: [p["kind"] for p in it["problems"]] for it in out["items"] if not it["ok"]}
        self.assertEqual(bad, {"I led a team of 8 th": ["number"], "No SOX: we're privat": ["no_source"]})

    def test_a_badly_made_file(self):
        from jobkit.errors import BadFile
        with self.assertRaises(BadFile):
            self.check("## Opener\nfrom: a source under a heading\n")


class PayTest(InterviewBase):
    def test_what_the_postings_state(self):
        state = self.folder.load_postings()
        pays = {"greenhouse-acme-1": "$120K to $150K", "greenhouse-acme-4": "$140K to $190K", "greenhouse-acme-9": "$160K to $210K"}
        for k, v in state["postings"].items():
            v.pop("pay_low", None), v.pop("pay_high", None)
            v["salary"] = pays.get(k, "")
        self.folder.save_postings(state)
        out = interviews.pay(self.root, ask=185000)
        self.assertEqual(out["all"]["with_pay"], 3)
        self.assertEqual(out["all"]["top"], {"lowest": 150000, "lower_quarter": 150000, "middle": 190000,
                                             "upper_quarter": 210000, "highest": 210000})
        self.assertEqual((out["all"]["tops_below_ask"], out["all"]["tops_reaching_ask"]), (1, 2))
        self.assertEqual(out["worth_a_look_or_applied"]["with_pay"], 1)  # the one applied to
        self.assertIn("Not a prediction", out["note"])


class OutcomesTest(InterviewBase):
    def test_tailored_or_not(self):
        apps = track.load(self.root)
        out = review.outcomes(apps, [], tailored={"greenhouse-acme-1"})
        self.assertEqual(out["by"]["tailored_resume"], {"yes": {"open": 1}})
