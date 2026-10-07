"""Phase 5b's proof, in code: Morgan's updated resume, with 10 claims planted among accurate lines
and one new claim that's true, is checked against about-me.md; Morgan's answers go into about-me.md;
then a clean resume and a copy for one job are made, as a Word file and a PDF, carrying none of the
planted claims. The transcription is the one Claude is asked to write: the resume word for word,
with the words from about-me.md each line rests on, and Claude's own flags where the wording goes
further than them."""

import json
import os
import shutil
import sys

from jobkit import resume
from jobkit.clock import Clock
from jobkit.errors import Refused
from tests.test_scan import FIXED, ScanBase

HERE = os.path.dirname(os.path.abspath(__file__))
PERSONA = os.path.join(HERE, "personas", "accounting-manager-denver")
TOOLS = os.path.join(os.path.dirname(HERE), "tools")
CLOCK = Clock("", fixed=FIXED)

TRANSCRIBED = """# Morgan Reyes, CPA
Denver, CO · morgan.reyes@example.com · (555) 010-0142

## Summary
Accounting manager with ten years across public accounting and in-house finance. Runs a fast, clean month-end close, led a move from QuickBooks to NetSuite, and automated accounts payable with Bill.com.
from: Years in accounting: since Aug 2015 (Morgan's words: "ten years")
from: Cut the month-end close from 10 business days to 6
from: Ran the QuickBooks to NetSuite migration
from: Automated accounts payable approvals with Bill.com

## Experience
### Senior Accounting Manager | Peakline Software, Denver, CO (B2B SaaS) | Mar 2021 – Present
from: Accounting Manager, Peakline Software, Denver, CO, Mar 2021 to present
- Lead a team of 8 covering the general ledger, accounts payable, payroll and the monthly close.
  from: 4 direct reports at Peakline
  from: The team covers the general ledger, accounts payable, payroll accounting and the monthly close
- Cut the month-end close from 10 business days to 6 by rebuilding the close calendar and reconciliations.
  from: Cut the month-end close from 10 business days to 6 by rebuilding the close calendar and reconciliations
- Led the migration from QuickBooks to NetSuite with an outside implementation partner; live in 2022.
  from: Ran the QuickBooks to NetSuite migration: owned the plan, decisions and go-live; an outside implementation partner did the configuration. Live in 2022
- Automated accounts payable approvals with Bill.com, removing paper invoices entirely and saving $250K a year.
  from: Automated accounts payable approvals with Bill.com, removing paper invoices entirely
- Owned ASC 606 revenue recognition for all subscription contracts.
  from: ASC 606 revenue recognition (the revenue accountant owned it)
- Led the annual external audit as the auditors' primary contact.
  from: Prepared schedules and managed requests for Peakline's annual external audit
  flag: inflated: you prepared the schedules and handled the auditors' requests; this says you led the audit
- Led multi-entity consolidations and foreign currency reporting.
  from: Consolidations across several entities, or foreign currency
- Designed and tested SOX controls across the close process.
  flag: contradicts: your profile says no SOX experience
- Built Tableau dashboards for the leadership team.
  from: Tools: NetSuite, QuickBooks, Bill.com, Expensify, Tableau
  flag: inflated: your profile has Tableau as a tool you use, not dashboards you built
- Rolled out Expensify company-wide in 2023, replacing paper expense reports.

### Senior Accountant | Front Range Outdoor Co., Englewood, CO (outdoor retail) | Jun 2016 – Feb 2021
from: Senior Accountant, Front Range Outdoor Co. (outdoor retail), Englewood, CO, Jun 2017 to Feb 2021
- Owned fixed assets, prepaid and accrual schedules, and inventory reconciliations across 12 stores.
  from: owned fixed assets, prepaid and accrual schedules, and inventory reconciliations across 12 stores
- Trained two staff accountants and wrote the close checklist the team still uses.
  from: Trained two staff accountants at Front Range Outdoor Co.
  from: Wrote the close checklist Front Range Outdoor Co.'s team still uses

### Staff Accountant, Audit | Henley & Park CPAs, Denver, CO | Aug 2015 – May 2017
from: Staff Accountant, Audit, Henley & Park CPAs, Denver, CO, Aug 2015 to May 2017
- Audit fieldwork for private companies in retail and construction.
  from: audit fieldwork for private companies in retail and construction

## Education
BS, Accounting, Front Range State University, 2015
from: BS, Accounting, Front Range State University, 2015

## Tools
NetSuite, QuickBooks, Bill.com, Expensify, Excel (advanced: lookups, pivot tables, Power Query), Tableau
from: Tools: NetSuite, QuickBooks, Bill.com, Expensify, Tableau, Excel (advanced: lookups, pivot tables, Power Query)
"""

