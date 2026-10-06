"""The weekly review's facts. Builds on the rules.md and the two overturns of Rule 2 in test_rule_change."""

import datetime as dt
import os

from jobkit import review, rules, schedule, settings, track, verdicts
from jobkit.clock import Clock
from tests.test_rule_change import CLOCK, RuleBase
from tests.test_scan import FIXED


def later(days):
    return Clock("", fixed=FIXED + dt.timedelta(days=days))


class DisagreementTest(RuleBase):
    def groups(self, clock=CLOCK):
        return {g["rule"]: g for g in review.build(self.root, clock)["disagreements"]}

    def test_two_overturns_of_one_rule_bring_a_proposal(self):
        g = self.groups()["rule 2"]
        self.assertEqual((g["label"], g["since_last_change"], g["propose"]), ("Rule 2 (Owns the queue)", 2, True))
        self.assertEqual({o["their_words"] for o in g["overturns"]}, {"leading the queue is fine"})
        self.assertTrue(g["overturns"][0]["rule_said"].startswith("Rule 2 (Owns the queue)"))
        self.assertEqual(review.build(self.root, CLOCK)["to_raise"], 1)

    def test_a_change_starts_the_count_afresh(self):
        replay = self.file("r.json", {"checked": [], "flips": []})
        rules.change(self.root, later(1), n=2, text_file=self.file("t.md", "- Not a fit when: works only the queue.\n"),
                     why="leading the queue is fine", replay_file=replay)
        g = self.groups(later(1))["rule 2"]
        self.assertEqual((g["since_last_change"], g["propose"], g["last_changed"]), (0, False, "2026-09-25"))

    def test_a_declined_proposal_stays_quiet_for_four_weeks(self):
        rules.decline(self.root, CLOCK, "rule 2", "not now")
        self.assertFalse(self.groups()["rule 2"]["propose"])
        self.assertTrue(self.groups(later(29))["rule 2"]["propose"])

    def test_scan_rules_and_claudes_verdicts_are_grouped_too(self):
        verdicts.mark(self.root, "greenhouse-acme-3", "worth_applying", "user", note="Austin is fine, hybrid", clock=CLOCK)
        verdicts.mark(self.root, "greenhouse-acme-9", "skipped", "user", note="candidate rule: too senior", clock=CLOCK)
        g = self.groups()
        self.assertEqual((g["location_in_country"]["since_last_change"], g["location_in_country"]["propose"]), (1, False))
        self.assertIn("Where the job is", g["location_in_country"]["label"])
        self.assertFalse(g["claude: worth_applying"]["propose"])  # no rule to rewrite; it's a candidate rule
        out = review.build(self.root, CLOCK)
        self.assertEqual([c["their_words"] for c in out["candidate_rules"]], ["candidate rule: too senior"])
        self.assertEqual(out["to_raise"], 2)


class ActivityTest(RuleBase):
    def test_how_often_each_rule_fired(self):
        a = review.build(self.root, CLOCK)["rule_activity"]
        fires = {f["rule"]: f["count"] for f in a["fires"]}
        self.assertEqual(fires, {"rule 2": 2, "location_in_country": 1, "phrases:quota": 1, "pay": 1})
        self.assertEqual((a["top"]["rule"], a["top"]["share"]), ("rule 2", 0.4))
        self.assertEqual(a["never_fired"], [])  # the search is too new to say

    def test_rules_that_never_fired(self):
        replay = self.file("r.json", {"checked": [], "flips": []})
        rules.change(self.root, later(31), n=3, why="never comes up", replay_file=replay, retire=True)
        a = review.build(self.root, later(31))["rule_activity"]
        self.assertEqual([n["rule"] for n in a["never_fired"]], ["rule 1", "rule 2"])  # retired Rule 3 isn't listed


class SpotCheckAndHealthTest(RuleBase):
    def test_spot_check_is_the_scans_rejects_and_stable(self):
        first = review.build(self.root, CLOCK)["spot_check"]
        self.assertEqual(sorted(x["key"] for x in first), ["greenhouse-acme-3", "greenhouse-acme-5", "greenhouse-acme-6"])
        self.assertEqual(first, review.build(self.root, CLOCK)["spot_check"])
        self.assertTrue(all(x["reason"].startswith("Not a fit") for x in first))

    def test_pipeline_and_health_are_included(self):
        out = review.build(self.root, CLOCK)
        self.assertIn("find_person", out["pipeline"])
        self.assertEqual(set(out["scan_health"]), {"failing", "silent", "at_cap"})
        self.assertFalse(out["monthly"])


class MonthlyTest(RuleBase):
    def test_outcomes_counts_only(self):
        self.folder.save_applications([])
        track.apply(self.root, CLOCK, key="greenhouse-acme-9", channel="company_site", top_pick=True)
        track.apply(self.root, CLOCK, key="greenhouse-acme-1", channel="linkedin")
        track.track(self.root, later(3), "greenhouse-acme-1", "screen")
        out = review.build(self.root, later(30), monthly=True)
        o = out["outcomes"]
        self.assertEqual((o["applications"], o["totals"]), (2, {"no_reply": 1, "answered": 1}))
        self.assertEqual(o["by"]["verdict"], {"worth_applying": {"no_reply": 1}, "not_a_fit": {"answered": 1}})
        self.assertEqual(o["by"]["channel"]["linkedin"], {"answered": 1})

    def test_profile_refresh(self):
        with open(os.path.join(self.root, "profile", "about-me.md"), "w", encoding="utf-8") as f:
            f.write("# About me\n\n## Confirmed\n| a | b |\n\n## Not confirmed yet (never use in an application)\n- Led a team of 30\n- Owns Zendesk\n\n## Owned hands-on\n")
        with open(os.path.join(self.root, "profile", "what-i-want.md"), "w", encoding="utf-8") as f:
            f.write("# What I want\n\n| Question | My answer | Date |\n|---|---|---|\n| Pay | 120000 | 2026-09-20 |\n| Place | Denver | 2026-09-21 |\n")
        p = review.build(self.root, CLOCK, monthly=True)["profile_refresh"]
        self.assertEqual(p, {"unconfirmed": ["Led a team of 30", "Owns Zendesk"], "answers": 2, "oldest_answer": "2026-09-20"})


class PrepareTest(RuleBase):
    def test_prepared_then_done(self):
        s = settings.load(self.root)
        review.prepare(self.root, CLOCK)
        self.assertEqual(self.folder.read_json(self.folder.review_json)["to_raise"], 1)
        self.assertEqual(schedule.review_state(self.root, s, CLOCK)[0], "2026-09-24")
        review.finish(self.root, later(1))
        self.assertEqual(schedule.review_state(self.root, s, later(1))[0], "")
        self.assertEqual(review.build(self.root, later(2))["since"], "2026-09-25")


if __name__ == "__main__":
    import unittest
    unittest.main()
