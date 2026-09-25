import json
import os
import shutil
import tempfile
import unittest

from jobkit import store


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.folder = store.Folder(self.root)

    def test_postings_round_trip_with_backup(self):
        f = self.folder
        self.assertEqual(f.load_postings(), {"postings": {}, "boards": {}})
        f.save_postings({"postings": {"a": {"title": "Café lead"}}, "boards": {}})
        self.assertFalse(os.path.exists(f.backup_json))
        f.save_postings({"postings": {"b": {}}, "boards": {}})
        self.assertEqual(json.loads(read(f.backup_json))["postings"], {"a": {"title": "Café lead"}})
        self.assertEqual(list(f.load_postings()["postings"]), ["b"])

    def test_description_header(self):
        rec = {"key": "greenhouse-acme-1", "title": "Support Manager", "company": "Acme", "location": "",
               "url": "https://acme.test/1", "posted": "", "ats": "greenhouse"}
        self.assertEqual(self.folder.save_description(rec, "Lead the team.", "2026-09-24"), "greenhouse-acme-1.md")
        text = self.folder.read_description("greenhouse-acme-1")
        self.assertTrue(text.startswith("# Support Manager\n\n- Company: Acme\n- Location: (not stated)\n"))
        self.assertIn("- Fetched: 2026-09-24\n- Key: greenhouse-acme-1\n\n---\nLead the team.\n", text)

    def test_logs_skip_a_truncated_line(self):
        f = self.folder
        f.log_run({"read": 10})
        with open(f.runs_log, "a", encoding="utf-8") as fh:
            fh.write('{"read": 1')  # a crash mid-write
        f.log_run({"read": 20})
        self.assertEqual([r["read"] for r in f.read_runs()], [10, 20])
        f.log_decision({"key": "k", "verdict": "not_a_fit", "by": "rule"})
        self.assertEqual(f.read_decisions()[0]["by"], "rule")

    def test_titles(self):
        self.folder.write_titles([("acme", "Lead\tSupport", "Denver")])
        self.assertEqual(read(self.folder.titles_tsv),
                         "source\ttitle\tlocation\nacme\tLead Support\tDenver\n")


class ApplicationMatchTest(unittest.TestCase):
    APPS = [
        {"company": "Acme", "role": "Head of CX (Remote)", "urls": ["https://acme.test/jobs/9/"], "applied": "2026-09-20"},
        {"company": "Globex", "role": "Support Operations Manager", "urls": [], "applied": "2026-09-21"},
    ]

    def test_by_link_then_by_title(self):
        by_link = {"company": "Other", "title": "Anything", "url": "https://acme.test/jobs/9"}
        self.assertEqual(store.application_for(by_link, self.APPS)["company"], "Acme")
        by_title = {"company": "Acme", "title": "Head of Customer Experience", "url": ""}
        self.assertEqual(store.application_for(by_title, self.APPS)["applied"], "2026-09-20")
        wider = {"company": "globex", "title": "Senior Support Operations Manager, Americas", "url": ""}
        self.assertEqual(store.application_for(wider, self.APPS)["company"], "Globex")
        self.assertIsNone(store.application_for({"company": "Globex", "title": "Engineer", "url": ""}, self.APPS))


if __name__ == "__main__":
    unittest.main()
