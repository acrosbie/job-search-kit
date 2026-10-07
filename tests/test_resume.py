"""The resume: every line traced to about-me.md before anything is made. The about-me.md here is
Morgan's, the made-up accounting manager in Denver (tests/personas/accounting-manager-denver)."""

import os
import unittest

from jobkit import resume
from jobkit.errors import BadFile

PERSONA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "personas", "accounting-manager-denver")


def about():
    with open(os.path.join(PERSONA, "about-me.md"), encoding="utf-8") as f:
        return resume.parse_about(f.read())


def check(body, head="# Morgan Reyes\nDenver, CO · morgan.reyes@example.com\n\n## Experience\n"):
    """The claims in a small resume, checked against Morgan's about-me.md."""
    out = resume.check_text(head + body, about())
    return [it for it in out["items"] if it["kind"] in resume.CLAIMS]


def kinds(item):
    return [p["kind"] for p in item["problems"]]


class AboutTest(unittest.TestCase):
    def test_reads_every_section(self):
        counts = {}
        for e in about():
            counts[e.kind] = counts.get(e.kind, 0) + 1
        self.assertEqual(counts, {"confirmed": 17, "was": 4, "now": 4, "unconfirmed": 2, "owned": 7,
                                  "alongside": 3, "facts": 10})

    def test_corrected_words(self):
        self.assertEqual(resume.was_phrases(about()), ["senior accounting manager", "lead a team of 6", "asc 606", "payroll"])

    def test_numbers(self):
        self.assertEqual(resume.numbers("From 10 business days to 6; $95,000; 1.5 times; 3 of 4; ten years; $250K"),
                         {"10", "6", "95000", "1.5", "3", "4", "250"})
        self.assertEqual(resume.numbers("one of the team, no one else"), set())


