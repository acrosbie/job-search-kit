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


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        for name, text in (("config.toml", CONFIG), ("watchlist.toml", WATCHLIST), ("pipeline.md", PIPELINE),
                           ("labels.json", json.dumps({"flag_in_country": "elsewhere", "reason_renewals": "Renewals: {hits}"}))):
            with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
                f.write(text)

    def run_tool(self, out):
        d = self.dir
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return import_reference.main(["--config", f"{d}/config.toml", "--watchlist", f"{d}/watchlist.toml",
                                          "--pipeline", f"{d}/pipeline.md", "--labels", f"{d}/labels.json",
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
        self.assertEqual((apps[1]["role"], apps[1]["applied"], apps[1]["applied_date"]), ("Head of Support", "1w", ""))
        posting = {"company": "Acme", "title": "Support Operations Manager", "url": ""}
        self.assertEqual(store.application_for(posting, apps)["applied"], "2026-09-10")

    def test_refuses_to_write_inside_the_repo(self):
        self.assertEqual(self.run_tool(os.path.join(import_reference.REPO, "tmp-personal")), 3)
        self.assertFalse(os.path.exists(os.path.join(import_reference.REPO, "tmp-personal")))


if __name__ == "__main__":
    unittest.main()
