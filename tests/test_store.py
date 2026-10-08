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

    def test_a_long_scan_never_undoes_what_was_saved_meanwhile(self):
        # Found in a bug hunt: a scan loaded postings.json, fetched for minutes, then saved its old
        # copy, so "I applied to #12" said meanwhile went back to Worth applying.
        f = self.folder
        f.save_postings({"postings": {"a": {"status": "worth_applying", "num": 12, "last_seen": "2026-10-01"},
                                      "b": {"status": "new", "last_seen": "2026-10-01"}}, "boards": {}})
        scan = f.load_postings()
        verdict = store.Folder(self.root).load_postings()
        verdict["postings"]["a"]["status"] = "applied"
        verdict["postings"]["a"]["triaged"] = "2026-10-07"
        store.Folder(self.root).save_postings(verdict)
        for k in ("a", "b"):
            scan["postings"][k]["last_seen"] = "2026-10-07"
        scan["postings"]["a"]["gone"] = "2026-10-07"
        scan["postings"]["c"] = {"status": "new", "first_seen": "2026-10-07"}
        scan["boards"]["acme"] = {"jobs": 3}
        f.save_postings(scan)
        got = f.load_postings()
        self.assertEqual(got["postings"]["a"], {"status": "applied", "num": 12, "triaged": "2026-10-07",
                                                "last_seen": "2026-10-07", "gone": "2026-10-07"})
        self.assertEqual(got["postings"]["b"]["last_seen"], "2026-10-07")
        self.assertEqual(got["postings"]["c"], {"status": "new", "first_seen": "2026-10-07"})
        self.assertEqual(got["boards"], {"acme": {"jobs": 3}})

    def test_applications_merge_too(self):
        from jobkit import track
        f = self.folder
        f.save_applications([{"id": "x", "company": "Acme", "role": "Lead", "status": "applied", "applied_date": "2026-09-01"},
                             {"id": "y", "company": "Globex", "role": "Lead", "status": "applied", "applied_date": "2026-09-20"}])
        closing = track.load(self.root)
        replying = track.load(self.root)
        replying[1]["status"] = "replied"
        track.save(self.root, replying)
        closing[0]["status"] = "presumed_rejected"
        track.save(self.root, closing)
        self.assertEqual([a["status"] for a in f.load_applications()], ["presumed_rejected", "replied"])

    def test_a_half_written_file_is_read_from_its_backup(self):
        f = self.folder
        f.save_postings({"postings": {"a": {"status": "new"}}, "boards": {}})
        f.save_postings({"postings": {"a": {"status": "applied"}}, "boards": {}})
        with open(f.postings_json, "w", encoding="utf-8") as h:
            h.write('{"postings": {"a": {"sta')
        state = f.load_postings()
        self.assertEqual(state["postings"]["a"]["status"], "new")  # the backup: one save behind, not lost
        state["postings"]["a"]["note"] = "kept"
        f.save_postings(state)
        self.assertEqual(f.load_postings()["postings"]["a"], {"status": "new", "note": "kept"})
        self.assertEqual(json.loads(read(f.backup_json))["postings"]["a"]["status"], "new")  # never the broken file

    def test_changed_lists_what_a_command_wrote(self):
        # For running on a copy of the user's folder: copy back exactly what changed (the fixed lists
        # this replaced had left out changes.log, review.json and the interview files).
        import contextlib
        import io
        import time
        from jobkit import cli
        os.makedirs(os.path.join(self.root, "data"), exist_ok=True)
        os.makedirs(os.path.join(self.root, ".kit"))
        for name in ("data/old.json", ".kit/engine.py"):
            with open(os.path.join(self.root, *name.split("/")), "w", encoding="utf-8") as f:
                f.write("{}")
            os.utime(os.path.join(self.root, *name.split("/")), (time.time() - 3600, time.time() - 3600))
        with open(os.path.join(self.root, "data", "changes.log"), "w", encoding="utf-8") as f:
            f.write("{}\n")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            cli.main(["changed", "--folder", self.root, "--since", time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - 60))])
        self.assertEqual(json.loads(out.getvalue())["files"], ["data/changes.log"])

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
        # A longer title holding the whole of a 3-word role is enough to flag "you already applied here",
        # never to record anything.
        wider = {"company": "globex", "title": "Senior Support Operations Manager, Americas", "url": ""}
        self.assertEqual(store.application_for(wider, self.APPS, loose=True)["company"], "Globex")
        self.assertIsNone(store.application_for(wider, self.APPS))
        self.assertIsNone(store.application_for({"company": "Globex", "title": "Engineer", "url": ""}, self.APPS))

    def test_a_short_title_inside_a_longer_one_is_not_the_same_job(self):
        # Found in a bug hunt: "Manager" was inside "Engineering Manager", so pasting a new Acme job
        # could mark it applied with an old application's date.
        apps = [{"company": "Acme", "role": "Manager", "urls": []},
                {"company": "Acme", "role": "Customer Success Manager", "urls": []}]
        for title in ("Engineering Manager", "Senior Customer Success Manager, Enterprise"):
            self.assertIsNone(store.application_for({"company": "Acme", "title": title, "url": ""}, apps), title)
        self.assertIsNone(store.application_for({"company": "Acme", "title": "Engineering Manager", "url": ""}, apps, loose=True))
        self.assertEqual(store.application_for({"company": "Acme", "title": "Sr. Customer Success Mgr", "url": ""},
                                               [{"company": "Acme", "role": "Senior Customer Success Manager", "urls": []}])["role"],
                         "Senior Customer Success Manager")


if __name__ == "__main__":
    unittest.main()
