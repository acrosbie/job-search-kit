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
            # Found on a real search: the page said "pay not stated" for these.
            "Acme reasonably expects to pay a base salary between $165,000 and $205,000 per year": (165000, 205000),
            "Compensation offered for this role is 104,000.00 - 176,250.00 annually": (104000, 176250),
            "$120,000.00 - $150,000.00": (120000, 150000),
            "USD 140,000 - 170,000": (140000, 170000),
            "Pay range: $120-150K": (120000, 150000),
            "$85,000/yr - $95,000/yr": (85000, 95000),
            "$45.00 - $55.00 per hour": (93600, 114400),
            "$40 to $50 an hour": (83200, 104000),
            # A bonus or commission range is never the pay, and the base range wins even when lower.
            "Base $150,000.00 - $180,000.00 plus commission $60,000 - $80,000": (150000, 180000),
            "Annual bonus target $60,000-$90,000. Base salary $120K to $140K.": (120000, 140000),
            "$150K-$190K base salary, $20K-$30K annual bonus": (150000, 190000),
            "OTE $200K-$260K; base $130K-$150K": (130000, 150000),
            # Not dollars, or not pay.
            "$120,000 - $150,000 CAD": None,
            "£60,000 - £75,000 salary": None,
            "Manage 10 to 15 people across 3-5 teams": None,
            "We have between 200 and 300 employees": None,
        }
        for s, want in cases.items():
            self.assertEqual(text.salary_range(s), want, s)

    def test_label(self):
        self.assertEqual(text.salary_from("$155,000 - $175,000"), "$155K to $175K")
        self.assertEqual(text.salary_from("no pay stated"), "")
        self.assertEqual(text.salary_from("$45.50 - $55 per hour"), "$45.50 to $55 an hour")
        self.assertEqual(text.salary_from("Salary: $8,000 to $10,000 a month"), "$8,000 to $10,000 a month")

    def test_the_label_reads_back_as_the_same_pay(self):
        # The pay command and the page read a saved posting's label again, so it must mean the same.
        for s in ("$45.50 - $55 per hour", "Salary: $8,000 to $10,000 a month", "between $165,000 and $205,000 a year"):
            self.assertEqual(text.salary_range(text.salary_from(s)), text.salary_range(s), s)


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
