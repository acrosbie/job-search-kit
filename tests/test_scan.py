"""A whole scan on made-up boards, for the made-up Denver support manager in test_screen."""

import contextlib
import datetime as dt
import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error

from jobkit import cli, net, scan, store
from jobkit.clock import Clock
from tests.test_boards import Fake
from tests.test_screen import EXAMPLE

GH = "https://boards-api.greenhouse.io/v1/boards"
FIXED = dt.datetime(2026, 9, 24, 18, 0, tzinfo=dt.timezone.utc)


def job(i, title, location):
    return {"id": i, "title": title, "location": {"name": location}, "absolute_url": f"https://acme.test/{i}",
            "updated_at": "2026-09-20T09:00:00Z"}


BOARD = {"jobs": [
    job(1, "Customer Support Manager", "Denver, CO"),            # new
    job(2, "Customer Support Manager", "Chicago, IL"),           # same role, second place: collapsed onto #1
    job(3, "Support Operations Manager", "Austin, TX"),          # far away, no remote wording: rejected
    job(4, "Customer Support Director", "Boulder, CO"),          # remote-only area, says remote: kept, flagged
    job(5, "Customer Support Manager, Enterprise", "Aurora"),    # quota language: rejected
    job(6, "Support Operations Director", "Lakewood"),           # pay under the line: rejected
    job(7, "Customer Support Specialist", "Denver"),             # no level word: dropped on title
    job(8, "Customer Support Manager", "London"),                # abroad: dropped on place
    job(9, "Head of Support Operations Manager", "Denver"),      # already applied elsewhere: flagged
]}
DETAILS = {
    1: "Lead the Denver team.",
    3: "Hybrid in Austin, three days a week.",
    4: "This role is remote.",
    5: "Own a quota and a book of business.",
    6: "Pay: $60K to $80K.",
    9: "Run support operations.",
}


def answers(board=BOARD):
    a = {f"{GH}/acme/jobs": board, f"{GH}/globex/jobs": {"jobs": []}}
    for i, text in DETAILS.items():
        a[f"{GH}/acme/jobs/{i}"] = {"content": f"&lt;p&gt;{text}&lt;/p&gt;"}
    a[f"{GH}/broken/jobs"] = RuntimeError("board down")
    return a


class ScanBase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "profile"))
        os.makedirs(os.path.join(self.root, "data"))
        with open(os.path.join(self.root, "profile", "settings.toml"), "w", encoding="utf-8") as f:
            f.write(EXAMPLE)
        with open(os.path.join(self.root, "profile", "companies.toml"), "w", encoding="utf-8") as f:
            f.write('[[company]]\nname = "Acme"\nslug = "acme"\nats = "greenhouse"\ntoken = "acme"\n\n'
                    '[[company]]\nname = "Globex"\nslug = "globex"\nats = "greenhouse"\ntoken = "globex"\n\n'
                    '[[company]]\nname = "Broken"\nslug = "broken"\nats = "greenhouse"\ntoken = "broken"\n\n'
                    '[[company]]\nname = "Initech"\nslug = "initech"\nats = "manual"\ncareers_url = "https://initech.test/jobs"\n')
        with open(os.path.join(self.root, "data", "applications.json"), "w", encoding="utf-8") as f:
            json.dump({"applications": [{"company": "Acme", "role": "Head of Support Operations Manager",
                                         "urls": [], "applied": "2026-09-10"}]}, f)
        self.folder = store.Folder(self.root)

    def scan(self, board=BOARD):
        self.addCleanup(net.use, net.use(Fake(answers(board))))
        return scan.run(self.root, clock=Clock("", fixed=FIXED), workers=2)


