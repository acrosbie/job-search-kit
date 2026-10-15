"""Offers side by side: what each company said or wrote, the first year all in, and the base against the
user's ask, walk-away number and last job. Arithmetic on the numbers the user gave, never a guess.

Found in real use (2026-10-14): two processes live, Scentbird ($130K, maybe $145K) and BCM One ($150K
top, plus a 401(k) match), against a $180K ask, after a last job at $180K base plus RSUs."""

import os

from jobkit import offers, page, track
from jobkit.errors import Refused
from tests.test_interviews import CLOCK, InterviewBase


class OffersTest(InterviewBase):
    def setUp(self):
        super().setUp()
        self.other = track.apply(self.root, CLOCK, company="Globex", role="Support Systems Lead", channel="referral",
                                 top_pick=True)["id"]

    def test_side_by_side_against_the_ask_and_walk_away(self):
        offers.record(self.root, CLOCK, self.app, base_low=130000, base_high=145000, note="recruiter: 130, maybe 145")
        offers.record(self.root, CLOCK, self.other, base_high=150000, k401="4% match", travel="heavier at launch")
        out = offers.compare(self.root, ask=180000, walk_away=150000, last_base=180000)
        first, second = out["offers"]  # the higher base first
        self.assertEqual((first["company"], first["base_top_vs_ask"], first["base_top_meets_walk_away"]),
                         ("Globex", -30000, True))
        self.assertEqual((second["company"], second["base_top_vs_ask"], second["base_top_meets_walk_away"]),
                         ("Acme", -35000, False))
        self.assertEqual(second["base_top_vs_last"], -35000)
        with open(os.path.join(self.root, *out["file"].split("/")), encoding="utf-8") as f:
            table = f.read()
        self.assertIn("| Base | $150K | $130K to $145K |", table)
        self.assertIn("below it, even at the top", table)
        self.assertIn("Arithmetic, not a prediction", table)

    def test_the_first_year_all_in(self):
        offers.record(self.root, CLOCK, self.app, base=150000, bonus=15000, k401_yearly=6000, stage="written",
                      deadline="2026-10-24")
        r = offers.compare(self.root)["offers"][0]
        self.assertEqual((r["first_year_low"], r["first_year_high"], r["stage"]), (171000, 171000, "written"))
        self.assertIsNone(r["base_top_vs_ask"])  # no ask given, no comparison made up

    def test_a_written_offer_replaces_what_was_said(self):
        offers.record(self.root, CLOCK, self.app, base_low=130000, base_high=145000, travel="some")
        offers.record(self.root, CLOCK, self.app, base=140000, stage="written")
        o = track.find(track.load(self.root), self.app)["offer"]
        self.assertEqual((o["base_low"], o["base_high"], o.get("travel")), (140000, 140000, None))

    def test_numbers_are_checked(self):
        with self.assertRaises(Refused):
            offers.record(self.root, CLOCK, self.app, base_low=150000, base_high=130000)
        with self.assertRaises(Refused):
            offers.record(self.root, CLOCK, self.app, base=150000, deadline="next Friday")

    def test_the_page_says_it_on_the_application(self):
        offers.record(self.root, CLOCK, self.other, base_high=150000, k401="4% match")
        app = next(a for a in page.build(self.root, CLOCK)["applications"] if a["id"] == self.other)
        self.assertEqual(app["offer"], "Said: $150K base, 4% match")