# Morgan's answers (the answer sheet's "Resume check"), recorded in about-me.md as the skill says.
ANSWERS = [
    ("## Corrected (never use the old version)\n| Was | Now | Why |\n|---|---|---|\n",
     '| "Morgan Reyes, CPA" (resume) | Not licensed: passed 3 of 4 CPA exam sections | Morgan said so, 2026-09-24: "I\'m not licensed." |\n'
     '| "Jun 2016" (resume, Front Range Outdoor Co.) | Jun 2017 | Morgan said so, 2026-09-24: "June 2017. I got that wrong." |\n'
     '| "Built Tableau dashboards" (resume) | Uses Tableau dashboards others build | Morgan said so, 2026-09-24: "I use the dashboards." |\n'
     '| "Led the annual external audit" (resume) | Prepared the schedules and handled the auditors\' requests; the controller led the audit | Morgan said so, 2026-09-24 |\n'),
    ("| Backs themself on:",
     '| Rolled out Expensify company-wide in 2023, replacing paper expense reports | Morgan said so, 2026-09-24: "Yes, that\'s right. I ran that rollout in 2023, for the whole company." |\n'
     '| Backs themself on:'),
    ("## Not confirmed yet (never use in an application)\n",
     '- Savings from the Bill.com automation: "I can\'t back that number up", 2026-09-24.\n'),
]

MAIN = """# Morgan Reyes
Denver, CO · morgan.reyes@example.com · (555) 010-0142

## Summary
Accounting manager with ten years across public accounting and in-house finance. Runs a month-end close cut from 10 business days to 6, ran the move from QuickBooks to NetSuite, and automated accounts payable with Bill.com.
from: Years in accounting: since Aug 2015 (Morgan's words: "ten years")
from: Cut the month-end close from 10 business days to 6
from: Ran the QuickBooks to NetSuite migration
from: Automated accounts payable approvals with Bill.com

## Experience
### Accounting Manager | Peakline Software, Denver, CO | Mar 2021 – Present
from: Accounting Manager, Peakline Software, Denver, CO, Mar 2021 to present
- Lead a team of 4 covering the general ledger, accounts payable, payroll accounting and the monthly close.
  from: 4 direct reports at Peakline
  from: The team covers the general ledger, accounts payable, payroll accounting and the monthly close
- Cut the month-end close from 10 business days to 6 by rebuilding the close calendar and reconciliations.
  from: Cut the month-end close from 10 business days to 6 by rebuilding the close calendar and reconciliations
- Led the migration from QuickBooks to NetSuite with an outside implementation partner; live in 2022.
  from: Ran the QuickBooks to NetSuite migration: owned the plan, decisions and go-live; an outside implementation partner did the configuration. Live in 2022
- Automated accounts payable approvals with Bill.com, removing paper invoices entirely.
  from: Automated accounts payable approvals with Bill.com, removing paper invoices entirely
- Rolled out Expensify company-wide in 2023, replacing paper expense reports.
  from: Rolled out Expensify company-wide in 2023, replacing paper expense reports
- Partnered with the revenue accountant on ASC 606 revenue recognition for subscription contracts.
  from: Worked alongside the revenue accountant on ASC 606
- Prepared schedules and handled the auditors' requests for the annual external audit.
  from: Prepared schedules and managed requests for Peakline's annual external audit

### Senior Accountant | Front Range Outdoor Co., Englewood, CO | Jun 2017 – Feb 2021
from: Senior Accountant, Front Range Outdoor Co. (outdoor retail), Englewood, CO, Jun 2017 to Feb 2021
- Owned fixed assets, prepaid and accrual schedules, and inventory reconciliations across 12 stores.
  from: owned fixed assets, prepaid and accrual schedules, and inventory reconciliations across 12 stores
- Trained two staff accountants and wrote the close checklist the team still uses.
  from: Trained two staff accountants at Front Range Outdoor Co.
  from: Wrote the close checklist Front Range Outdoor Co.'s team still uses

### Staff Accountant, Audit | Henley & Park CPAs, Denver, CO | Aug 2015 – May 2017
from: Staff Accountant, Audit, Henley & Park CPAs, Denver, CO, Aug 2015 to May 2017
- Audit fieldwork for private companies in retail and construction.
  from: audit fieldwork for private companies in retail and construction

## Education
BS, Accounting, Front Range State University, 2015
from: BS, Accounting, Front Range State University, 2015
CPA exam: passed 3 of 4 sections
from: CPA exam: passed 3 of 4 sections

## Tools
NetSuite, QuickBooks, Bill.com, Expensify, Excel (advanced: lookups, pivot tables, Power Query), Tableau
from: Tools: NetSuite, QuickBooks, Bill.com, Expensify, Tableau, Excel (advanced: lookups, pivot tables, Power Query)
"""