class ScanTest(ScanBase):
    def test_first_scan(self):
        out = self.scan()
        self.assertEqual((out["boards"], out["failed"], out["read"], out["dropped_title"], out["dropped_location"]),
                         (2, 1, 9, 1, 1))
        self.assertEqual(out["matched"], 6)  # 9 read, 1 title, 1 place, 1 duplicate collapsed
        self.assertEqual(sorted(p["key"] for p in out["new_postings"]),
                         ["greenhouse-acme-1", "greenhouse-acme-4", "greenhouse-acme-9"])
        self.assertEqual(out["rejected_by_rule"], {"location_in_country": 1, "phrases:quota": 1, "pay": 1})
        self.assertEqual(out["failures"][0]["board"], "Broken")
        self.assertEqual(out["check_by_hand"], [{"name": "Initech", "careers_url": "https://initech.test/jobs"}])

        p = self.folder.load_postings()["postings"]
        self.assertEqual(p["greenhouse-acme-1"]["location"], "Denver, CO; Chicago, IL")
        self.assertEqual(p["greenhouse-acme-4"]["flag"], "near you, but only if it's remote")
        self.assertIn("already applied here on 2026-09-10", p["greenhouse-acme-9"]["flag"])
        self.assertEqual(p["greenhouse-acme-6"]["salary"], "$60K to $80K")
        self.assertEqual((p["greenhouse-acme-6"]["status"], p["greenhouse-acme-6"]["rule"]), ("not_a_fit", "pay"))
        self.assertEqual(p["greenhouse-acme-1"]["first_seen"], "2026-09-24")

        decisions = self.folder.read_decisions()
        self.assertEqual(sorted(d["key"] for d in decisions), ["greenhouse-acme-3", "greenhouse-acme-5", "greenhouse-acme-6"])
        self.assertTrue(all(d["by"] == "rule" for d in decisions))
        self.assertEqual(self.folder.read_runs()[-1]["matched"], 6)
        self.assertIn("Lead the Denver team.", self.folder.read_description("greenhouse-acme-1"))

    def test_second_scan_marks_gone_and_keeps_verdicts(self):
        self.scan()
        smaller = {"jobs": [j for j in BOARD["jobs"] if j["id"] != 4]}
        out = self.scan(smaller)
        self.assertEqual(out["new_postings"], [])
        p = self.folder.load_postings()["postings"]
        self.assertEqual(p["greenhouse-acme-4"]["gone"], "2026-09-24")
        self.assertNotIn("gone", p["greenhouse-acme-1"])
        self.assertEqual(p["greenhouse-acme-6"]["status"], "not_a_fit")
        self.assertTrue(os.path.exists(self.folder.backup_json))


    def test_a_description_that_cant_be_read_is_kept_and_read_again(self):
        # Found in a bug hunt: the error message was saved as the description, and a job outside
        # the commute was then turned away for having no remote wording, for good.
        a = answers()
        a[f"{GH}/acme/jobs/3"] = TimeoutError("timed out")
        self.addCleanup(net.use, net.use(Fake(a)))
        out = scan.run(self.root, clock=Clock("", fixed=FIXED), workers=2)
        p = self.folder.load_postings()["postings"]["greenhouse-acme-3"]
        self.assertEqual((p["status"], p.get("unread")), ("new", True))
        self.assertIn("couldn't be read", p["flag"])
        self.assertIn("greenhouse-acme-3", [x["key"] for x in out["new_postings"]])
        self.assertNotIn("greenhouse-acme-3", [d["key"] for d in self.folder.read_decisions()])
        # The next scan reads it, and screens it as any new posting.
        out = self.scan()
        p = self.folder.load_postings()["postings"]["greenhouse-acme-3"]
        self.assertEqual((p["status"], p["rule"], "unread" in p), ("not_a_fit", "location_in_country", False))
        self.assertIn("Hybrid in Austin", self.folder.read_description("greenhouse-acme-3"))
        self.assertEqual([x["key"] for x in out["rejected_postings"]], ["greenhouse-acme-3"])

    def test_a_listed_job_is_not_gone_because_the_filter_would_drop_it_now(self):
        # Found in a bug hunt: only jobs passing today's filters counted as listed, so a job added
        # by link, or kept under older settings, read "No longer on the company's job board".
        self.scan()
        state = self.folder.load_postings()
        state["postings"]["greenhouse-acme-7"] = {"company": "Acme", "title": "Customer Support Specialist",
                                                  "status": "worth_applying", "source": "greenhouse",
                                                  "first_seen": "2026-09-20", "last_seen": "2026-09-20"}
        self.folder.save_postings(state)
        self.scan()
        p = self.folder.load_postings()["postings"]["greenhouse-acme-7"]
        self.assertNotIn("gone", p)
        self.assertEqual(p["last_seen"], "2026-09-24")

    def test_one_board_isnt_the_days_scan(self):
        from jobkit import schedule, settings
        self.scan()
        runs = self.folder.read_runs()
        self.addCleanup(net.use, net.use(Fake(answers())))
        scan.run(self.root, only="acme", clock=Clock("", fixed=FIXED + dt.timedelta(days=2)), workers=2)
        runs = self.folder.read_runs()
        self.assertEqual(runs[-1]["only"], "acme")
        s = settings.load(self.root)
        s.schedule["scan"] = "daily"
        self.assertTrue(schedule.scan_overdue(s, runs, Clock("", fixed=FIXED + dt.timedelta(days=2))))


