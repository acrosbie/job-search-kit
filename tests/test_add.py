"""Adding a job the user found themselves: a pasted link or its text. Made-up postings on the made-up
Acme board from test_scan, and real ones replayed from the recorded sample boards."""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from jobkit import add, cli, net, store
from jobkit.clock import Clock
from jobkit.errors import Refused
from tests.test_recorded import AS_OF, FOLDER, SAMPLE
from tests.test_scan import FIXED, Fake, ScanBase, answers

CLOCK = Clock("", fixed=FIXED)
LINKEDIN = "https://www.linkedin.com/jobs/view/support-operations-manager-at-initech-4012345678/?trk=public_jobs"


def posting(title="Support Operations Manager", company="Initech", location="Denver, CO", url=LINKEDIN,
            body="Lead the support operations team.\n\nPay: $130,000 to $150,000."):
    return (f"# {title}\n\n- Company: {company}\n- Location: {location}\n- URL: {url}\n- Posted: (unknown)\n\n"
            f"---\n\n{body}\n")


class LinkTest(unittest.TestCase):
    def test_link_ids(self):
        self.assertEqual(add.link_id(LINKEDIN), "4012345678")
        self.assertEqual(add.link_id("https://www.linkedin.com/jobs/view/4012345678/"), "4012345678")
        self.assertEqual(add.link_id("https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4012345678"),
                         "4012345678")
        self.assertEqual(add.link_id("https://www.indeed.com/viewjob?jk=1a2b3c4d5e6f7a8b&from=serp"), "1a2b3c4d5e6f7a8b")
        self.assertEqual(add.link_id("https://careers.initech.test/jobs/support-lead"), "")
        self.assertEqual(add.manual_key("Initech, Inc.", "", "Support Lead (Remote)"), "manual-initech-inc-support-lead-remote")

    def test_one_linkedin_job_in_any_shape_is_one_link(self):
        shapes = [LINKEDIN, "https://linkedin.com/jobs/view/4012345678",
                  "https://www.linkedin.com/jobs/search/?currentJobId=4012345678&keywords=support"]
        self.assertEqual({add.norm_url(u) for u in shapes}, {"linkedin:4012345678"})
        self.assertEqual(add.norm_url("https://Boards.Greenhouse.io/acme/jobs/1/?utm=x#apply"),
                         add.norm_url("http://boards.greenhouse.io/acme/jobs/1"))

    def test_board_links(self):
        cases = {
            "https://boards.greenhouse.io/acme/jobs/4012": ("greenhouse", {"token": "acme"}, "4012"),
            "https://job-boards.greenhouse.io/doordashusa/jobs/7983379?gh_src=x": ("greenhouse", {"token": "doordashusa"}, "7983379"),
            "https://jobs.lever.co/happyco/6c940fb8-9809-4b77-9207-07de545180eb/apply":
                ("lever", {"token": "happyco"}, "6c940fb8-9809-4b77-9207-07de545180eb"),
            "https://jobs.ashbyhq.com/ramp/1285aefc-d2c4-4f7c-8357-6e8f97fb22d4":
                ("ashby", {"token": "ramp"}, "1285aefc-d2c4-4f7c-8357-6e8f97fb22d4"),
            "https://jobs.smartrecruiters.com/VuoriInc/744000012345678-support-lead":
                ("smartrecruiters", {"token": "VuoriInc"}, "744000012345678"),
            "https://ats.rippling.com/opendoor/jobs/0a1b2c3d-1111-2222-3333-444455556666":
                ("rippling", {"token": "opendoor"}, "0a1b2c3d-1111-2222-3333-444455556666"),
            "https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/USA-CA-Pleasanton/Lead_JR-0109564-1":
                ("workday", {"host": "workday.wd5.myworkdayjobs.com", "tenant": "workday", "site": "Workday"}, ""),
        }
        for url, want in cases.items():
            self.assertEqual(add.parse_link(url), want, url)
        self.assertIsNone(add.parse_link(LINKEDIN))


