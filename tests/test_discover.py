"""Finding a company's board, and checking one before it's saved. Found in real use (2026-10-12 to 14):
discover found nothing for NVIDIA (Workday), Retool (Gem), Mistral AI ("mistral.ai" on Ashby), Etsy or
Chewy, all of which the scanner can read; two boards added on 10-12 answered 404 from their first scan."""

import json
import os
import unittest
import urllib.error

from jobkit import configure, discover as disc, net, scan
from jobkit.boards import READERS, Context
from jobkit.errors import Refused
from tests.test_boards import Fake
from tests.test_scan import ScanBase

WD_BODY = json.dumps({"appliedFacets": {}, "limit": disc.SAMPLE, "offset": 0, "searchText": ""}, sort_keys=True)


def wd(host, tenant, site):
    return (f"https://{host}/wday/cxs/{tenant}/{site}/jobs", WD_BODY)


def http(code):
    return urllib.error.HTTPError("u", code, "x", None, None)


class DiscoverTest(unittest.TestCase):
    def use(self, answers):
        fake = Fake(answers)
        self.addCleanup(net.use, net.use(fake))
        return fake

    def test_workday_is_found_by_name(self):
        self.use({
            wd("acme.wd5.myworkdayjobs.com", "acme", "no-such-site-x"): http(422),  # not this host
            wd("acme.wd1.myworkdayjobs.com", "acme", "no-such-site-x"): http(404),  # this host, no such site
            wd("acme.wd1.myworkdayjobs.com", "acme", "careers"): {"total": 12, "jobPostings": [{"title": "Support Lead"}]},
        })
        found = disc.discover("Acme")
        self.assertEqual(found["boards"], [{"ats": "workday", "host": "acme.wd1.myworkdayjobs.com", "tenant": "acme",
                                            "site": "careers", "jobs": 12, "titles": ["Support Lead"]}])

    def test_gem_and_a_dotted_ashby_name_from_the_careers_page(self):
        page = "https://acme.example/careers"
        self.use({
            page: '<a href="https://jobs.ashbyhq.com/acme.ai">Jobs</a> <a href="https://jobs.gem.com/acme">More</a>',
            "https://api.ashbyhq.com/posting-api/job-board/acme.ai": {"jobs": [{"title": "Head of Support"}]},
            "https://api.gem.com/job_board/v0/acme/job_posts/": [{"title": "Support Ops Lead"}],
        })
        found = disc.discover("Acme", page=page)
        self.assertEqual([(e["ats"], e["token"], e["jobs"]) for e in found["embedded"]],
                         [("ashby", "acme.ai", 1), ("gem", "acme", 1)])

    def test_a_workday_link_is_read_properly(self):
        # "/en-US/" is the language, not the site (it was taken for the site before).
        link = "https://acme.wd5.myworkdayjobs.com/en-US/AcmeExternalCareerSite"
        self.use({wd("acme.wd5.myworkdayjobs.com", "acme", "AcmeExternalCareerSite"): {"total": 2000, "jobPostings": []},
                  wd("acme.wd5.myworkdayjobs.com", "acme", "no-such-site-x"): http(404)})
        found = disc.discover("Acme", page=link)
        self.assertEqual([(e["host"], e["site"], e["jobs"]) for e in found["embedded"]],
                         [("acme.wd5.myworkdayjobs.com", "AcmeExternalCareerSite", 2000)])

    def test_a_dead_link_on_the_careers_page_says_so(self):
        page = "https://acme.example/jobs"
        self.use({page: "https://job-boards.greenhouse.io/acme",
                  "https://boards-api.greenhouse.io/v1/boards/acme/jobs": http(404)})
        found = disc.discover("Acme", page=page)
        self.assertIn("404", found["embedded"][0]["error"])

    def test_a_blocked_network_is_not_no_board(self):
        class Blocked(Fake):
            def request(self, url, data=None, headers=None):
                raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")
        self.addCleanup(net.use, net.use(Blocked({})))
        found = disc.discover("Acme")
        self.assertTrue(found["blocked"])
        self.assertEqual(found["boards"], [])

    def test_the_gem_reader(self):
        self.use({"https://api.gem.com/job_board/v0/acme/job_posts/": [
            {"id": "9", "title": "Support Manager", "location": {"name": "Denver, United States"}, "location_type": "remote",
             "offices": [], "absolute_url": "https://jobs.gem.com/acme/9", "content_plain": "Lead the team.",
             "first_published_at": "2026-10-01T00:00:00Z"}]})
        recs = READERS["gem"]({"name": "Acme", "slug": "acme", "token": "acme"}, Context())
        self.assertEqual((recs[0]["key"], recs[0]["location"], recs[0]["posted"], recs[0]["description"]),
                         ("gem-acme-9", "Denver, United States; Remote", "2026-10-01", "Lead the team."))


class CheckBeforeSavingTest(ScanBase):
    def entry(self, **kw):
        return {"name": "Mistral AI", "slug": "mistral-ai", "ats": "ashby", "token": "mistral", **kw}

    def test_a_board_that_doesnt_work_isnt_saved(self):
        failing = lambda e: {"ok": False, "jobs": 0, "titles": [], "kind": "http", "error": "HTTPError: HTTP Error 404"}
        with self.assertRaises(Refused) as r:
            configure.add_company(self.root, self.entry(), check=failing)
        self.assertIn("discover", str(r.exception))
        self.assertNotIn("mistral-ai", [c["slug"] for c in configure.list_companies(self.root)])

    def test_one_that_works_is_saved_with_what_it_lists(self):
        working = lambda e: {"ok": True, "jobs": 216, "titles": ["AI Deployment Strategist"], "kind": "", "error": ""}
        out = configure.add_company(self.root, self.entry(token="mistral.ai"), check=working)
        self.assertEqual(out["checked"]["jobs"], 216)

    def test_unreachable_from_here_says_so(self):
        blocked = lambda e: {"ok": False, "jobs": 0, "titles": [], "kind": "proxy", "error": "407"}
        with self.assertRaises(Refused) as r:
            configure.add_company(self.root, self.entry(), check=blocked)
        self.assertIn("--unchecked", str(r.exception))

    def test_moving_a_board_reads_it_where_it_moved(self):
        asked = []
        working = lambda e: asked.append(e["token"]) or {"ok": True, "jobs": 3, "titles": [], "kind": "", "error": ""}
        configure.edit_company(self.root, "acme", {"token": "acme2"}, check=working)
        self.assertEqual(asked, ["acme2"])

    def test_check_board_reads_without_saving(self):
        self.addCleanup(net.use, net.use(Fake({"https://boards-api.greenhouse.io/v1/boards/acme/jobs": {"jobs": []}})))
        before = sorted(os.listdir(os.path.join(self.root, "data")))
        got = scan.check_board(self.root, {"name": "Acme", "slug": "acme", "ats": "greenhouse", "token": "acme"})
        self.assertEqual((got["ok"], got["error"]), (False, "the board answered, but lists no jobs"))
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "data"))), before)  # nothing written