class MarkTest(ScanBase):
    def mark(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["mark", "--folder", self.root, *args])
        return code, err.getvalue()

    def test_a_job_that_moves_keeps_its_other_flags(self):
        self.scan()
        state = self.folder.load_postings()
        state["postings"]["greenhouse-acme-1"]["flags"].append({"code": "contract", "text": "contract or interim (contract)"})
        self.folder.save_postings(state)
        self.scan({"jobs": [job(1, "Customer Support Manager", "Denver, CO")]})  # Chicago no longer listed
        e = self.folder.load_postings()["postings"]["greenhouse-acme-1"]
        self.assertEqual(e["location"], "Denver, CO")
        self.assertEqual([f["code"] for f in e["flags"]], ["contract"])  # the old place flag went; contract stayed
        self.assertEqual(e["flag"], "contract or interim (contract)")

    def test_a_job_is_gone_only_when_its_own_board_answered(self):
        # acme answers; acme-health, whose keys also start "greenhouse-acme-", is down today.
        with open(os.path.join(self.root, "profile", "companies.toml"), "a", encoding="utf-8") as f:
            f.write('\n[[company]]\nname = "Acme Health"\nslug = "acme-health"\nats = "greenhouse"\ntoken = "acmehealth"\n')
        state = self.folder.load_postings()
        state["postings"]["greenhouse-acme-health-77"] = {
            "company": "Acme Health", "title": "Support Manager", "status": "new", "source": "greenhouse",
            "first_seen": "2026-09-01", "last_seen": "2026-09-01", "location": "Denver", "url": "", "salary": ""}
        self.folder.save_postings(state)
        a = answers()
        a[f"{GH}/acmehealth/jobs"] = RuntimeError("board down")
        self.addCleanup(net.use, net.use(Fake(a)))
        scan.run(self.root, clock=Clock("", fixed=FIXED), workers=2)
        self.assertNotIn("gone", self.folder.load_postings()["postings"]["greenhouse-acme-health-77"])
        self.assertEqual(scan.owner("greenhouse-acme-health-77", [("greenhouse-acme-", "acme"),
                                                                   ("greenhouse-acme-health-", "acme-health")]), "acme-health")

    def test_user_decision_stands(self):
        self.scan()
        self.assertEqual(self.mark("greenhouse-acme-3", "worth_applying", "--by", "user")[0], 0)
        self.assertEqual(self.folder.read_decisions()[-1]["reverses"], "not_a_fit")  # overturned the location rule
        code, err = self.mark("greenhouse-acme-3", "not_a_fit", "--by", "claude")
        self.assertEqual(code, 3)
        self.assertIn("their decision stands", err)
        self.assertEqual(self.folder.load_postings()["postings"]["greenhouse-acme-3"]["status"], "worth_applying")

    def test_only_the_user_marks_applied(self):
        self.scan()
        self.assertEqual(self.mark("greenhouse-acme-1", "applied", "--by", "claude")[0], 3)
        # Even the user's goes through apply, which asks how they applied and if it's a top pick.
        code, err = self.mark("greenhouse-acme-1", "applied", "--by", "user")
        self.assertEqual(code, 3)
        self.assertIn("apply KEY --channel", err)


