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
        self.assertEqual(resume.numbers("B2B SaaS, Q4 close, ASC 606, 401(k)"), {"606", "401"})


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


class LookTest(unittest.TestCase):
    """The look both files share (resume_style.py), and sizing it to fill the page."""

    def setUp(self):
        from jobkit import pdf
        self.pdf = pdf
        self.blocks = resume.blocks(resume.parse_source(SAMPLE))

    def lay_out(self, blocks, style):
        pages, fill = self.pdf._lay_out(blocks, style)
        return len(pages), fill

    def with_bullets(self, n):
        return self.blocks + [("bullet", f"Reconciled account {i} and closed the month on time, with the schedules ready for review.")
                              for i in range(n)]

    def test_a_short_resume_grows_to_fill_its_page(self):
        from jobkit.resume_style import Style
        style = self.pdf.fit(self.blocks)
        self.assertGreater(style.scale, 1.0)
        pages, fill = self.lay_out(self.blocks, style)
        self.assertEqual(pages, 1)
        self.assertLessEqual(fill, self.pdf.FULL)
        self.assertGreater(fill, self.lay_out(self.blocks, Style())[1])

    def test_a_slight_spill_tightens_onto_one_page(self):
        from jobkit.resume_style import Style
        n = next(n for n in range(10, 80) if self.lay_out(self.with_bullets(n), Style())[0] == 2)
        blocks = self.with_bullets(n)
        style = self.pdf.fit(blocks)
        self.assertLess(style.scale, 1.0 + 1e-9)
        self.assertEqual(self.lay_out(blocks, style)[0], 1)

    def test_a_long_career_keeps_the_normal_size(self):
        style = self.pdf.fit(self.with_bullets(120))
        self.assertEqual((style.scale, style.space), (1.0, 1.0))
        self.assertGreater(self.lay_out(self.with_bullets(120), style)[0], 1)

    def test_the_pdf_draws_in_the_accent(self):
        from jobkit.resume_style import ACCENT, rgb
        data, _ = self.pdf.build(self.blocks, "Morgan Reyes resume", "Morgan Reyes")
        self.assertIn(f"q {rgb(ACCENT)} rg BT /F2".encode(), data)  # the name and the headings
        self.assertIn(f"q {rgb(ACCENT)} RG".encode(), data)  # the rule under the name

    def test_the_word_file_carries_the_same_look(self):
        import io
        import zipfile
        from jobkit import docx
        from jobkit.resume_style import ACCENT, HAIRLINE, Style
        style = Style(1.06, 1.2)
        data = docx.build(self.blocks, "Morgan Reyes resume", "Morgan Reyes", style)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            styles = z.read("word/styles.xml").decode("utf-8")
            body = z.read("word/document.xml").decode("utf-8")
            numbering = z.read("word/numbering.xml").decode("utf-8")
        title = styles[styles.index('w:styleId="Title"'):styles.index('w:styleId="Heading1"')]
        heading = styles[styles.index('w:styleId="Heading1"'):styles.index('w:styleId="ListBullet"')]
        self.assertIn(f'<w:color w:val="{ACCENT}"/>', title)
        self.assertIn(f'<w:sz w:val="{round(style.name * 2)}"/>', title)
        for part in ("<w:caps/>", f'<w:color w:val="{ACCENT}"/>', '<w:spacing w:val="22"/>', f'w:color="{HAIRLINE}"'):
            self.assertIn(part, heading)
        self.assertIn(f'<w:color w:val="{ACCENT}"/>', numbering)  # the bullet marks
        self.assertEqual(body.count(f'w:color="{ACCENT}"/></w:pBdr>'), 1)  # one rule, under the contact lines
        self.assertEqual(docx.text_of(data), SAMPLE_PARAGRAPHS)


