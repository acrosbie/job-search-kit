"""The jobs page: its data, stable job numbers, and the files written from the one template."""

import contextlib
import io
import json
import os
import re

from jobkit import cli, configure, page, track
from jobkit.clock import Clock
from tests.test_scan import FIXED, ScanBase
from tests.test_track import on

CLOCK = Clock("", fixed=FIXED)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class PageTest(ScanBase):
    def setUp(self):
        super().setUp()
        self.scan()
        self.folder.save_applications([])

    def test_what_the_page_shows(self):
        track.apply(self.root, on(1), key="greenhouse-acme-4", date="2026-09-01", top_pick=True)
        d = page.build(self.root, on(10))
        self.assertEqual(sorted(j["key"] for j in d["waiting"]), ["greenhouse-acme-1", "greenhouse-acme-9"])
        self.assertEqual(sorted(j["key"] for j in d["screened"]),
                         ["greenhouse-acme-3", "greenhouse-acme-5", "greenhouse-acme-6"])
        self.assertTrue(all(j["note"].startswith("Not a fit") for j in d["screened"]))
        self.assertEqual([(t["id"], t["route"], t["days"]) for t in d["todo"]], [("greenhouse-acme-4", "find_person", 9)])
        app = d["applications"][0]
        self.assertEqual((app["status"], app["closes_on"], app["num"] is not None), ("applied", "2026-09-22", True))
        self.assertEqual(d["counts"], {"waiting": 2, "to_do": 1, "open": 1, "applications": 1})
        self.assertEqual(d["title"], "My job search")
        self.assertEqual({j["key"]: j["by"] for j in d["screened"]}["greenhouse-acme-3"], "rule")

    def test_numbers_stay_put(self):
        first = {j["key"]: j["num"] for j in page.build(self.root, CLOCK)["waiting"]}
        self.assertEqual(sorted(first.values()), [1, 3, 6])  # numbered with the screened ones, in key order
        saved = self.folder.load_postings()["postings"]
        self.assertEqual(saved["greenhouse-acme-1"]["num"], first["greenhouse-acme-1"])
        track.apply(self.root, CLOCK, company="Globex", role="Support Director")
        again = page.build(self.root, CLOCK)
        self.assertEqual({j["key"]: j["num"] for j in again["waiting"]}, first)
        self.assertEqual(again["applications"][0]["num"], 7)  # six postings numbered before it

    def test_the_three_files(self):
        configure.set_value(self.root, "you.name", "Sam")
        out = page.refresh(self.root, CLOCK)
        self.assertEqual(out["waiting"], 3)
        html = read(self.folder.page_html)
        publish = read(self.folder.page_publish_html)
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertTrue(publish.startswith("<title>Sam&#x27;s job search</title>") or publish.startswith("<title>Sam's job search</title>"))
        self.assertIn(publish, html)
        data = json.loads(read(self.folder.page_json))
        self.assertEqual(data["title"], "Sam's job search")
        embedded = re.search(r'<script type="application/json" id="jobs-data">(.*?)</script>', publish, re.S).group(1)
        self.assertEqual(json.loads(embedded), data)

    def test_nothing_in_a_posting_can_break_out_of_the_page(self):
        p = self.folder.load_postings()
        p["postings"]["greenhouse-acme-1"]["title"] = '</script><script>alert(1)</script><!--'
        self.folder.save_postings(p)
        page.refresh(self.root, CLOCK)
        html = read(self.folder.page_html)
        self.assertNotIn("<script>alert(1)", html)
        self.assertEqual(html.count("</script>"), 2)  # the data block and the page's own script

    def test_the_data_always_fits_the_pages_storage(self):
        p = self.folder.load_postings()
        for i in range(40):
            p["postings"][f"manual-many-{i}"] = {"status": "new", "company": "Many", "title": f"Job {i}", "first_seen": "2026-09-24",
                                                 "note": "x" * 2000, "flag": "", "location": "", "url": "", "salary": ""}
        self.folder.save_postings(p)
        self.addCleanup(setattr, page, "MAX_BYTES", page.MAX_BYTES)
        page.MAX_BYTES = 20_000
        d = page.build(self.root, CLOCK)
        self.assertLessEqual(page._size(d), page.MAX_BYTES)
        self.assertEqual(d["screened"], [])
        self.assertGreater(d["more_waiting"], 0)
        self.assertEqual(d["counts"]["waiting"], 43)  # the summary still counts them all
        self.assertEqual(len(d["waiting"]) + d["more_waiting"], 43)

    def test_the_template_loads_nothing_from_elsewhere(self):
        template = read(page.TEMPLATE)
        for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', template):
            self.assertRegex(url, r"^https://fonts\.(googleapis|gstatic)\.com(/|$)", url)
        self.assertNotIn("<script src", template)
        self.assertLess(template.index("<title>"), 8000)
        for banned in ("alert(", "confirm(", "prompt(", "window.print"):
            self.assertNotIn(banned, template)

    def test_unsent_clicks_survive_a_rebuilt_page(self):
        # Before 0.6.0 the page kept clicks under its "as of" time, so the next scan's copy lost them.
        template = read(page.TEMPLATE)
        self.assertIn('var LOCAL = PREFIX + (data ? data.title : "");', template)
        self.assertNotIn("data.as_of : \"\")", template)
        self.assertIn("k.indexOf(PREFIX) === 0", template)  # older copies' clicks are gathered up too

    def test_the_file_only(self):
        # The user wants My jobs.html and no page in their Claude account: nothing is ever behind.
        from jobkit import configure, schedule, settings
        configure.set_value(self.root, "page.route", "file")
        s = settings.load(self.root)
        self.assertEqual((s.page["route"], s.page["url"]), ("file", ""))
        self.assertFalse(schedule.page_behind(self.root, s))

    def test_a_page_that_is_behind_gets_noticed(self):
        def run(*args):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main([args[0], "--folder", self.root, *args[1:]]), 0)
            return json.loads(out.getvalue())

        self.assertFalse(run("due")["page_behind"])  # no jobs page yet
        configure.set_value(self.root, "page.url", "https://claude.ai/artifact/example")
        self.assertTrue(run("due")["page_behind"])
        pushed = run("page", "--pushed")
        self.assertEqual(pushed["pushed"], json.loads(read(self.folder.page_json))["digest"])
        self.assertFalse(run("due")["page_behind"])  # written again since, but showing the same
        run("mark", "greenhouse-acme-1", "skipped", "--by", "user")
        self.assertTrue(run("due")["page_behind"])

    def test_the_fingerprint_ignores_when_it_was_written(self):
        a = page.build(self.root, CLOCK)
        b = page.build(self.root, Clock("", fixed=FIXED.replace(hour=20)))
        self.assertNotEqual(a["as_of"], b["as_of"])
        self.assertEqual(page.digest(a), page.digest(b))

    def test_every_change_rewrites_the_page(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["mark", "--folder", self.root, "greenhouse-acme-1", "worth_applying", "--by", "claude",
                      "--note", "Tailor: lead with the Denver team"])
        data = json.loads(read(self.folder.page_json))
        self.assertEqual(data["waiting"][0]["status"], "worth_applying")  # worth applying is listed first
        self.assertTrue(os.path.exists(self.folder.page_html))


if __name__ == "__main__":
    import unittest
    unittest.main()
