"""Each company's process, and the people in it: who's asking in each round and what it's for, rounds
known to be coming with no day yet, the interviewers as contacts, and the thank-you after each round.

Found in real use (2026-10-13 and 14): the user couldn't thank Scentbird's Head of CX because her
email was never captured, BCM One had "a few more rounds" that lived only in chat, and Scentbird's
next round sat on the calendar all day until its time was added."""

import datetime as dt

from jobkit import contacts, interviews, page, start, track
from jobkit.clock import Clock
from jobkit.errors import Refused
from tests.test_interviews import CLOCK, InterviewBase


def at(day, hour=12):
    return Clock("", fixed=dt.datetime.fromisoformat(f"2026-{day}T{hour:02d}:00:00+00:00"))


def dos(out):
    return [n["do"] for n in out["next"]]


class ContactTest(InterviewBase):
    def test_a_person_is_one_record_and_only_what_the_user_gave(self):
        c = contacts.add(self.root, CLOCK, "Hannah", company="Scentbird", title="Head of CX", kind="interviewer",
                         source="interview")
        self.assertEqual((c["id"], c["email"]), ("c-hannah-scentbird", ""))
        again = contacts.add(self.root, CLOCK, "Hannah", company="Scentbird", email="hannah@scentbird.example")
        self.assertEqual((again["id"], again["title"], again["email"], again["kind"]),
                         ("c-hannah-scentbird", "Head of CX", "hannah@scentbird.example", "interviewer"))
        self.assertEqual(len(contacts.load(self.root)), 1)
        with self.assertRaises(Refused):
            contacts.add(self.root, CLOCK, "Hannah", company="Scentbird", email="hannah at scentbird")
        with self.assertRaises(Refused):
            contacts.add(self.root, CLOCK, "", company="Scentbird")
        self.assertIn("data/contacts.json", __import__("jobkit.store", fromlist=["x"]).SNAPSHOT_FILES)

    def test_a_message_is_a_touch_on_their_record(self):
        contacts.add(self.root, CLOCK, "Troy Hess", company="BCM One", kind="referrer")
        c = contacts.touch(self.root, CLOCK, "Troy Hess, BCM One", channel="linkedin", note="thanks for the referral")
        self.assertEqual(contacts.last_touch(c), "2026-09-24")
        with self.assertRaises(Refused):
            contacts.touch(self.root, CLOCK, "Troy Hess", channel="pigeon")


class RoundsTest(InterviewBase):
    def test_who_is_asking_and_what_it_is_for(self):
        out = interviews.schedule(self.root, CLOCK, self.app, "2026-09-28T10:00", who="Hannah", asker="head_of_function",
                                  purpose="the Head of CX's round", status="interview")
        self.assertEqual((out["asker"], out["for"]), ("head_of_function", "the Head of CX's round"))
        listed = interviews.listing(self.root, CLOCK)[0]
        self.assertEqual(listed["role"], "Customer Support Manager")  # the job's title is kept apart
        self.assertEqual(listed["asker"], "head_of_function")
        with self.assertRaises(Refused):
            interviews.schedule(self.root, CLOCK, self.app, "2026-09-29T10:00", asker="boss")

    def test_a_round_with_no_day_yet_waits_until_it_has_one(self):
        interviews.expect(self.root, CLOCK, self.app, "final round with the CEO", asker="executive")
        self.assertEqual([x["for"] for x in interviews.expected_rounds(self.root)], ["final round with the CEO"])
        out = interviews.schedule(self.root, CLOCK, self.app, "2026-10-02", asker="executive", status="interview")
        self.assertEqual(out["for"], "final round with the CEO")
        self.assertEqual(interviews.expected_rounds(self.root), [])
        # Saying it again with its time is the same round: nothing else is used up.
        interviews.expect(self.root, CLOCK, self.app, "a panel", asker="executive")
        interviews.schedule(self.root, CLOCK, self.app, "2026-10-02T15:00", asker="executive")
        self.assertEqual(len(interviews.expected_rounds(self.root)), 1)

    def test_the_time_is_asked_for_all_week(self):
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-30", status="interview")  # 6 days ahead, day only
        step = next(n for n in start.start(self.root, CLOCK)["next"] if n["do"] == "ask_interview_time")
        self.assertEqual(step["interview"]["on"], "2026-09-30")
        self.assertNotIn("offer_prep", dos(start.start(self.root, CLOCK)))  # prep is offered 3 days out

    def test_the_page_shows_who_and_why(self):
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-28T10:00", who="Paul Bloom", asker="executive",
                            purpose="meet the COO", status="interview")
        interviews.expect(self.root, CLOCK, self.app, "a panel with the team", asker="panel")
        data = page.build(self.root, CLOCK)
        self.assertEqual((data["coming_up"][0]["asker"], data["coming_up"][0]["for"]), ("executive", "meet the COO"))
        self.assertEqual([x["for"] for x in data["expected"]], ["a panel with the team"])


