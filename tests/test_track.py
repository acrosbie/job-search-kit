"""Applications: recording them, what happens next, and the follow-ups and day-21 close that follow
from them. Uses the made-up Denver support manager and Acme board from test_scan."""

import contextlib
import datetime as dt
import io
import json

from jobkit import cli, track
from jobkit.clock import Clock
from tests.test_scan import FIXED, ScanBase


def on(day):
    """The clock at noon UTC on 2026-09-<day>, or a later month's date given as 'MM-DD'."""
    md = day if isinstance(day, str) else f"09-{day:02d}"
    return Clock("", fixed=dt.datetime.fromisoformat(f"2026-{md}T12:00:00+00:00"))


class TrackBase(ScanBase):
    def setUp(self):
        super().setUp()
        self.scan()

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main([args[0], "--folder", self.root, *args[1:]])
        return code, out.getvalue(), err.getvalue()

    def apps(self):
        return {a["id"]: a for a in track.load(self.root)}


class ApplyTest(TrackBase):
    def test_apply_records_the_application_and_the_verdict(self):
        a = track.apply(self.root, on(24), key="greenhouse-acme-1", channel="company_site", top_pick=True)
        self.assertTrue(a["created"])
        self.assertEqual((a["company"], a["role"], a["applied_date"], a["status"]),
                         ("Acme", "Customer Support Manager", "2026-09-24", "applied"))
        self.assertEqual(a["urls"], ["https://acme.test/1"])
        self.assertEqual(a["level"], "manager")
        self.assertEqual(a["history"][0]["status"], "applied")
        self.assertEqual(a["history"][0]["by"], "user")
        posting = self.folder.load_postings()["postings"]["greenhouse-acme-1"]
        self.assertEqual(posting["status"], "applied")
        last = self.folder.read_decisions()[-1]
        self.assertEqual((last["key"], last["verdict"], last["by"]), ("greenhouse-acme-1", "applied", "user"))
        with open(self.folder.applications_json, encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["applications"]), 2)  # this one, and the one from test_scan

    def test_saying_it_twice_updates_one_record(self):
        track.apply(self.root, on(20), key="greenhouse-acme-1")
        again = track.apply(self.root, on(24), key="greenhouse-acme-1", date="2026-09-18", contact="Dana Example")
        self.assertFalse(again["created"])
        a = self.apps()["greenhouse-acme-1"]
        self.assertEqual((a["applied_date"], a["contact"]), ("2026-09-18", "Dana Example"))
        self.assertEqual(sum(1 for d in self.folder.read_decisions() if d["verdict"] == "applied"), 1)

    def test_an_application_without_a_saved_posting(self):
        a = track.apply(self.root, on(24), company="Globex", role="Head of Support", channel="referral")
        self.assertEqual(a["id"], "app-globex-head-of-support")
        self.assertEqual(a["key"], "")

    def test_refusals(self):
        code, _, err = self.run_cli("mark", "greenhouse-acme-1", "applied", "--by", "claude")
        self.assertEqual(code, 3)
        self.assertIn("only the user", err)
        how = ("--channel", "linkedin", "--top-pick", "not_sure")
        self.assertEqual(self.run_cli("apply", "no-such-key", *how)[0], 1)
        code, _, err = self.run_cli("apply", "greenhouse-acme-1", "--date", "2027-01-01", *how)
        self.assertEqual(code, 3)
        self.assertIn("after today", err)
        self.assertEqual(self.run_cli("apply", "--company", "Globex", *how)[0], 3)
        # How they applied and whether it's a top pick are asked, every time: without them nothing
        # about how applications fare can be counted, and a top pick is never routed to a person.
        code, _, err = self.run_cli("apply", "greenhouse-acme-1")
        self.assertEqual(code, 3)
        self.assertIn("--top-pick yes|no|not_sure", err)
        self.assertEqual(list(self.apps()), [track.app_id("Acme", "Head of Support Operations Manager")])

    def test_applied_goes_through_apply_with_how_and_top_pick(self):
        code, _, err = self.run_cli("mark", "greenhouse-acme-4", "applied", "--by", "user", "--note", "sent today")
        self.assertEqual(code, 3)
        self.assertNotIn("greenhouse-acme-4", self.apps())
        code, out, _ = self.run_cli("apply", "greenhouse-acme-4", "--channel", "not_sure", "--top-pick", "not_sure")
        self.assertEqual(code, 0)
        a = self.apps()["greenhouse-acme-4"]
        self.assertEqual((a["channel"], a["top_pick"]), ("", None))


    def test_two_long_roles_stay_two_applications(self):
        # Found in a bug hunt: ids cut the role at 40 characters, so East and West became one.
        east = track.apply(self.root, on(20), company="Acme", role="Senior Customer Success Manager, Strategic Accounts (East)")
        west = track.apply(self.root, on(21), company="Acme", role="Senior Customer Success Manager, Strategic Accounts (West)")
        self.assertNotEqual(east["id"], west["id"])
        self.assertTrue(west["created"])
        self.assertEqual(track.app_id("Globex", "Head of Support"), "app-globex-head-of-support")  # short ones unchanged

    def test_an_application_recorded_before_long_ids_is_still_found(self):
        role = "Senior Customer Success Manager, Strategic Accounts (East)"
        state = track.load(self.root)
        state.append(track.normalize({"id": track._legacy_app_id("Acme", role), "company": "Acme", "role": role,
                                      "applied_date": "2026-09-10", "status": "applied"}))
        track.save(self.root, state)
        again = track.apply(self.root, on(22), company="Acme", role=role, channel="referral")
        self.assertFalse(again["created"])
        self.assertEqual(again["channel"], "referral")

    def test_a_click_never_moves_the_date_already_recorded(self):
        # Found in a bug hunt: "I applied" clicked on an old page restarted the 21-day clock.
        track.apply(self.root, on(1), key="greenhouse-acme-1", date="2026-09-01")
        a = track.apply(self.root, on(7), key="greenhouse-acme-1", date="2026-09-07", choice="c-1")
        self.assertEqual(a["applied_date"], "2026-09-01")
        a = track.apply(self.root, on(7), key="greenhouse-acme-1", date="2026-09-02")  # the user correcting it
        self.assertEqual(a["applied_date"], "2026-09-02")

    def test_an_old_application_by_name_isnt_joined_to_a_new_opening(self):
        from jobkit import add
        track.apply(self.root, on("06-01"), company="Acme", role="Customer Support Manager", date="2026-06-01")
        state = self.folder.load_postings()
        state["postings"]["greenhouse-acme-1"]["status"] = "worth_applying"
        self.folder.save_postings(state)
        self.assertIsNone(track.link(self.root, on(24), "greenhouse-acme-1"))  # same title, four months later
        self.assertEqual(self.folder.load_postings()["postings"]["greenhouse-acme-1"]["status"], "worth_applying")
        track.apply(self.root, on(20), company="Acme", role="Customer Support Manager", date="2026-09-20")
        self.assertIsNotNone(track.link(self.root, on(24), "greenhouse-acme-1"))  # four days later: the same one


