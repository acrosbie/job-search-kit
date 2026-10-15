"""On hold: a job turned away only by the cooldown waits for the day it ends, then comes back as what
it was held as. Found in real use (2026-10-12): the best find of the day, Toast #156, went to Screened
out with the rejects because the user had applied to Toast on 18 September."""

from jobkit import page, start, verdicts
from jobkit.errors import Refused
from tests.test_track import TrackBase, on


def dos(out):
    return [n["do"] for n in out["next"]]


class HoldTest(TrackBase):
    # TrackBase's Acme application is dated 2026-09-10, so with the default 30 days the wait ends 10-10.

    def posting(self, key="greenhouse-acme-1"):
        return self.folder.load_postings()["postings"][key]

    def test_the_wait_is_worked_out_from_the_application(self):
        self.assertEqual(verdicts.hold_until(self.root, "Acme", on(24)), "2026-10-10")
        self.assertEqual(verdicts.hold_until(self.root, "Globex", on(24)), "")
        row = verdicts.mark(self.root, "greenhouse-acme-1", "on_hold", "claude", note="Strong match", clock=on(24))
        self.assertEqual((row["until"], row["then"]), ("2026-10-10", "worth_applying"))
        p = self.posting()
        self.assertEqual((p["status"], p["hold_until"], p["hold_then"]), ("on_hold", "2026-10-10", "worth_applying"))

    def test_nothing_to_wait_for_is_refused(self):
        with self.assertRaises(Refused):
            verdicts.mark(self.root, "greenhouse-acme-1", "on_hold", "claude", until="2026-09-20", clock=on(24))
        with self.assertRaises(Refused):
            verdicts.mark(self.root, "greenhouse-acme-1", "on_hold", "claude", then="not_a_fit", clock=on(24))
        self.assertEqual(verdicts.hold_until(self.root, "Acme", on("10-11")), "")  # the wait is over

    def test_on_the_day_it_comes_back_and_is_said_once(self):
        verdicts.mark(self.root, "greenhouse-acme-1", "on_hold", "claude", then="your_call", clock=on(24))
        self.assertNotIn("say_holds_over", dos(start.start(self.root, on("10-09"))))
        out = start.start(self.root, on("10-10"))
        step = next(n for n in out["next"] if n["do"] == "say_holds_over")
        self.assertEqual([(j["key"], j["now"]) for j in step["jobs"]], [("greenhouse-acme-1", "your_call")])
        p = self.posting()
        self.assertEqual(p["status"], "your_call")
        self.assertNotIn("hold_until", p)
        last = self.folder.read_decisions()[-1]
        self.assertEqual((last["verdict"], last["by"], last["released"]), ("your_call", "claude", "2026-10-10"))
        self.assertNotIn("say_holds_over", dos(start.start(self.root, on("10-11"))))

    def test_another_verdict_ends_the_hold(self):
        verdicts.mark(self.root, "greenhouse-acme-1", "on_hold", "claude", clock=on(24))
        verdicts.mark(self.root, "greenhouse-acme-1", "worth_applying", "user", note="apply now", clock=on(25))
        self.assertNotIn("hold_until", self.posting())

    def test_the_page_lists_them_apart_from_the_rejects(self):
        verdicts.mark(self.root, "greenhouse-acme-1", "on_hold", "claude", clock=on(24))
        data = page.build(self.root, on(24))
        self.assertEqual([j["key"] for j in data["on_hold"]], ["greenhouse-acme-1"])
        self.assertEqual(data["on_hold"][0]["hold_until"], "2026-10-10")
        self.assertTrue(data["on_hold"][0]["num"])
        self.assertNotIn("greenhouse-acme-1", [j["key"] for j in data["screened"] + data["waiting"]])
        self.assertEqual(data["tracking"]["cooldown_days"], 30)

    def test_a_not_a_fit_from_before_is_offered_once(self):
        verdicts.mark(self.root, "greenhouse-acme-1", "not_a_fit", "claude", note="Rule 10 (cooldown)", clock=on(24))
        step = next(n for n in start.start(self.root, on(24))["next"] if n["do"] == "offer_holds")
        self.assertEqual([(j["key"], j["reopens"]) for j in step["jobs"]], [("greenhouse-acme-1", "2026-10-10")])
        self.assertNotIn("offer_holds", dos(start.start(self.root, on(24))))  # said once

    def test_the_users_own_not_a_fit_and_an_ended_wait_arent_offered(self):
        verdicts.mark(self.root, "greenhouse-acme-1", "not_a_fit", "user", note="not for me", clock=on(24))
        self.assertNotIn("offer_holds", dos(start.start(self.root, on(24))))
        verdicts.mark(self.root, "greenhouse-acme-4", "not_a_fit", "claude", note="cooldown", clock=on(24))
        self.assertNotIn("offer_holds", dos(start.start(self.root, on("10-11"))))

    def test_only_the_cooldown_rules_rejects_are_offered_when_rules_md_names_it(self):
        import os
        with open(os.path.join(self.root, "profile", "rules.md"), "w", encoding="utf-8") as f:
            f.write("# Rules\n\n### Rule 1: Commute\n- **Not a fit when:** far.\n\n"
                    "### Rule 2: Company cooldown\n- **Not a fit when:** applied in 30 days.\n")
        verdicts.mark(self.root, "greenhouse-acme-1", "not_a_fit", "claude", note="far", clock=on(24))
        verdicts.mark(self.root, "greenhouse-acme-4", "not_a_fit", "claude", note="wait", clock=on(24))
        state = self.folder.load_postings()  # the rule each rests on, as mark --rule keeps it
        state["postings"]["greenhouse-acme-1"]["rule"], state["postings"]["greenhouse-acme-4"]["rule"] = "rule 1", "rule 2"
        self.folder.save_postings(state)
        step = next(n for n in start.start(self.root, on(24))["next"] if n["do"] == "offer_holds")
        self.assertEqual([j["key"] for j in step["jobs"]], ["greenhouse-acme-4"])

    def test_the_queue_says_when_the_wait_ends(self):
        from jobkit import queue
        q = queue.queue(self.root, on(24))
        recent = next(p for p in q["postings"] if p["key"] == "greenhouse-acme-1")["applied_recently_at_company"]
        self.assertEqual(recent[0]["reopens"], "2026-10-10")

    def test_from_the_command_line(self):
        # The command line runs on today's date, when the fixture's wait (to 2026-10-10) is long over.
        code, _, err = self.run_cli("mark", "greenhouse-acme-1", "on_hold", "--by", "claude")
        self.assertEqual(code, 3, err)
        self.assertIn("nothing to wait for", err)
        code, out, err = self.run_cli("mark", "greenhouse-acme-1", "on_hold", "--by", "claude", "--then", "your_call",
                                      "--until", "2099-01-01")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.posting()["hold_then"], "your_call")