class ThanksTest(InterviewBase):
    def setUp(self):
        super().setUp()
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-25T10:00", who="Hannah", status="interview")
        c = contacts.add(self.root, CLOCK, "Hannah", company="Acme", title="Head of CX", kind="interviewer",
                         email="hannah@acme.example", source="interview", application=self.app)
        interviews.add_interviewer(self.root, CLOCK, self.app, "2026-09-25", c["id"])

    def test_the_day_after_a_round_the_thank_you_is_asked_about(self):
        due = interviews.thanks_due(self.root, at("09-26"))
        self.assertEqual([t["email"] for t in due[0]["to_thank"]], ["hannah@acme.example"])
        self.assertIn("ask_thank_you", dos(start.start(self.root, at("09-26"))))
        self.assertEqual(interviews.thanks_due(self.root, at("09-30")), [])  # four days on, let it go

    def test_once_sent_it_is_a_touch_and_not_asked_again(self):
        interviews.thanked(self.root, at("09-26"), self.app, contact="c-hannah-acme")
        self.assertEqual(interviews.thanks_due(self.root, at("09-26")), [])
        c = contacts.find(contacts.load(self.root), "c-hannah-acme")
        self.assertEqual(c["touches"][0]["note"], "thank-you after the 2026-09-25 interview")

    def test_none_is_an_answer_and_a_name_is_needed(self):
        with self.assertRaises(Refused):
            interviews.thanked(self.root, at("09-26"), self.app)
        interviews.thanked(self.root, at("09-26"), self.app, none=True)
        self.assertEqual(interviews.thanks_due(self.root, at("09-26")), [])

    def test_a_round_with_nobody_recorded_asks_who_they_met(self):
        interviews.schedule(self.root, CLOCK, self.app, "2026-09-26T10:00", status="interview")
        due = [t for t in interviews.thanks_due(self.root, at("09-27")) if t["on"].startswith("2026-09-26")]
        self.assertTrue(due[0]["nobody_recorded"])

    def test_from_the_command_line(self):
        code, out, err = self.run_cli("contact", "add", "--name", "Dana", "--company", "Acme", "--kind", "recruiter",
                                      "--application", self.app, "--round", "2026-09-25")
        self.assertEqual(code, 0, err)
        a = track.find(track.load(self.root), self.app)
        self.assertIn("c-dana-acme", a["upcoming"][0]["interviewers"])
        code, out, err = self.run_cli("interview", "thanked", self.app, "--none")
        self.assertEqual(code, 0, err)

    def run_cli(self, *args):
        import contextlib
        import io
        from jobkit import cli
        argv = [args[0], args[1], "--folder", self.root, *args[2:]]
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()


class PulledTest(InterviewBase):
    """Found in real use (2026-10-13): BCM One took its posting down on the day of the user's screen; the
    saved copy saved the prep."""

    def test_a_pulled_posting_is_said_once_and_shown_on_the_application(self):
        state = self.folder.load_postings()
        state["postings"]["greenhouse-acme-1"]["gone"] = "2026-09-23"
        self.folder.save_postings(state)
        step = next(n for n in start.start(self.root, CLOCK)["next"] if n["do"] == "say_posting_pulled")
        self.assertEqual(step["applications"][0]["gone"], "2026-09-23")
        self.assertTrue(step["applications"][0]["saved_copy"].startswith("data/postings/"))
        self.assertNotIn("say_posting_pulled", dos(start.start(self.root, CLOCK)))
        app = next(a for a in page.build(self.root, CLOCK)["applications"] if a["id"] == self.app)
        self.assertEqual(app["gone"], "2026-09-23")