class TraceTest(unittest.TestCase):
    def test_a_confirmed_line_traces(self):
        [it] = check("- Cut the month-end close from 10 business days to 6 by rebuilding the close calendar.\n"
                     "  from: Cut the month-end close from 10 business days to 6 by rebuilding the close calendar\n")
        self.assertTrue(it["ok"], it["problems"])

    def test_a_job_heading_and_number_words(self):
        items = check("### Accounting Manager | Peakline Software, Denver, CO | Mar 2021 – Present\n"
                      "from: Accounting Manager, Peakline Software, Denver, CO, Mar 2021 to present\n"
                      "- Lead four direct reports covering the general ledger, accounts payable, payroll accounting and the monthly close.\n"
                      "  from: 4 direct reports at Peakline\n"
                      "  from: The team covers the general ledger, accounts payable, payroll accounting and the monthly close\n")
        self.assertEqual([kinds(it) for it in items], [[], []])

    def test_nothing_says_it(self):
        [it] = check("- Designed and tested SOX controls.\n")
        self.assertEqual(kinds(it), ["no_source"])

    def test_a_source_that_isnt_there(self):
        [it] = check("- Designed and tested SOX controls.\n  from: Designed and tested SOX controls\n")
        self.assertEqual(kinds(it), ["source_not_found"])

    def test_unconfirmed(self):
        [it] = check("- Led consolidations across several entities.\n  from: Consolidations across several entities\n")
        self.assertEqual(kinds(it), ["unconfirmed"])

    def test_citing_what_was_corrected(self):
        [it] = check("- Lead a team of 6.\n  from: Lead a team of 6\n")
        self.assertIn("corrected", kinds(it))

    def test_a_corrected_title_coming_back(self):
        [it] = check("### Senior Accounting Manager | Peakline Software, Denver, CO | Mar 2021 – Present\n"
                     "from: Accounting Manager, Peakline Software, Denver, CO, Mar 2021 to present\n")
        self.assertEqual(kinds(it), ["corrected"])

    def test_stretched_dates(self):
        [it] = check("### Accounting Manager | Peakline Software, Denver, CO | Jan 2020 – Present\n"
                     "from: Accounting Manager, Peakline Software, Denver, CO, Mar 2021 to present\n")
        self.assertEqual(kinds(it), ["number"])
        self.assertIn("2020", it["problems"][0]["detail"])

    def test_a_bigger_team(self):
        [it] = check("- Lead a team of 8 accountants.\n  from: 4 direct reports at Peakline\n")
        self.assertEqual(kinds(it), ["number"])

    def test_money_from_nowhere(self):
        [it] = check("- Automated accounts payable approvals with Bill.com, saving $250K a year.\n"
                     "  from: Automated accounts payable approvals with Bill.com, removing paper invoices entirely\n")
        self.assertEqual(kinds(it), ["number"])

    def test_worked_alongside_isnt_owned(self):
        owned, partnered, via_correction = check(
            "- Owned ASC 606 revenue recognition for subscription contracts.\n"
            "  from: ASC 606 revenue recognition (the revenue accountant owned it)\n"
            "- Partnered with the revenue accountant on ASC 606 revenue recognition.\n"
            "  from: ASC 606 revenue recognition (the revenue accountant owned it)\n"
            "- Led ASC 606 revenue recognition.\n"
            "  from: Worked alongside the revenue accountant on ASC 606\n")
        self.assertEqual(kinds(owned), ["alongside_as_owned"])
        self.assertEqual(kinds(partnered), [])
        self.assertEqual(kinds(via_correction), ["alongside_as_owned"])

    def test_a_corrected_word_is_fine_where_its_source_says_it(self):
        [ok, bad] = check("- Partnered with the revenue accountant on ASC 606.\n"
                          "  from: Worked alongside the revenue accountant on ASC 606\n"
                          "- Expert in ASC 606 and month-end close.\n"
                          "  from: Cut the month-end close from 10 business days to 6\n")
        self.assertEqual(kinds(ok), [])
        self.assertEqual(kinds(bad), ["number", "corrected"])  # 606 isn't in its source either

    def test_a_source_must_say_which_claim(self):
        short, whole = check("- NetSuite.\n  from: NetSuite\n"
                             "### Accounting Manager | Peakline Software | 2021\n  from: Accounting Manager\n")
        self.assertEqual(kinds(short), ["too_short"])
        self.assertEqual(kinds(whole), [])  # the whole of a short entry is fine

    def test_a_credential_after_the_name_is_a_claim(self):
        items = check("", head="# Morgan Reyes, CPA\nDenver, CO\n\n## Experience\n")
        self.assertEqual([(it["kind"], it["text"], kinds(it)) for it in items], [("credential", "CPA", ["no_source"])])

    def test_contact_lines_and_headings_arent_claims(self):
        out = resume.check_text("# Morgan Reyes\nDenver, CO · (555) 010-0142\nlinkedin.com/in/example\n\n"
                                "## Education\nBS, Accounting, Front Range State University, 2015\n"
                                "from: BS, Accounting, Front Range State University, 2015\n", about())
        self.assertEqual((out["name"], out["lines"], out["traced"], out["flagged"]), ("Morgan Reyes", 1, 1, 0))
        self.assertEqual([it["kind"] for it in out["items"]], ["name", "contact", "contact", "heading", "para"])

    def test_claude_s_own_flag(self):
        [it] = check("- Led the annual external audit.\n"
                     "  from: Prepared schedules and managed requests for Peakline's annual external audit\n"
                     "  flag: inflated: about-me.md says they prepared the schedules and handled requests, not that they led it\n")
        self.assertEqual(kinds(it), ["inflated"])
        self.assertEqual(it["problems"][0]["by"], "claude")

    def test_a_badly_made_file(self):
        with self.assertRaises(BadFile):
            resume.parse_source("from: something\n# Morgan Reyes\n")
        with self.assertRaises(BadFile):
            resume.parse_source("Morgan Reyes\n")
        with self.assertRaises(BadFile):
            resume.parse_source("# Morgan Reyes\n## Experience\nfrom: a source under a heading\n")


