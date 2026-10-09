"""`start`: the first command of every conversation. One short answer with what's wrong, the last
scan, and `next`, what only Claude can do now, in order. `doctor`: the same checks in full."""

import contextlib
import io
import json
import os

from jobkit import __fingerprint__, cli, configure, interviews, start, track
from tests.test_track import TrackBase, on


def dos(out):
    return [n["do"] for n in out["next"]]


class StartTest(TrackBase):
    def test_a_folder_not_set_up_is_offered_setup(self):
        os.remove(os.path.join(self.root, "profile", "settings.toml"))
        out = start.start(self.root, on(24))
        self.assertFalse(out["folder_ready"])
        self.assertEqual(dos(out), ["offer_setup"])

    def test_an_engine_that_isnt_the_plugins_is_refreshed_first(self):
        self.assertEqual(dos(start.start(self.root, on(24), expect="0" * 16))[0], "refresh_engine")
        out = start.start(self.root, on(24), expect=__fingerprint__)
        self.assertTrue(out["engine"]["current"])
        self.assertNotIn("refresh_engine", dos(out))

    def test_a_new_user_gets_a_jobs_page_and_one_who_has_one_has_their_clicks_read(self):
        self.assertIn("publish_page", dos(start.start(self.root, on(24))))
        configure.set_value(self.root, "page.url", "https://claude.ai/artifact/x")
        out = start.start(self.root, on(24))
        self.assertEqual(dos(out)[:2], ["read_clicks", "republish_page"])  # no design recorded yet
        configure.set_value(self.root, "page.route", "file")
        self.assertFalse({"read_clicks", "publish_page", "push_page"} & set(dos(start.start(self.root, on(24)))))

    def test_day_21_is_named_but_not_closed(self):
        # News the user brings is recorded first; then `due` closes what's left.
        track.apply(self.root, on(1), key="greenhouse-acme-1", date="2026-09-01", channel="company_site", top_pick=True)
        out = start.start(self.root, on(24))
        step = next(n for n in out["next"] if n["do"] == "run_due_after_news")
        self.assertEqual([a["id"] for a in step["applications"]], ["greenhouse-acme-1"])
        self.assertEqual(track.find(track.load(self.root), "greenhouse-acme-1")["status"], "applied")

    def test_open_applications_with_no_channel_are_asked_three_at_a_time(self):
        for i in range(5):
            track.apply(self.root, on(20), company="Globex", role=f"Lead {i}")
        step = next(n for n in start.start(self.root, on(24))["next"] if n["do"] == "ask_channels")
        self.assertEqual((len(step["applications"]), step["more"]), (3, 3))  # and test_scan's own application

    def test_an_interview_soon_with_no_time_asks_for_it(self):
        track.apply(self.root, on(20), key="greenhouse-acme-1", channel="company_site", top_pick=True)
        interviews.schedule(self.root, on(24), "greenhouse-acme-1", "2026-09-26")
        out = dos(start.start(self.root, on(24)))
        self.assertLess(out.index("ask_interview_time"), out.index("offer_prep"))

    def test_a_scan_that_reached_nothing_is_said(self):
        self.folder.log_run({"at": "2026-09-24T09:00:00-06:00", "status": "blocked", "boards": 0, "failed": 3})
        out = start.start(self.root, on(24))
        self.assertEqual(out["scan"]["last_status"], "blocked")
        self.assertIn("say_last_scan_failed", dos(out))

    def test_open_applications_with_no_company_need_the_user(self):
        track.apply(self.root, on(20), company="Unknown", role="Senior Manager")
        step = next(n for n in start.start(self.root, on(24))["next"] if n["do"] == "tell_about_records")
        self.assertEqual(step["problems"][0]["what"], "open applications with no company name")

    def test_whats_new_is_said_once(self):
        from jobkit import __version__, news
        self.folder.log_run({"at": "2026-09-20T09:00:00-06:00", "boards": 3})
        step = next(n for n in start.start(self.root, on(24))["next"] if n["do"] == "say_whats_new")
        minor = tuple(int(x) for x in __version__.split("."))[:2]
        self.assertEqual(step["lines"], [news.NEWS[v] for v in sorted(news.NEWS, key=news._v) if news._v(v)[:2] == minor])
        self.assertNotIn("say_whats_new", dos(start.start(self.root, on(24))))
        self.folder.write_json(os.path.join(self.folder.data, "kit.json"), {"seen_version": "0.9.0"})
        lines = next(n for n in start.start(self.root, on(24))["next"] if n["do"] == "say_whats_new")["lines"]
        self.assertEqual(lines[0], news.NEWS["0.10.0"])

    def test_a_folder_being_set_up_hears_no_news(self):
        open(self.folder.runs_log, "w").close()  # no scan yet (TrackBase's own scan taken away)
        self.assertNotIn("say_whats_new", dos(start.start(self.root, on(24))))

    def test_from_the_command_line_and_doctor(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(["start", "--folder", self.root, "--expect", __fingerprint__]), 0)
        self.assertTrue(json.loads(out.getvalue())["engine"]["current"])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(["doctor", "--folder", self.root]), 0)
        d = json.loads(out.getvalue())
        self.assertTrue(d["engine"]["files_match"])
        self.assertEqual((d["records"]["applications"], d["problems"]), (1, []))
        self.assertTrue(d["ok"])
