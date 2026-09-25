"""Screening rules, on a made-up job seeker: a support manager in Denver who will commute within
the metro, would take a Boulder job only if remote, and has a $90K pay line."""

import unittest

from jobkit import screen, settings
from jobkit.toml import loads

EXAMPLE = r'''
[you]
timezone = "America/Denver"

[titles]
function = "customer support|support operations"
level = "\\bmanager\\b|\\bdirector\\b"
exclude = "\\bsales\\b|associate"

[places]
remote = "remote|anywhere"
hybrid_ok = "denver|aurora|lakewood"
remote_only = "boulder|fort collins"
in_country = "colorado|texas|new york|(?-i:\\b(CO|TX|NY)\\b)"
country_wide = "united states|\\busa?\\b"
abroad = "canada|london|india"

[description]
remote_language = "\\bremote\\b|work from home"
contract = "\\b(contract|interim)\\s+(role|position)\\b"
onsite_days = "\\b(4|5|four|five)\\s*days?\\s*(a|per)\\s*week\\b"
onsite_place = "in[- ]?office|on[- ]?site"

[[phrase_rejects]]
name = "quota"
phrases = "quota|book of business|net revenue retention|\\bnrr\\b"
min_distinct = 2
same_as = { "net revenue retention" = "nrr" }

[pay]
reject_if_top_below = 90000
'''


def example(**labels):
    raw = loads(EXAMPLE)
    if labels:
        raw["labels"] = labels
    return settings.parse(raw)


class TitleTest(unittest.TestCase):
    def test_titles(self):
        s = example()
        self.assertTrue(screen.title_ok("Customer Support Manager", s))
        self.assertFalse(screen.title_ok("Customer Support Specialist", s))    # no level word
        self.assertFalse(screen.title_ok("Sales Customer Support Manager", s)) # excluded

    def test_empty_pattern_matches_nothing(self):
        s = settings.parse({"titles": {"function": "support", "level": "manager"}})
        self.assertTrue(screen.title_ok("Support Manager", s))                 # no exclude pattern: nothing excluded
        self.assertEqual(screen.location_ok("Somewhere", s), (True, screen.UNKNOWN))


class PlaceTest(unittest.TestCase):
    def test_tiers(self):
        s = example()
        cases = {
            "Denver, CO": (True, ""),
            "Remote - US": (True, ""),
            "Boulder, CO": (True, screen.REMOTE_ONLY),
            "Denver; Boulder": (True, ""),                 # a near place wins
            "Austin, TX": (True, screen.IN_COUNTRY),
            "United States": (True, screen.COUNTRY_WIDE),
            "Toronto, Canada": (False, ""),
            "London; New York": (True, screen.IN_COUNTRY), # abroad, but a home place is listed
            "": (True, screen.UNKNOWN),
            "Chennai, in": (True, screen.UNKNOWN),         # lower-case 'in' is not Indiana-style CO/TX/NY
        }
        for loc, want in cases.items():
            self.assertEqual(screen.location_ok(loc, s), want, loc)

    def test_normalising(self):
        self.assertEqual(screen.norm_loc("san_francisco/new-york"), "san francisco new york")


class AssessTest(unittest.TestCase):
    def test_location_rejects_need_remote_wording(self):
        s = example()
        st, rule, reason, flags = screen.assess("Austin, TX", screen.IN_COUNTRY, "Hybrid, three days in Austin.", s)
        self.assertEqual((st, rule), ("not_a_fit", "location_in_country"))
        self.assertIn("Austin TX", reason)
        st, rule, _, _ = screen.assess("Austin, TX", screen.IN_COUNTRY, "This role is remote.", s)
        self.assertEqual((st, rule), ("new", ""))
        st, rule, _, _ = screen.assess("Boulder", screen.REMOTE_ONLY, "In office in Boulder.", s)
        self.assertEqual((st, rule), ("not_a_fit", "location_remote_only"))

    def test_phrase_reject_counts_distinct_and_merges(self):
        s = example()
        st, _, _, _ = screen.assess("Denver", "", "Own the NRR number and net revenue retention.", s)
        self.assertEqual(st, "new")  # one idea, two spellings
        st, rule, reason, _ = screen.assess("Denver", "", "Carry a quota and a book of business.", s)
        self.assertEqual((st, rule), ("not_a_fit", "phrases:quota"))
        self.assertIn("book of business, quota", reason)

    def test_pay_tests_the_top_of_the_range(self):
        s = example()
        self.assertEqual(screen.assess("Denver", "", "$60K to $85K", s)[:2], ("not_a_fit", "pay"))
        self.assertEqual(screen.assess("Denver", "", "$70K to $95K", s)[0], "new")
        self.assertEqual(screen.assess("Denver", "", "$70K to $90K", s)[0], "new")  # strictly below rejects
        self.assertEqual(screen.assess("Denver", "", "no pay stated", s)[0], "new")

    def test_first_rule_wins_and_flags_never_reject(self):
        s = example()
        body = ("This is a contract role. You will work in-office 5 days a week. "
                "Carry a quota and a book of business. $50K to $60K.")
        st, rule, _, flags = screen.assess("Austin, TX", screen.IN_COUNTRY, body, s)
        self.assertEqual(rule, "location_in_country")
        self.assertEqual([c for c, _ in flags], [screen.IN_COUNTRY, "contract", "onsite"])
        self.assertIn("contract role", flags[1][1])
        self.assertIn("5 days a week", flags[2][1])

    def test_labels_can_be_replaced(self):
        s = example(flag_in_country="elsewhere in the US", reason_pay="Too low: tops out at ${top_k}K")
        _, _, _, flags = screen.assess("Austin, TX", screen.IN_COUNTRY, "remote", s)
        self.assertEqual(flags[0][1], "elsewhere in the US")
        self.assertEqual(screen.assess("Denver", "", "$60K to $85K", s)[2], "Too low: tops out at $85K")
        self.assertEqual(s.labels["flag_unknown"], settings.DEFAULT_LABELS["flag_unknown"])


if __name__ == "__main__":
    unittest.main()