SAMPLE = """# Morgan Reyes
Denver, CO · morgan.reyes@example.com · (555) 010-0142

## Summary
Accounting manager who runs a fast, clean close & leads a team of 4.
from: 4 direct reports at Peakline
from: Cut the month-end close from 10 business days to 6

## Experience
### Accounting Manager | Peakline Software, Denver, CO | Mar 2021 – Present
from: Accounting Manager, Peakline Software, Denver, CO, Mar 2021 to present
- Cut the month-end close from 10 business days to 6 by rebuilding the close calendar and reconciliations.
  from: Cut the month-end close from 10 business days to 6 by rebuilding the close calendar and reconciliations
- Automated accounts payable approvals with Bill.com, removing paper invoices entirely.
  from: Automated accounts payable approvals with Bill.com, removing paper invoices entirely

## Education
BS, Accounting, Front Range State University, 2015
from: BS, Accounting, Front Range State University, 2015
"""

SAMPLE_PARAGRAPHS = [
    "Morgan Reyes",
    "Denver, CO · morgan.reyes@example.com · (555) 010-0142",
    "Summary",
    "Accounting manager who runs a fast, clean close & leads a team of 4.",
    "Experience",
    "Accounting Manager\tMar 2021 – Present",
    "Peakline Software, Denver, CO",
    "Cut the month-end close from 10 business days to 6 by rebuilding the close calendar and reconciliations.",
    "Automated accounts payable approvals with Bill.com, removing paper invoices entirely.",
    "Education",
    "BS, Accounting, Front Range State University, 2015",
]


class BlocksTest(unittest.TestCase):
    def test_layout(self):
        out = resume.blocks(resume.parse_source(SAMPLE))
        self.assertEqual(out[5], ("job", "Accounting Manager", "Peakline Software, Denver, CO", "Mar 2021 – Present"))
        self.assertEqual([b[0] for b in out], ["name", "contact", "heading", "para", "heading", "job", "bullet",
                                                "bullet", "heading", "para"])

    def test_job_headings(self):
        self.assertEqual(resume._job("Controller | 2019 - 2021"), ("Controller", "", "2019 - 2021"))
        self.assertEqual(resume._job("Controller | Acme"), ("Controller", "Acme", ""))
        self.assertEqual(resume._job("Controller"), ("Controller", "", ""))

    def test_a_credential_joins_the_name(self):
        items = resume.parse_source("# Morgan Reyes, MBA\nDenver\n## Education\nMBA\n")
        self.assertEqual(resume.blocks(items)[0], ("name", "Morgan Reyes, MBA"))


class WordTest(unittest.TestCase):
    def setUp(self):
        from jobkit import docx
        self.docx = docx
        self.data = docx.build(resume.blocks(resume.parse_source(SAMPLE)), title="Morgan Reyes resume",
                               author="Morgan Reyes")

    def test_parts_are_well_formed(self):
        import io
        import zipfile
        from xml.dom import minidom
        with zipfile.ZipFile(io.BytesIO(self.data)) as z:
            names = z.namelist()
            self.assertEqual(names[0], "[Content_Types].xml")
            self.assertEqual(sorted(names), sorted(["[Content_Types].xml", "_rels/.rels", "word/document.xml",
                                                    "word/_rels/document.xml.rels", "word/styles.xml",
                                                    "word/numbering.xml", "docProps/core.xml"]))
            for n in names:
                minidom.parseString(z.read(n))  # raises if any part isn't well-formed XML
            core = z.read("docProps/core.xml").decode("utf-8")
        self.assertIn("<dc:creator>Morgan Reyes</dc:creator>", core)

    def test_text_is_the_resume_without_its_sources(self):
        self.assertEqual(self.docx.text_of(self.data), SAMPLE_PARAGRAPHS)
        self.assertNotIn(b"from:", self.data)

    def test_bullets_are_word_bullets(self):
        import io
        import zipfile
        with zipfile.ZipFile(io.BytesIO(self.data)) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        self.assertEqual(xml.count('<w:numId w:val="1"/>'), 2)
        self.assertNotIn("<w:tbl", xml)  # no tables
        self.assertNotIn("<w:txbx", xml)  # no text boxes

    def test_the_same_resume_makes_the_same_file(self):
        self.assertEqual(self.docx.build(resume.blocks(resume.parse_source(SAMPLE)), "Morgan Reyes resume",
                                         "Morgan Reyes"), self.data)