class AddFileTest(ScanBase):
    def draft(self, text):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        path = os.path.join(d, "draft.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_a_pasted_linkedin_job(self):
        out = add.add_file(self.root, self.draft(posting()), CLOCK, text_from="link")
        key = "manual-initech-4012345678"
        self.assertEqual((out["key"], out["status"], out["source"], out["text_from"]), (key, "new", "manual", "link"))
        self.assertEqual(out["salary"], "$130K to $150K")
        self.assertEqual(out["flag"], "")  # Denver, and a title the search looks for
        saved = self.folder.read_description(key)
        self.assertTrue(saved.startswith("# Support Operations Manager\n\n- Company: Initech\n"))
        self.assertIn("- Key: manual-initech-4012345678", saved)
        self.assertIn("Lead the support operations team.", saved)
        self.assertEqual(self.folder.load_postings()["postings"][key]["status"], "new")

    def test_screened_like_a_scan(self):
        out = add.add_file(self.root, self.draft(posting(body="Own a quota and a book of business.")), CLOCK)
        self.assertEqual((out["status"], out["rule"]), ("not_a_fit", "phrases:quota"))
        self.assertEqual(self.folder.read_decisions()[-1]["by"], "rule")
        far = add.add_file(self.root, self.draft(posting(title="Support Director", location="London, UK", url="")), CLOCK)
        self.assertEqual((far["status"], far["rule"]), ("not_a_fit", "location_abroad"))
        self.assertIn("London UK", far["note"])
        odd = add.add_file(self.root, self.draft(posting(title="Office Coordinator", url="")), CLOCK)
        self.assertEqual(odd["status"], "new")  # the user chose it: flagged, never dropped on its title
        self.assertIn("not one of the titles", odd["flag"])

    def test_duplicates(self):
        add.add_file(self.root, self.draft(posting()), CLOCK)
        with self.assertRaises(Refused) as same_link:
            add.add_file(self.root, self.draft(posting(title="Something else", url=LINKEDIN + "&x=1")), CLOCK)
        self.assertIn("manual-initech-4012345678", str(same_link.exception))
        with self.assertRaises(Refused):  # same company and title, a different link
            add.add_file(self.root, self.draft(posting(url="https://initech.test/careers/7")), CLOCK)
        again = add.add_file(self.root, self.draft(posting(url="")), CLOCK, anyway=True)
        self.assertEqual(again["key"], "manual-initech-support-operations-manager")

    def test_a_file_already_named_as_a_key(self):
        path = self.folder.description_path("manual-initech-lead")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(posting(url=""))
        self.assertEqual(add.add_file(self.root, path, CLOCK)["key"], "manual-initech-lead")

    def test_missing_header(self):
        with self.assertRaises(Refused):
            add.add_file(self.root, self.draft("Just some text about a job."), CLOCK)

    def test_a_scan_flags_the_same_job_found_on_its_board(self):
        add.add_file(self.root, self.draft(posting(title="Customer Support Manager", company="Acme")), CLOCK)
        self.scan()
        p = self.folder.load_postings()["postings"]["greenhouse-acme-1"]
        self.assertIn("the same job as one you pasted in on 2026-09-24", p["flag"])


class AddLinkTest(ScanBase):
    def link(self, url, **kw):
        self.addCleanup(net.use, net.use(Fake(answers())))
        return add.add_link(self.root, url, CLOCK, **kw)

    def test_the_same_key_a_scan_gives(self):
        out = self.link("https://boards.greenhouse.io/acme/jobs/1")
        self.assertTrue(out["saved"] and out["watched"])
        self.assertEqual((out["key"], out["source"], out["text_from"]), ("greenhouse-acme-1", "greenhouse", "board"))
        self.assertIn("Lead the Denver team.", self.folder.read_description("greenhouse-acme-1"))
        self.assertNotIn("greenhouse-acme-1", [p["key"] for p in self.scan()["new_postings"]])  # already saved

    def test_already_saved(self):
        self.scan()
        with self.assertRaises(Refused):
            self.link("https://boards.greenhouse.io/acme/jobs/1")

    def test_what_it_cant_read(self):
        self.assertEqual(self.link(LINKEDIN), {"saved": False, "why": "not_a_board_link"})
        self.assertEqual(self.link("https://boards.greenhouse.io/acme/jobs/999")["why"], "not_on_board")
        self.assertEqual(self.link("https://boards.greenhouse.io/broken/jobs/1")["why"], "board_failed")

    def test_cli(self):
        self.addCleanup(net.use, net.use(Fake(answers())))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(["add-link", "--folder", self.root, "https://boards.greenhouse.io/acme/jobs/4"]), 0)
        self.assertEqual(json.loads(out.getvalue())["key"], "greenhouse-acme-4")


class RecordedLinkTest(unittest.TestCase):
    """Real postings from the recorded public boards: a pasted link gets the key the scan gave it."""

    def setUp(self):
        self.root = os.path.join(tempfile.mkdtemp(), "Job Search")
        self.addCleanup(shutil.rmtree, os.path.dirname(self.root))
        shutil.copytree(FOLDER, self.root)
        self.replay = net.Replay(SAMPLE)
        self.addCleanup(net.use, net.use(self.replay))

    def test_links_on_five_systems(self):
        clock = Clock("America/New_York", fixed=AS_OF)
        links = {
            "https://boards.greenhouse.io/doordashusa/jobs/7983379": "greenhouse-doordash-7983379",
            "https://jobs.ashbyhq.com/ramp/1285aefc-d2c4-4f7c-8357-6e8f97fb22d4": "ashby-ramp-1285aefc-d2c4-4f7c-8357-6e8f97fb22d4",
            "https://jobs.lever.co/happyco/6c940fb8-9809-4b77-9207-07de545180eb": "lever-happyco-6c940fb8-9809-4b77-9207-07de545180eb",
            "https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/USA-CA-Pleasanton/Senior-Manager--Product-Management"
            "---Business-Technology-GTM---Customer-Support_JR-0109564-1": "workday-workdayinc-JR-0109564",
            "https://job-boards.greenhouse.io/thefarmersdog/jobs/8769521002": "greenhouse-thefarmersdog-8769521002",
        }
        with open(os.path.join(os.path.dirname(SAMPLE), "..", "fixtures", "sample-expected.json"), encoding="utf-8") as f:
            expected = json.load(f)["postings"]
        for url, key in links.items():
            out = add.add_link(self.root, url, clock)
            self.assertEqual(out["key"], key, url)
            self.assertEqual((out["status"], out.get("rule", "")), (expected[key]["status"], expected[key]["rule"]), url)
        self.assertEqual(self.replay.misses, [])


if __name__ == "__main__":
    unittest.main()
