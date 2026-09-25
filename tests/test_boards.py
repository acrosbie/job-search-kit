"""Board readers against made-up answers. The real proof is the replay of recorded public boards;
these pin down the fiddly parts in isolation."""

import json
import unittest
import urllib.error

from jobkit import net
from jobkit.boards import READERS, Context


class Fake:
    """Answers by URL (and JSON body, for Workday's POSTs). Unknown URLs are a test failure."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def request(self, url, data=None, headers=None):
        key = (url, json.dumps(data, sort_keys=True)) if data is not None else url
        self.asked.append(key)
        answer = self.answers[key]
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer)

    def pause(self, seconds):
        pass


class ReaderTest(unittest.TestCase):
    def use(self, answers):
        fake = Fake(answers)
        self.addCleanup(net.use, net.use(fake))
        return fake

    def test_greenhouse_fetches_detail_only_when_asked(self):
        base = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
        fake = self.use({
            base: {"jobs": [{"id": 7, "title": "Support Manager ", "location": {"name": "Denver, CO"},
                             "absolute_url": "https://acme.test/7", "updated_at": "2026-09-01T10:00:00-04:00"}]},
            f"{base}/7": {"content": "&lt;p&gt;Lead the team&lt;/p&gt;"},
        })
        recs = READERS["greenhouse"]({"name": "Acme", "slug": "Acme Co", "token": "acme"}, Context())
        self.assertEqual(len(fake.asked), 1)
        r = recs[0]
        self.assertEqual((r["key"], r["title"], r["location"], r["posted"]),
                         ("greenhouse-acme-co-7", "Support Manager", "Denver, CO", "2026-09-01"))
        self.assertEqual(r["detail"](), "Lead the team")

    def test_workday_uses_country_facet_and_cap(self):
        base = "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/External/jobs"

        def body(offset, facets):
            return (base, json.dumps({"appliedFacets": facets, "limit": 20, "offset": offset, "searchText": ""}, sort_keys=True))

        us = {"locationCountry": ["us-id"]}
        page = lambda n, start: {"total": 45 if start == 0 else 0, "jobPostings": [
            {"title": f"Job {start + i}", "externalPath": f"/job/{start + i}", "bulletFields": [f"R{start + i}"],
             "locationsText": "2 Locations", "postedOn": "Posted Today"} for i in range(n)]}
        self.use({
            body(0, {}): {"facets": [{"facetParameter": "locationCountry",
                                      "values": [{"descriptor": "Canada", "id": "ca-id"}, {"descriptor": "United States of America", "id": "us-id"}]}]},
            body(0, us): page(20, 0),
            body(20, us): page(20, 20),
        })
        ctx = Context(workday={"country_facet": "^united states", "max_total": 40})
        recs = READERS["workday"]({"name": "Acme", "slug": "acme", "host": "acme.wd5.myworkdayjobs.com",
                                    "tenant": "acme", "site": "External"}, ctx)
        self.assertEqual(len(recs), 40)  # capped at max_total, though 45 exist
        self.assertEqual(recs[0]["location"], "")  # "2 Locations" is treated as unknown
        self.assertEqual(recs[0]["posted"], "Today")
        self.assertEqual(recs[0]["key"], "workday-acme-R0")

    def test_smartrecruiters_pages_through(self):
        base = "https://api.smartrecruiters.com/v1/companies/acme/postings"
        item = lambda i, country: {"id": str(i), "name": f"Job {i}", "releasedDate": "2026-09-02",
                                   "location": {"city": "Chennai" if country == "in" else "Denver", "country": country, "remote": i == 0}}
        self.use({
            f"{base}?limit=100&offset=0": {"totalFound": 101, "content": [item(i, "us") for i in range(100)]},
            f"{base}?limit=100&offset=100": {"totalFound": 101, "content": [item(100, "in")]},
        })
        recs = READERS["smartrecruiters"]({"name": "Acme", "slug": "acme", "token": "acme"}, Context())
        self.assertEqual(len(recs), 101)
        self.assertEqual(recs[0]["location"], "Denver, United States; Remote")
        self.assertEqual(recs[100]["location"], "Chennai, non-US (in)")

    def test_himalayas_skips_watched_and_keeps_partial_on_429(self):
        url = lambda q, p: "https://himalayas.app/jobs/api/search?q=" + q + "&country=United+States&page=" + str(p)
        job = lambda co, n: {"companyName": co, "companySlug": co.lower(), "guid": f"https://himalayas.app/c/{co}/jobs/{n}",
                             "title": "Support Manager", "locationRestrictions": ["United States"], "description": "<p>Hi</p>",
                             "minSalary": 90000, "maxSalary": 120000, "pubDate": "1790000000"}
        self.use({
            url("support", 1): {"jobs": [job("Acme", 1)] * 1 + [job("Other", n) for n in range(19)]},
            url("support", 2): urllib.error.HTTPError(url("support", 2), 429, "Too Many Requests", None, None),
        })
        ctx = Context(watched={"acme"})
        recs = READERS["himalayas"]({"name": "Himalayas", "slug": "himalayas", "queries": ["support"]}, ctx)
        self.assertEqual(len(recs), 19)  # Acme skipped; page 2 rate-limited, page 1 kept
        self.assertEqual(recs[0]["location"], "United States; Remote")
        self.assertTrue(recs[0]["description"].startswith("Compensation: $90,000 - $120,000"))
        self.assertEqual(recs[0]["key"], "himalayas-other-0")


if __name__ == "__main__":
    unittest.main()