class ScanOutTest(ScanBase):
    """Found in real use (2026-10-12): scans run from PowerShell on Windows were saved with `>`, which
    wrote a byte-order mark. `--out` writes the result itself, as plain UTF-8, or what went wrong."""

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(list(args))
        return code, out.getvalue()

    def test_the_result_goes_to_the_file(self):
        self.addCleanup(net.use, net.use(Fake(answers())))
        target = os.path.join(self.root, "data", "scan-latest.json")
        code, printed = self.run_cli("scan", "--folder", self.root, "--as-of", FIXED.isoformat(), "--out", target)
        self.assertEqual((code, printed), (0, ""))
        with open(target, "rb") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(b"{"))  # no byte-order mark
        got = json.loads(raw.decode("utf-8"))
        self.assertEqual(got["new"], 3)
        # Every job the scan names carries its number and link (found in real use, 2026-10-14: "what's
        # the link to this one?").
        for p in got["new_postings"] + got["rejected_postings"]:
            self.assertTrue(p["num"] and p["url"].startswith("https://"), p)

    def test_what_went_wrong_goes_to_the_file(self):
        os.remove(os.path.join(self.root, "profile", "settings.toml"))
        target = os.path.join(self.root, "scan-latest.json")
        code, _ = self.run_cli("scan", "--folder", self.root, "--out", target)
        self.assertEqual(code, 1)
        with open(target, encoding="utf-8") as f:
            got = json.load(f)
        self.assertEqual(got["exit"], 1)
        self.assertIn("settings.toml", got["error"])


class BlockedScanTest(ScanBase):
    """Found in real use (2026-10-08): Claude's sandbox reached no job board through its proxy, and the
    scan logged 0 boards read as if it were a scan. A blocked scan now changes nothing but the log."""

    def blocked(self, url, data=None, headers=None):
        raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")

    def test_a_blocked_network_changes_nothing(self):
        self.scan()
        titles = read_file(self.folder.titles_tsv)
        boards = self.folder.load_postings()["boards"]
        fake = Fake({})
        fake.request = self.blocked
        self.addCleanup(net.use, net.use(fake))
        out = scan.run(self.root, clock=Clock("", fixed=FIXED + dt.timedelta(days=1)), workers=2)
        self.assertEqual((out["status"], out["boards"], out["watched"], out["failures_by_kind"]),
                         ("blocked", 0, 3, {"proxy": 3}))
        self.assertEqual(read_file(self.folder.titles_tsv), titles)
        self.assertEqual(self.folder.load_postings()["boards"], boards)
        self.assertEqual(self.folder.read_runs()[-1]["status"], "blocked")

    def test_some_boards_unreachable_is_partial_and_not_held_against_them(self):
        a = answers()
        a[f"{GH}/globex/jobs"] = urllib.error.URLError("Tunnel connection failed: 403 Forbidden")
        self.addCleanup(net.use, net.use(Fake(a)))
        out = scan.run(self.root, clock=Clock("", fixed=FIXED), workers=2)
        self.assertEqual((out["status"], out["boards"], out["failures_by_kind"]), ("partial", 1, {"proxy": 1, "other": 1}))
        boards = self.folder.load_postings()["boards"]
        self.assertEqual((boards["globex"]["fails"], boards["broken"]["fails"]), (0, 1))

    def test_every_board_failing_for_its_own_reasons_saves_nothing(self):
        self.scan()
        before = read_file(self.folder.postings_json)
        a = {f"{GH}/acme/jobs": RuntimeError("down"), f"{GH}/globex/jobs": RuntimeError("down"),
             f"{GH}/broken/jobs": RuntimeError("down")}
        self.addCleanup(net.use, net.use(Fake(a)))
        out = scan.run(self.root, clock=Clock("", fixed=FIXED + dt.timedelta(days=1)), workers=2)
        self.assertEqual(out["status"], "failed")
        self.assertEqual(read_file(self.folder.postings_json), before)

    def test_probe_reads_three_boards_and_saves_nothing(self):
        fake = Fake({})
        fake.request = self.blocked
        self.addCleanup(net.use, net.use(fake))
        out = scan.probe(self.root)
        self.assertEqual((out["network"], out["tried"], out["reached"], out["watched"]), ("blocked", 3, 0, 3))
        self.assertFalse(os.path.exists(self.folder.runs_log))
        self.addCleanup(net.use, net.use(Fake(answers())))
        self.assertEqual(scan.probe(self.root)["network"], "some")  # Broken is down; the others answer

    def test_how_a_fetch_failed(self):
        self.assertEqual(net.failure_kind(urllib.error.URLError("Tunnel connection failed: 403 Forbidden")), "proxy")
        self.assertEqual(net.failure_kind(urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))), "offline")
        self.assertEqual(net.failure_kind(urllib.error.URLError("[Errno 11001] getaddrinfo failed")), "offline")
        self.assertEqual(net.failure_kind(TimeoutError("timed out")), "timeout")
        self.assertEqual(net.failure_kind(urllib.error.HTTPError("u", 404, "Not Found", None, None)), "http")
        self.assertEqual(net.failure_kind(RuntimeError("board down")), "other")


