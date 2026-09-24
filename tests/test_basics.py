import datetime as dt
import unittest

from jobkit import clock, text, toml
from jobkit._vendor import tomli


class PayTest(unittest.TestCase):
    def test_ranges(self):
        cases = {
            "Pay: $74K to $95K": (74000, 95000),
            "$100,000 - $125,000 a year": (100000, 125000),
            "Base $115K–$194K": (115000, 194000),
            "74K to 95K, no dollar sign": None,
            "A $1,000 - $2,000 stipend. Base $150K to $190K.": (150000, 190000),
            "Band A $120K-$140K, band B $160K-$200K": (160000, 200000),
            "": None,
        }
        for s, want in cases.items():
            self.assertEqual(text.salary_range(s), want, s)

    def test_label(self):
        self.assertEqual(text.salary_from("$155,000 - $175,000"), "$155K to $175K")
        self.assertEqual(text.salary_from("no pay stated"), "")


class HtmlTest(unittest.TestCase):
    def test_html_to_text(self):
        self.assertEqual(text.html_to_text("<p>Hello&nbsp;there</p><ul><li>One</li><li>Two &amp; three</li></ul>"),
                         "Hello\xa0there\n\n- One\n\n- Two & three")
        self.assertEqual(text.html_to_text("<div>A<br>B</div>"), "A\nB")
        self.assertEqual(text.html_to_text(""), "")


SAMPLE = r'''
[titles]
function = "customer support|head of [\\w &]*support|\\bescalations?\\b"
level = "\\bmanager\\b|sr\\.? manager"
[pay]
reject_if_top_below = 90000
[[company]]
name = "Example"
slug = "example"
'''


class TomlTest(unittest.TestCase):
    def test_vendored_reader_matches(self):
        got = tomli.loads(SAMPLE)
        self.assertEqual(got["titles"]["function"], r"customer support|head of [\w &]*support|\bescalations?\b")
        self.assertEqual(got["pay"]["reject_if_top_below"], 90000)
        self.assertEqual(got["company"][0]["slug"], "example")
        self.assertEqual(toml.loads(SAMPLE), got)


class ClockTest(unittest.TestCase):
    FIXED = dt.datetime(2026, 9, 25, 2, 30, tzinfo=dt.timezone.utc)

    def test_local_date_from_settings(self):
        c = clock.Clock("America/Los_Angeles", fixed=self.FIXED)
        if c.tz is None:
            self.skipTest("no time zone data on this machine")
        self.assertEqual(c.today(), "2026-09-24")  # still the evening before, in California
        self.assertTrue(c.stamp().endswith("-07:00"))

    def test_unknown_zone_falls_back(self):
        c = clock.Clock("Not/AZone", fixed=self.FIXED)
        self.assertIsNone(c.tz)
        self.assertRegex(c.today(), r"^2026-09-2[45]$")


if __name__ == "__main__":
    unittest.main()