class PdfTest(unittest.TestCase):
    def setUp(self):
        from jobkit import pdf
        self.pdf = pdf
        self.data, self.pages = pdf.build(resume.blocks(resume.parse_source(SAMPLE)), title="Morgan Reyes resume",
                                          author="Morgan Reyes")

    def test_plain_ascii(self):
        self.assertTrue(all(b < 128 for b in self.data))
        self.assertTrue(self.data.startswith(b"%PDF-1.4\n"))
        self.assertTrue(self.data.endswith(b"%%EOF\n"))

    def test_cross_reference_offsets(self):
        import re
        start = int(re.search(rb"startxref\n(\d+)", self.data).group(1))
        self.assertTrue(self.data[start:].startswith(b"xref\n"))
        rows = re.findall(rb"(\d{10}) 00000 n ", self.data[start:])
        for n, offset in enumerate(rows, 1):
            self.assertTrue(self.data[int(offset):].startswith(f"{n} 0 obj\n".encode()), n)
        size = int(re.search(rb"/Size (\d+)", self.data).group(1))
        self.assertEqual(size, len(rows) + 1)

    def test_text_is_the_resume_without_its_sources(self):
        drawn = self.pdf.text_of(self.data)
        self.assertEqual(self.pages, 1)
        self.assertNotIn("from:", " ".join(drawn))
        flat = " ".join(" ".join(drawn).split())
        for paragraph in SAMPLE_PARAGRAPHS:
            for part in paragraph.split("\t"):
                want = part.upper() if part in ("Summary", "Experience", "Education") else part
                self.assertIn(want, flat)
        self.assertEqual(drawn.count("•"), 2)  # a bullet mark for each bullet

    def test_a_long_resume_runs_onto_more_pages(self):
        bullets = [("bullet", f"Line {n}: reconciled the accounts and closed the month on time.") for n in range(80)]
        data, pages = self.pdf.build([("name", "Morgan Reyes"), ("heading", "Experience")] + bullets)
        self.assertEqual(pages, 2)
        self.assertEqual(data.count(b"/Type /Page "), 2)
        self.assertIn("Line 79: reconciled the accounts and closed the month on time.", self.pdf.text_of(data))

    def test_wrapping(self):
        lines = self.pdf.wrap("word " * 60, "regular", 10, 200)
        self.assertTrue(all(self.pdf.width(line, "regular", 10) <= 200 for line in lines))
        self.assertEqual(" ".join(lines), ("word " * 60).strip())
        self.assertEqual(self.pdf.wrap("x" * 200, "regular", 10, 100)[0], "x" * 20)  # 20 x 5.0 = 100 points

    def test_escapes(self):
        data, _ = self.pdf.build([("name", "Zoë (Jo) O’Neil \\ £")])
        self.assertTrue(all(b < 128 for b in data))
        self.assertEqual(self.pdf.text_of(data), ["Zoë (Jo) O’Neil \\ £"])

    def test_letters_it_cant_draw(self):
        with self.assertRaises(self.pdf.CantDraw) as cm:
            self.pdf.build([("name", "Łucja Nowak"), ("para", "Tokyo 東京")])
        self.assertEqual(cm.exception.chars, ["Ł", "京", "東"])


if __name__ == "__main__":
    unittest.main()