class CommandTest(unittest.TestCase):
    """resume check and resume render, through the command line, in a folder with Morgan's profile and
    the saved jobs of test_scan's made-up boards."""

    def setUp(self):
        import contextlib
        import io
        import shutil
        from tests.test_scan import ScanBase
        base = ScanBase()
        base.setUp()
        self.addCleanup(base.doCleanups)
        base.scan()
        self.root = base.root
        shutil.copy(os.path.join(PERSONA, "about-me.md"), os.path.join(self.root, "profile", "about-me.md"))
        self.source = os.path.join(self.root, "resume", "main.md")
        os.makedirs(os.path.dirname(self.source))
        self.write(SAMPLE)
        self.io, self.contextlib = io, contextlib

    def write(self, text, path=None):
        with open(path or self.source, "w", encoding="utf-8") as f:
            f.write(text)

    def run_cli(self, *args):
        import json
        from jobkit import cli
        out, err = self.io.StringIO(), self.io.StringIO()
        with self.contextlib.redirect_stdout(out), self.contextlib.redirect_stderr(err):
            code = cli.main(list(args) + ["--folder", self.root])
        return code, (json.loads(out.getvalue()) if out.getvalue().strip() else None), err.getvalue()

    def test_render_makes_both_files_beside_the_source(self):
        from jobkit import docx, pdf
        code, out, _ = self.run_cli("resume", "render", self.source)
        self.assertEqual(code, 0)
        self.assertEqual(out["files"], ["resume/Morgan Reyes resume.docx", "resume/Morgan Reyes resume.pdf"])
        self.assertEqual((out["pages"], out["lines"], out["warnings"]), (1, 5, []))
        with open(os.path.join(self.root, "resume", "Morgan Reyes resume.docx"), "rb") as f:
            self.assertEqual(docx.text_of(f.read()), SAMPLE_PARAGRAPHS)
        with open(os.path.join(self.root, "resume", "Morgan Reyes resume.pdf"), "rb") as f:
            self.assertIn("Automated accounts payable approvals with Bill.com, removing paper invoices entirely.",
                          " ".join(pdf.text_of(f.read())))
        [rec] = resume.records(self.root)
        self.assertEqual((rec["source"], rec["for"]), ("resume/main.md", ""))
        self.assertGreater(rec["style"]["scale"], 1.0)  # a short resume, grown to fill its page

    def test_render_refuses_a_line_that_doesnt_trace(self):
        self.write(SAMPLE + "- Designed and tested SOX controls.\n")
        code, out, err = self.run_cli("resume", "render", self.source)
        self.assertEqual((code, out), (3, None))
        self.assertIn("1 of its lines don't trace to about-me.md", err)
        self.assertIn("Designed and tested SOX controls", err)
        self.assertFalse(os.path.exists(os.path.join(self.root, "resume", "Morgan Reyes resume.docx")))

    def test_a_tailored_copy_names_its_job(self):
        path = os.path.join(self.root, "resume", "Acme - Support Lead", "resume.md")
        os.makedirs(os.path.dirname(path))
        self.write(SAMPLE, path)
        code, out, _ = self.run_cli("resume", "render", path, "--for", "greenhouse-acme-1")
        self.assertEqual(code, 0)
        self.assertEqual((out["for"], out["company"]), ("greenhouse-acme-1", "Acme"))
        self.assertEqual(out["files"][0], "resume/Acme - Support Lead/Morgan Reyes resume.docx")
        self.assertEqual(self.run_cli("resume", "render", path, "--for", "greenhouse-acme-404")[0], 1)

    def test_checking_the_user_s_own_resume_keeps_the_result(self):
        own = os.path.join(self.root, "resume", "your-resume.md")
        self.write("# Morgan Reyes, CPA\nDenver, CO\n\n## Experience\n- Lead a team of 8.\n  from: 4 direct reports at Peakline\n", own)
        code, out, _ = self.run_cli("resume", "check", own, "--own")
        self.assertEqual((code, out["lines"], out["flagged"]), (0, 2, 2))
        from jobkit import store
        kept = store.Folder(self.root).read_json(os.path.join(self.root, "data", "resume-check.json"))
        self.assertEqual((kept["source"], kept["flagged"]), ("resume/your-resume.md", 2))
        self.assertTrue(kept["checked_at"])

    def test_a_badly_made_source_is_named(self):
        self.write("Morgan Reyes\n")
        code, _, err = self.run_cli("resume", "check", self.source)
        self.assertEqual(code, 1)
        self.assertIn("starts with the name", err)

    def test_catching_up_notices_a_resume_that_no_longer_matches(self):
        self.assertEqual(self.run_cli("resume", "render", self.source)[0], 0)
        self.assertEqual(self.run_cli("due")[1]["resume_stale"], [])

        # A claim it rests on is corrected in about-me.md: the resume no longer traces.
        about_path = os.path.join(self.root, "profile", "about-me.md")
        with open(about_path, encoding="utf-8") as f:
            text = f.read()
        self.write(text.replace("| Automated accounts payable approvals with Bill.com, removing paper invoices entirely |",
                                "| Automated accounts payable approvals with Bill.com, cutting most paper invoices |"),
                   about_path)
        [stale] = self.run_cli("due")[1]["resume_stale"]
        self.assertEqual((stale["source"], stale["why"]), ("resume/main.md", "profile_changed"))
        self.assertEqual([x["line"] for x in stale["lines"]],
                         ["Automated accounts payable approvals with Bill.com, removing paper invoices entirely."])

        # The source was edited after the files were made.
        self.write(text, about_path)
        self.write(SAMPLE.replace("& leads", "and leads"))
        [stale] = self.run_cli("due")[1]["resume_stale"]
        self.assertEqual(stale["why"], "changed_since_made")

        # Made again: nothing to catch up.
        self.assertEqual(self.run_cli("resume", "render", self.source)[0], 0)
        self.assertEqual(self.run_cli("due")[1]["resume_stale"], [])


if __name__ == "__main__":
    unittest.main()