# The copy for one job: the summary leads with what fits, and the most relevant bullets come first.
TAILORED_SUMMARY = (
    "Accounting manager who ran a QuickBooks to NetSuite migration and automated accounts payable with Bill.com, "
    "with a month-end close cut from 10 business days to 6 and schedules prepared for the annual external audit.\n"
    "from: Ran the QuickBooks to NetSuite migration\n"
    "from: Automated accounts payable approvals with Bill.com\n"
    "from: Cut the month-end close from 10 business days to 6\n"
    "from: Prepared schedules and managed requests for Peakline's annual external audit\n")


def tailored():
    head, rest = MAIN.split("## Summary\n", 1)
    _, rest = rest.split("\n## Experience\n", 1)
    first = "- Led the migration from QuickBooks"
    lines = rest.split("\n")
    i = next(n for n, line in enumerate(lines) if line.startswith(first))
    moved = lines[i:i + 2]
    del lines[i:i + 2]
    j = next(n for n, line in enumerate(lines) if line.startswith("- Lead a team of 4"))
    lines[j:j] = moved
    return head + "## Summary\n" + TAILORED_SUMMARY + "\n## Experience\n" + "\n".join(lines)


class ResumeProofTest(ScanBase):
    def setUp(self):
        super().setUp()
        self.scan()
        about = os.path.join(self.root, "profile", "about-me.md")
        shutil.copy(os.path.join(PERSONA, "about-me.md"), about)
        self.about = about
        os.makedirs(os.path.join(self.root, "resume"))
        with open(os.path.join(PERSONA, "resume-seeds.json"), encoding="utf-8") as f:
            self.seeds = json.load(f)
        # The run's job is #72 at Grafana Labs; here, one of the recorded test boards' jobs.
        self.seeds["job"].update({"key": "greenhouse-acme-1", "company": "Acme", "num": 1})

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_check_answers_clean_and_tailored(self):
        # The check: every planted claim is flagged, and no accurate line is called wrong.
        own = self.write("resume/your-resume-2026-09-24.md", TRANSCRIBED)
        out = resume.check(self.root, own, CLOCK, own=True)
        self.assertEqual((out["lines"], out["flagged"]), (20, 11))
        engine_kinds = {}
        for it in out["items"]:
            for p in it.get("problems", []):
                engine_kinds.setdefault(p["kind"], []).append(it["text"][:24])
        # What the engine catches by rule, without Claude's flags: 7 of the 10, and the new claim.
        self.assertEqual(sorted((k, len(v)) for k, v in engine_kinds.items()),
                         [("alongside_as_owned", 1), ("contradicts", 1), ("corrected", 1), ("inflated", 2),
                          ("no_source", 2), ("number", 3), ("unconfirmed", 1)])

        # Nothing is made from it.
        with self.assertRaises(Refused):
            resume.render(self.root, own, CLOCK)

        # Morgan's answers, recorded in about-me.md.
        with open(self.about, encoding="utf-8") as f:
            text = f.read()
        for anchor, added in ANSWERS:
            self.assertIn(anchor, text)
            text = text.replace(anchor, anchor + added if anchor.startswith("##") else added, 1)
        self.write("profile/about-me.md", text)

        # The clean resume and the copy for one job: each traces, and is made.
        main = self.write("resume/main.md", MAIN)
        self.assertEqual(resume.check(self.root, main, CLOCK)["flagged"], 0)
        made = resume.render(self.root, main, CLOCK)
        self.assertEqual((made["pages"], made["warnings"]), (1, []))
        copy = self.write("resume/Acme - Head of Support/resume.md", tailored())
        self.assertEqual(resume.check(self.root, copy, CLOCK)["flagged"], 0)
        resume.render(self.root, copy, CLOCK, for_key="greenhouse-acme-1")

        # A planted claim slipped back into the clean resume is refused.
        self.write("resume/main.md", MAIN.replace("team of 4", "team of 8"))
        with self.assertRaises(Refused):
            resume.render(self.root, main, CLOCK)
        self.write("resume/main.md", MAIN)

        # And the Cowork run's checker agrees.
        sys.path.insert(0, TOOLS)
        import check_resume
        results = check_resume.check(self.root, self.seeds)
        self.assertEqual([what for passed, what in results if not passed], [])
        self.assertGreater(len(results), 50)


if __name__ == "__main__":
    import unittest
    unittest.main()