def read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    unittest.main()


class QueueTest(ScanBase):
    def test_queue_carries_cooldown_facts(self):
        from jobkit import queue as triage_queue
        self.scan()
        apps = {"applications": [
            {"company": "Acme", "role": "Head of Support Operations Manager", "urls": [], "applied": "2026-09-10",
             "applied_date": "2026-09-10"},
            {"company": "ACME", "role": "Old one", "urls": [], "applied": "2026-06-01", "applied_date": "2026-06-01"},
            {"company": "Acme", "role": "LinkedIn one", "urls": [], "applied": "2w", "applied_date": ""},
        ]}
        with open(self.folder.applications_json, "w", encoding="utf-8") as f:
            json.dump(apps, f)
        q = triage_queue.queue(self.root, Clock("", fixed=FIXED))
        self.assertEqual(q["count"], 3)
        self.assertEqual(q["cooldown_days"], 30)
        first = q["postings"][0]
        self.assertEqual(first["description_file"], f"data/postings/{first['key']}.md")
        recent = first["applied_recently_at_company"]
        self.assertEqual([r["role"] for r in recent], ["Head of Support Operations Manager", "LinkedIn one"])
        self.assertFalse(recent[1]["date_known"])
        self.assertEqual(len(first["same_company_in_queue"]), 2)

    def test_newest_first_in_batches(self):
        # Found in an audit: the first scan's backlog came sorted by company with no date, so the
        # day-2 "go through the new ones" got all of it at once.
        from jobkit import queue as triage_queue
        self.scan()
        state = self.folder.load_postings()
        waiting = sorted(k for k, v in state["postings"].items() if v["status"] == "new")
        for i, k in enumerate(waiting):
            state["postings"][k]["posted"] = f"2026-09-1{i}"
        self.folder.save_postings(state)
        q = triage_queue.queue(self.root, Clock("", fixed=FIXED), limit=2)
        self.assertEqual((q["count"], q["shown"], q["more"]), (len(waiting), 2, len(waiting) - 2))
        self.assertEqual([p["key"] for p in q["postings"]], list(reversed(waiting))[:2])
        self.assertEqual(q["postings"][0]["posted"], f"2026-09-1{len(waiting) - 1}")
