"""Phase 4's proof, run on the made-up New York job seeker and the recorded public boards: three weeks
of use leave every file and the page correct.

    09-24  a scan; they apply to Ramp and HappyCo
    10-05  they paste a LinkedIn link, apply to it as a top pick, and skip a job on the jobs page
    10-08  Ramp replies: a phone screen
    10-15  day 21 for HappyCo: the one application closed, with Ramp's screen untouched
"""

import datetime as dt
import json
import os
import re
import shutil
import tempfile
import sys
import unittest

from jobkit import add, choices, configure, net, page, scan, store, track
from jobkit.clock import Clock
from tests.test_recorded import FOLDER, SAMPLE

RAMP = "ashby-ramp-1285aefc-d2c4-4f7c-8357-6e8f97fb22d4"
HAPPYCO = "lever-happyco-6c940fb8-9809-4b77-9207-07de545180eb"
LINKEDIN = "https://www.linkedin.com/jobs/view/support-operations-manager-at-initech-4099887766/"
PASTED = """# Support Operations Manager

- Company: Initech
- Location: New York, NY
- URL: https://www.linkedin.com/jobs/view/support-operations-manager-at-initech-4099887766/
- Posted: (unknown)

---

Initech is hiring a Support Operations Manager to run the tools, reporting and staffing plans for a
40-person support team in New York. Hybrid, three days a week in the office.
Pay: $120,000 to $140,000.
"""


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def at(md, hour=14):
    return Clock("America/New_York", fixed=dt.datetime.fromisoformat(f"2026-{md}T{hour:02d}:00:00+00:00"))


class ScriptedWeekTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = root = os.path.join(tempfile.mkdtemp(), "Job Search")
        cls.addClassCleanup(shutil.rmtree, os.path.dirname(root))
        shutil.copytree(FOLDER, root)
        store.Folder(root).save_applications([])  # start this job seeker with no applications

        # 09-24: a scan of the recorded boards, then two applications.
        previous = net.use(net.Replay(SAMPLE))
        try:
            scan.run(root, clock=at("09-24", 19))
        finally:
            net.use(previous)
        page.refresh(root, at("09-24", 19))
        cls.first_numbers = {j["key"]: j["num"] for j in page.build(root, at("09-24", 19))["waiting"]}
        track.apply(root, at("09-24", 20), key=RAMP, channel="company_site", top_pick=False)
        track.apply(root, at("09-24", 20), key=HAPPYCO, channel="company_site", top_pick=False)

        # 10-05: a pasted LinkedIn link, applied to as a top pick, and a click on the jobs page.
        draft = os.path.join(os.path.dirname(root), "pasted.md")
        with open(draft, "w", encoding="utf-8") as f:
            f.write(PASTED)
        cls.pasted = add.add_file(root, draft, at("10-05"), text_from="link")
        track.apply(root, at("10-05"), key=cls.pasted["key"], channel="linkedin", top_pick=True)
        page.refresh(root, at("10-05"))
        waiting = json.loads(read(store.Folder(root).page_json))["waiting"]
        cls.skipped = next(j for j in waiting if j["status"] == "new")
        cls.clicks = choices.record(root, at("10-05", 15), [{
            "id": "c-week-1", "at": "2026-10-05T14:30:00.000Z", "action": "skip", "key": cls.skipped["key"],
            "num": cls.skipped["num"], "label": "a waiting job", "note": "too junior", "channel": "", "top_pick": "",
            "contact": "", "recorded": ""}])

        # 10-08: Ramp replies with a phone screen. 10-15: day 21 for HappyCo.
        track.track(root, at("10-08"), RAMP, "screen", note="recruiter call booked for Friday")
        cls.due = track.due(root, at("10-15"))
        cls.summary = page.refresh(root, at("10-15"))
        cls.folder = store.Folder(root)

    def apps(self):
        return {a["id"]: a for a in track.load(self.root)}

    def test_the_pasted_linkedin_link(self):
        key = self.pasted["key"]
        self.assertEqual(key, "manual-initech-4099887766")
        p = self.folder.load_postings()["postings"][key]
        self.assertEqual((p["source"], p["text_from"], p["status"], p["salary"]), ("manual", "link", "applied", "$120K to $140K"))
        self.assertIn("40-person support team", self.folder.read_description(key))

    def test_three_applications_one_reply_one_close(self):
        a = self.apps()
        self.assertEqual(len(a), 3)
        self.assertEqual(a[RAMP]["status"], "screen")
        self.assertEqual(a[HAPPYCO]["status"], "presumed_rejected")
        self.assertEqual(a[self.pasted["key"]]["status"], "applied")
        self.assertEqual([x["id"] for x in self.due["closed_now"]], [HAPPYCO])
        self.assertEqual([h.get("status") for h in a[RAMP]["history"]], ["applied", "screen"])
        close = a[HAPPYCO]["history"][-1]
        self.assertEqual((close["by"], close["date"]), ("engine", "2026-10-15"))
        self.assertEqual((a[self.pasted["key"]]["channel"], a[self.pasted["key"]]["top_pick"]), ("linkedin", True))

    def test_the_follow_up_is_routed(self):
        self.assertEqual([(x["id"], x["days"]) for x in self.due["find_person"]], [(self.pasted["key"], 10)])
        self.assertEqual(self.due["send"] + self.due["closing"], [])

    def test_postings_and_verdicts(self):
        p = self.folder.load_postings()["postings"]
        self.assertEqual((p[RAMP]["status"], p[HAPPYCO]["status"]), ("applied", "applied"))
        self.assertEqual(p[self.skipped["key"]]["status"], "skipped")
        mine = [d for d in self.folder.read_decisions() if d["by"] == "user"]
        self.assertEqual(sorted((d["key"], d["verdict"]) for d in mine),
                         sorted([(RAMP, "applied"), (HAPPYCO, "applied"), (self.pasted["key"], "applied"),
                                 (self.skipped["key"], "skipped")]))
        click = next(d for d in mine if d.get("choice") == "c-week-1")
        self.assertEqual(dt.datetime.fromisoformat(click["at"]), dt.datetime(2026, 10, 5, 14, 30, tzinfo=dt.timezone.utc))
        self.assertEqual(click["reason"], "too junior")  # recorded as of the click, not of when Claude read it
        self.assertEqual([c["id"] for c in self.clicks["recorded"]], ["c-week-1"])

    def test_the_page(self):
        data = json.loads(read(self.folder.page_json))
        status = {x["id"]: x["status"] for x in data["applications"]}
        self.assertEqual(status, {RAMP: "screen", HAPPYCO: "presumed_rejected", self.pasted["key"]: "applied"})
        self.assertEqual([(t["id"], t["route"]) for t in data["todo"]], [(self.pasted["key"], "find_person")])
        waiting = {j["key"] for j in data["waiting"]}
        self.assertFalse(waiting & {RAMP, HAPPYCO, self.pasted["key"], self.skipped["key"]})
        for key, num in self.first_numbers.items():  # numbers given on day one never moved
            if key in waiting:
                self.assertEqual(next(j["num"] for j in data["waiting"] if j["key"] == key), num)
        self.assertEqual(data["counts"]["open"], 2)
        self.assertEqual(dt.datetime.fromisoformat(data["as_of"]), dt.datetime(2026, 10, 15, 14, tzinfo=dt.timezone.utc))

        html = read(self.folder.page_html)
        embedded = re.search(r'id="jobs-data">(.*?)</script>', html, re.S).group(1)
        self.assertEqual(json.loads(embedded), data)
        self.assertEqual(self.summary["applications"], 3)

    def test_the_cowork_checker_agrees(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
        import check_week
        configure.set_value(self.root, "page.url", "https://claude.ai/artifact/example")
        configure.set_value(self.root, "page.route", "storage")
        page.refresh(self.root, at("10-15"))
        want = {"pasted": {"company": "Initech", "text_from": "link"}, "page_clicks": 1, "applications": [
            {"company": "Initech", "status": "applied", "top_pick": True, "channel": "linkedin", "route": "find_person"},
            {"company": "Ramp", "status": "screen", "never": ["presumed_rejected"]},
            {"company": "HappyCo", "status": "presumed_rejected"}]}
        failed = [what for passed, what in check_week.check(self.root, want, today=dt.date(2026, 10, 15)) if not passed]
        self.assertEqual(failed, [])

    def test_nothing_was_deleted_and_backups_exist(self):
        for name in ("postings.backup.json", "applications.backup.json"):
            self.assertTrue(os.path.exists(os.path.join(self.root, "data", name)), name)


if __name__ == "__main__":
    unittest.main()