class TrackStatusTest(TrackBase):
    def setUp(self):
        super().setUp()
        track.apply(self.root, on(1), key="greenhouse-acme-1", date="2026-09-01")

    def test_statuses_build_a_history(self):
        track.track(self.root, on(10), "greenhouse-acme-1", "replied", note="recruiter email")
        track.track(self.root, on(12), "greenhouse-acme-1", "screen", date="2026-09-12")
        a = track.track(self.root, on(12), "greenhouse-acme-1", contact="Dana Example")
        self.assertEqual(a["status"], "screen")
        self.assertEqual([h.get("status") or h.get("event") for h in a["history"]],
                         ["applied", "replied", "screen", "contact"])
        self.assertEqual(a["history"][1]["note"], "recruiter email")

    def test_a_screen_needs_its_day(self):
        code, _, err = self.run_cli("track", "greenhouse-acme-1", "screen")
        self.assertEqual(code, 3)
        self.assertIn("--on", err)
        self.assertEqual(self.run_cli("track", "greenhouse-acme-1", "screen", "--time-unknown")[0], 0)
        self.assertEqual(self.apps()["greenhouse-acme-1"]["status"], "screen")

    def test_an_interview_booked_without_a_stage_cant_close_at_day_21(self):
        # Found in a bug hunt: --on with no status left the application at "applied".
        from jobkit import interviews
        interviews.schedule(self.root, on(10), "greenhouse-acme-1", "2026-09-25T10:00")
        self.assertEqual(self.apps()["greenhouse-acme-1"]["status"], "interview")
        closed = [a["id"] for a in track.close_due(self.root, on("10-01"))]
        self.assertNotIn("greenhouse-acme-1", closed)
        self.assertEqual(self.apps()["greenhouse-acme-1"]["status"], "interview")

    def test_a_follow_up_is_an_event_not_a_status(self):
        a = track.track(self.root, on(7), "greenhouse-acme-1", "followed_up")
        self.assertEqual((a["status"], a["followed_up"]), ("applied", "2026-09-07"))

    def test_only_the_engine_presumes(self):
        with self.assertRaises(track.Refused):
            track.track(self.root, on(7), "greenhouse-acme-1", "presumed_rejected")
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stderr(io.StringIO()):
            cli.main(["track", "--folder", self.root, "greenhouse-acme-1", "presumed_rejected"])
        self.assertEqual(stop.exception.code, 2)  # not one of the command's choices

    def test_nothing_to_record(self):
        self.assertEqual(self.run_cli("track", "greenhouse-acme-1")[0], 3)
        self.assertEqual(self.run_cli("track", "nope", "replied")[0], 1)


