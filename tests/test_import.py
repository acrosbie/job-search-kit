"""tools/import_reference.py on made-up files in the reference scanner's shapes."""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

from jobkit import settings, store

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import import_reference  # noqa: E402

CONFIG = r'''
[titles]
function = "support operations|head of [\\w &]*support"
level = "\\bmanager\\b"
exclude = "sales"
renewals = "quota|renewal|\\bnrr\\b"
contract = "\\bcontract role\\b"

[location]
remote = "remote"
bay_core = "springfield"
bay_outer = "shelbyville"
us = "ohio|(?-i:\\bOH\\b)"
us_national = "united states"
remote_language = "\\bremote\\b"
onsite_days = "5 days a week"
onsite_place = "in office"
drop = "canada"

[pay]
reject_if_top_below = 80000

[workday]
country_facet = "^united states"
max_total = 500
'''

WATCHLIST = '''
# a comment that won't survive
[[company]]
name = "Acme"
slug = "acme"
ats = "greenhouse"
token = "acme"
size_note = ""

[[company]]
name = "Remote board"
slug = "remote-board"
ats = "himalayas"
queries = ["support operations", "head of support"]
'''

PIPELINE = """# Pipeline

## To apply

| Company | Role |
|---|---|

## Applied

| Company | Role | Fit | Level | Pay | Applied | Followed up | Status | Note |
|---|---|---|---|---|---|---|---|---|
| Acme | Support Operations Manager ([posting](https://acme.test/jobs/5)) | Strong | Manager | $90K | 2026-09-10 | | open | contact: Pat |
| Globex | [Head of Support](https://globex.test/j/1) | Fair | Manager | | 1w | | open | |

## Outreach
"""

SEEN = {
    "postings": {
        "greenhouse-acme-5": {"status": "reject", "company": "Acme", "title": "Support Operations Manager",
                              "location": "Toledo, OH", "url": "https://acme.test/jobs/5", "posted": "", "source": "greenhouse",
                              "flag": "elsewhere; contract or interim (contract role)", "file": "greenhouse-acme-5.md",
                              "first_seen": "2026-09-20", "last_seen": "2026-09-21", "salary": "",
                              "note": "Rule 11: requires 5 years managing vendors", "triaged": "2026-09-21"},
        "greenhouse-acme-6": {"status": "apply", "company": "Acme", "title": "Head of Support", "location": "Springfield",
                              "url": "https://acme.test/jobs/6", "posted": "", "source": "greenhouse", "flag": "",
                              "file": "greenhouse-acme-6.md", "first_seen": "2026-09-22", "last_seen": "2026-09-22",
                              "salary": "$120K to $150K"},
    },
    "sources": {"acme": {"ats": "greenhouse", "jobs": 12, "matched": 2}},
}