class DueTest(TrackBase):
    def setUp(self):
        super().setUp()
        self.folder.save_applications([])
        # Three applications sent on 09-01: one with a contact, one a top pick, one neither.
        track.apply(self.root, on(1), key="greenhouse-acme-1", date="2026-09-01", contact="Dana Example")
        track.apply(self.root, on(1), key="greenhouse-acme-4", date="2026-09-01", top_pick=True)
        track.apply(self.root, on(1), key="greenhouse-acme-9", date="2026-09-01", top_pick=False)

    def test_routes(self):
        out = track.due(self.root, on(8))
        self.assertEqual([r["id"] for r in out["send"]], ["greenhouse-acme-1"])
        self.assertEqual([r["id"] for r in out["find_person"]], ["greenhouse-acme-4"])
        self.assertIn("greenhouse-acme-9", [r["id"] for r in out["closing"]])
        self.assertEqual(out["closing"][0]["closes_on"], "2026-09-22")
        self.assertEqual(out["closed_now"], [])

    def test_not_due_before_day_five_or_after_a_follow_up(self):
        self.assertEqual(track.due(self.root, on(5))["send"], [])
        self.assertEqual(len(track.due(self.root, on(6))["send"]), 1)
        track.track(self.root, on(6), "greenhouse-acme-1", "followed_up")
        self.assertEqual(track.due(self.root, on(7))["send"], [])

    def test_day_21_closes_only_plain_applied(self):
        track.track(self.root, on(15), "greenhouse-acme-1", "screen")
        track.track(self.root, on(15), "greenhouse-acme-4", "followed_up")
        self.assertEqual(track.due(self.root, on(21))["closed_now"], [])  # day 20
        out = track.due(self.root, on(22))
        self.assertEqual(sorted(r["id"] for r in out["closed_now"]), ["greenhouse-acme-4", "greenhouse-acme-9"])
        a = self.apps()
        self.assertEqual(a["greenhouse-acme-1"]["status"], "screen")
        self.assertEqual(a["greenhouse-acme-4"]["status"], "presumed_rejected")
        self.assertEqual(a["greenhouse-acme-4"]["history"][-1]["by"], "engine")
        self.assertEqual(a["greenhouse-acme-4"]["history"][-1]["date"], "2026-09-22")
        self.assertEqual(track.due(self.root, on(23))["closed_now"], [])  # once only

    def test_every_protected_status_survives(self):
        for i, status in zip((1, 4, 9), ("replied", "offer", "withdrawn")):
            track.track(self.root, on(10), f"greenhouse-acme-{i}", status)
        track.apply(self.root, on(10), company="Globex", role="Support Director", date="2026-09-01")
        for status in ("interview", "rejected", "closed"):
            track.track(self.root, on(10), "app-globex-support-director", status)
            self.assertEqual(track.due(self.root, on("10-30"))["closed_now"], [])
        self.assertEqual(self.apps()["app-globex-support-director"]["status"], "closed")

    def test_a_late_reply_replaces_presumed(self):
        track.due(self.root, on(25))
        a = track.track(self.root, on(28), "greenhouse-acme-9", "replied")
        self.assertEqual(a["status"], "replied")
        self.assertEqual([h.get("status") for h in a["history"]], ["applied", "presumed_rejected", "replied"])

    def test_the_users_time_zone_decides_the_day(self):
        # 03:00 UTC on 09-22 is still 09-21 in Denver: day 20, nothing closes yet.
        late = Clock("America/Denver", fixed=dt.datetime(2026, 9, 22, 3, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(track.due(self.root, late)["closed_now"], [])


class ScanClosesTest(TrackBase):
    def test_a_scan_runs_the_day_21_close(self):
        from jobkit import net
        from tests.test_scan import Fake, answers
        self.folder.save_applications([])
        track.apply(self.root, on(1), key="greenhouse-acme-1", date="2026-09-01")
        track.apply(self.root, on(10), key="greenhouse-acme-4", date="2026-09-10", contact="Dana Example")
        self.addCleanup(net.use, net.use(Fake(answers())))
        code, out, _ = self.run_cli("scan", "--as-of", FIXED.isoformat())
        self.assertEqual(code, 0)
        summary = json.loads(out)
        self.assertEqual([a["id"] for a in summary["closed_day_21"]], ["greenhouse-acme-1"])
        self.assertEqual(summary["follow_ups_due"], {"send": 1, "find_person": 0, "closing": 0})


class LegacyTest(TrackBase):
    def test_older_rows_are_read_in_the_current_shape(self):
        with open(self.folder.applications_json, "w", encoding="utf-8") as f:
            json.dump({"applications": [
                {"company": "Acme", "role": "Lead", "urls": [], "fit": "**Strong**", "applied": "2026-09-01",
                 "applied_date": "2026-09-01", "followed_up": "", "status": "**presumed rejected**"},
                {"company": "Globex", "role": "Manager", "urls": [], "fit": "Fair", "applied": "2w",
                 "applied_date": "", "status": "reply 2026-09-20"},
            ]}, f)
        a = {x["company"]: x for x in track.load(self.root)}
        self.assertEqual((a["Acme"]["status"], a["Acme"]["top_pick"], a["Acme"]["id"]),
                         ("presumed_rejected", True, "app-acme-lead"))
        self.assertEqual((a["Globex"]["status"], a["Globex"]["top_pick"]), ("replied", False))
        self.assertEqual(track.due(self.root, on(30))["closed_now"], [])  # no date, never closed

    def test_scan_still_flags_an_application(self):
        self.assertIn("already applied here on 2026-09-10",
                      self.folder.load_postings()["postings"]["greenhouse-acme-9"]["flag"])


if __name__ == "__main__":
    import unittest
    unittest.main()