TRIAGE_LOG = """# Triage log

| Date | Company | Title | Verdict | Rule or question | Key |
|---|---|---|---|---|---|
| 2026-09-21 | Acme | Support Operations Manager | REJECT | Rule 11: "5+ years managing vendors" | greenhouse-acme-5 |
| 2026-09-22 | Acme | Head of Support | APPLY | Owns the stack | greenhouse-acme-6 |
| 2026-09-22 | Acme | Head of Support | REJECT | REVERSAL of APPLY. page: too far | greenhouse-acme-6 |
"""


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        for name, text in (("config.toml", CONFIG), ("watchlist.toml", WATCHLIST), ("pipeline.md", PIPELINE),
                           ("labels.json", json.dumps({"flag_in_country": "elsewhere", "reason_renewals": "Renewals: {hits}"})),
                           ("seen.json", json.dumps(SEEN)), ("triage-log.md", TRIAGE_LOG),
                           ("dates.json", json.dumps({"1w": "2026-09-05"}))):
            with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
                f.write(text)
        os.makedirs(os.path.join(self.dir, "postings"))
        with open(os.path.join(self.dir, "postings", "greenhouse-acme-5.md"), "w", encoding="utf-8") as f:
            f.write("# Support Operations Manager\n\n- Company: Acme\n\n---\nManage the vendors.\n")

    def run_tool(self, out):
        d = self.dir
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return import_reference.main(["--config", f"{d}/config.toml", "--watchlist", f"{d}/watchlist.toml",
                                          "--pipeline", f"{d}/pipeline.md", "--labels", f"{d}/labels.json",
                                          "--relative-dates", f"{d}/dates.json", "--seen", f"{d}/seen.json",
                                          "--postings-dir", f"{d}/postings", "--triage-log", f"{d}/triage-log.md",
                                          "--timezone", "America/New_York", "--out", out])

    def test_converts_everything(self):
        out = os.path.join(self.dir, "kit")
        self.assertEqual(self.run_tool(out), 0)
        s = settings.load(out)
        self.assertEqual(s.timezone, "America/New_York")
        self.assertEqual(s.hybrid_ok.pattern, "springfield")
        self.assertEqual(s.remote_only.pattern, "shelbyville")
        self.assertEqual(s.in_country.pattern, r"ohio|(?-i:\bOH\b)")
        self.assertEqual(s.contract.pattern, r"\bcontract role\b")
        self.assertEqual((s.pay_top_below, s.workday["max_total"]), (80000, 500))
        pr = s.phrase_rejects[0]
        self.assertEqual((pr.name, pr.min_distinct, pr.same_as, pr.reason),
                         ("renewals", 2, {"net revenue retention": "nrr"}, "Renewals: {hits}"))
        self.assertEqual(s.labels["flag_in_country"], "elsewhere")
        self.assertNotIn("reason_renewals", s.labels)

        companies = settings.load_companies(out)
        self.assertEqual([c["slug"] for c in companies], ["acme", "remote-board"])
        self.assertEqual(companies[1]["queries"], ["support operations", "head of support"])

        apps = store.Folder(out).load_applications()
        self.assertEqual(len(apps), 2)
        self.assertEqual((apps[0]["role"], apps[0]["urls"], apps[0]["applied_date"]),
                         ("Support Operations Manager (posting)", ["https://acme.test/jobs/5"], "2026-09-10"))
        self.assertEqual((apps[1]["role"], apps[1]["applied"], apps[1]["applied_date"], apps[1]["applied_date_estimated"]),
                         ("Head of Support", "1w", "2026-09-05", True))
        posting = {"company": "Acme", "title": "Support Operations Manager", "url": ""}
        self.assertEqual(store.application_for(posting, apps)["applied"], "2026-09-10")

    def test_postings_and_decisions(self):
        out = os.path.join(self.dir, "kit")
        self.assertEqual(self.run_tool(out), 0)
        f = store.Folder(out)
        state = f.load_postings()
        p5, p6 = state["postings"]["greenhouse-acme-5"], state["postings"]["greenhouse-acme-6"]
        self.assertEqual((p5["status"], p5["rule"], p6["status"]), ("not_a_fit", "rule_11", "worth_applying"))
        self.assertEqual([x["text"] for x in p5["flags"]], ["elsewhere", "contract or interim (contract role)"])
        self.assertEqual(state["boards"]["acme"]["jobs"], 12)
        self.assertIn("Manage the vendors.", f.read_description("greenhouse-acme-5"))
        self.assertIsNone(f.read_description("greenhouse-acme-6"))  # no saved copy to bring across
        d = f.read_decisions()
        self.assertEqual([(x["verdict"], x["by"]) for x in d],
                         [("not_a_fit", "claude"), ("worth_applying", "claude"), ("not_a_fit", "user")])
        self.assertEqual((d[0]["rule"], d[2]["reverses"]), ("rule_11", "worth_applying"))

    def test_refuses_to_write_inside_the_repo(self):
        self.assertEqual(self.run_tool(os.path.join(import_reference.REPO, "tmp-personal")), 3)
        self.assertFalse(os.path.exists(os.path.join(import_reference.REPO, "tmp-personal")))


if __name__ == "__main__":
    unittest.main()
