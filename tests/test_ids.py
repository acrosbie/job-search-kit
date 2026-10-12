"""Every application has its own id. Found in real use (2026-10-08): two applications to the same
TikTok title, sent on 09-03 and 09-14, shared one id, so a change to either could land on the other,
and a save made while another command wrote could fold the two rows into one."""

import json

from jobkit import choices, store, track
from jobkit.errors import Refused
from tests.test_track import TrackBase, on

SHARED = "app-tiktok-usds-ux-and-support-program-manager"


def row(ident, applied, url, num):
    return {"id": ident, "key": "", "company": "TikTok", "role": "USDS UX and Support Program Manager",
            "urls": [url], "applied_date": applied, "status": "applied", "num": num,
            "history": [{"date": applied, "status": "applied", "by": "import"}]}


class SharedIdTest(TrackBase):
    def setUp(self):
        super().setUp()
        rows = [row(SHARED, "2026-09-14", "https://example.test/4466", 121),
                row(SHARED, "2026-09-03", "https://example.test/4453", 110),
                # imported with no id at all: the id comes from the company and role, so these two collide too
                {"company": "Unknown", "role": "Senior Manager", "urls": ["https://example.test/a"], "applied": "2026-08-16"},
                {"company": "Unknown", "role": "Senior Manager", "urls": ["https://example.test/b"], "applied": "2026-08-16"}]
        with open(self.folder.applications_json, "w", encoding="utf-8") as f:
            json.dump({"applications": rows}, f)

    def written(self):
        with open(self.folder.applications_json, encoding="utf-8") as f:
            return json.load(f)["applications"]

    def test_repaired_once_the_same_way_and_written(self):
        apps = track.load(self.root)
        self.assertEqual([a["id"] for a in apps],
                         [SHARED, SHARED + "-2026-09-03", "app-unknown-senior-manager", "app-unknown-senior-manager-2026-08-16"])
        self.assertEqual([a["num"] for a in apps[:2]], [121, 110])  # the page's numbers stay with their rows
        self.assertEqual(apps[1]["id_was"], SHARED)
        self.assertEqual(apps[1]["history"][-1]["event"], "id_repaired")
        self.assertEqual([a["id"] for a in self.written()], [a["id"] for a in apps])  # written at once
        again = track.load(self.root)
        self.assertEqual([a["id"] for a in again], [a["id"] for a in apps])
        self.assertEqual(sum(h.get("event") == "id_repaired" for h in again[1]["history"]), 1)

    def test_a_change_lands_on_the_row_it_was_meant_for(self):
        track.track(self.root, on("10-08"), SHARED + "-2026-09-03", "rejected")
        apps = {a.get("num"): a for a in track.load(self.root)}
        self.assertEqual((apps[110]["status"], apps[121]["status"]), ("rejected", "applied"))

    def test_find_never_guesses_between_two(self):
        two = [row("x", "2026-09-01", "u1", 1), row("x", "2026-09-02", "u2", 2)]
        with self.assertRaises(Refused):
            track.find(two, "x")
        for a in two:
            a["id"], a["key"] = a["num"], "greenhouse-acme-1"
        with self.assertRaises(Refused):
            track.find(two, "greenhouse-acme-1")

    def test_a_click_made_while_the_id_was_shared_isnt_guessed(self):
        track.load(self.root)
        click = {"id": "c-1", "at": "2026-10-05T10:00:00Z", "action": "replied", "app": SHARED, "num": 121,
                 "label": "TikTok, USDS UX and Support Program Manager"}
        out = choices.record(self.root, on("10-08"), [click])
        self.assertEqual(len(out["unknown"]), 1)
        self.assertIn("which one you meant", out["unknown"][0]["why"])
        self.assertTrue(all(a["status"] == "applied" for a in track.load(self.root) if a["company"] == "TikTok"))
        # A click on the repaired id itself is clear, and is recorded.
        click = {**click, "id": "c-2", "app": SHARED + "-2026-09-03", "num": 110}
        self.assertEqual(len(choices.record(self.root, on("10-08"), [click])["recorded"]), 1)


class MergeTest(TrackBase):
    def test_a_merge_never_folds_two_rows_into_one(self):
        # The store on its own, as a file from before ids were repaired: two rows with one id. One
        # command changes the first; meanwhile another adds a third. All three survive, as changed.
        f = store.Folder(self.root)
        rows = [row(SHARED, "2026-09-14", "u14", 121), row(SHARED, "2026-09-03", "u03", 110)]
        f.save_applications(rows)
        read = json.loads(json.dumps(rows))
        mine = json.loads(json.dumps(rows))
        mine[0]["status"] = "rejected"
        f.save_applications(rows + [row("app-acme-lead", "2026-10-01", "u01", 130)])  # the other command
        f.save_applications(mine, read=read, base=read)
        got = f.load_applications()
        self.assertEqual([(a["num"], a["status"]) for a in got], [(121, "rejected"), (110, "applied"), (130, "applied")])


class CloseWhileAnotherWritesTest(TrackBase):
    """Found in real use (2026-10-12), on engine 0.8.0: a scan's day-21 close saved while another
    command had written the file, so the save merged rows by id, and each pair sharing an id came out
    as two copies of one of them. Still 60 rows, but the 09-14 TikTok application and a LinkedIn row
    were gone, until restored by hand from a copy made before the scan."""

    def setUp(self):
        super().setUp()
        rows = [row(SHARED, "2026-09-14", "https://www.linkedin.com/jobs/view/4466722142/", 121),
                row(SHARED, "2026-09-03", "https://www.linkedin.com/jobs/view/4453350221/", 110)]
        with open(self.folder.applications_json, "w", encoding="utf-8") as f:
            json.dump({"applications": rows}, f)

    def test_both_applications_to_one_title_survive_the_close(self):
        apps = track.load(self.root)  # what close_due does: load, change, save
        track.apply(self.root, on("10-12"), company="Roblox", role="Senior Product Support Manager",
                    date="2026-10-08", channel="company_site")  # meanwhile, another command writes
        for a in apps:
            if a["company"] == "TikTok":
                a["status"] = "presumed_rejected"
        track.save(self.root, apps)
        tiktok = sorted((a["num"], a["applied_date"], a["urls"][0][-11:-1], a["status"])
                        for a in track.load(self.root) if a["company"] == "TikTok")
        self.assertEqual(tiktok, [(110, "2026-09-03", "4453350221", "presumed_rejected"),
                                  (121, "2026-09-14", "4466722142", "presumed_rejected")])
        self.assertEqual(len({a["id"] for a in track.load(self.root)}), len(track.load(self.root)))


class ApplyAgainTest(TrackBase):
    def test_another_link_for_the_same_title_is_asked_about(self):
        track.apply(self.root, on(3), company="Globex", role="Support Lead", url="https://globex.test/1",
                    channel="linkedin")
        with self.assertRaises(Refused) as e:
            track.apply(self.root, on(14), company="Globex", role="Support Lead", url="https://globex.test/2")
        self.assertIn("--again", str(e.exception))
        same = track.apply(self.root, on(14), company="Globex", role="Support Lead", url="https://globex.test/2", same=True)
        self.assertEqual((same["applied_date"], same["urls"]), ("2026-09-03", ["https://globex.test/1", "https://globex.test/2"]))

    def test_saying_it_again_without_a_date_or_link_is_the_same_one(self):
        track.apply(self.root, on(3), company="Globex", role="Support Lead")
        a = track.apply(self.root, on(14), company="Globex", role="Support Lead", channel="referral")
        self.assertFalse(a["created"])
        self.assertEqual((a["applied_date"], a["channel"]), ("2026-09-03", "referral"))

    def test_again_is_a_new_application_and_both_are_kept(self):
        track.apply(self.root, on(3), company="Globex", role="Support Lead", date="2026-09-03")
        new = track.apply(self.root, on(14), company="Globex", role="Support Lead", date="2026-09-14", again=True)
        self.assertTrue(new["created"])
        dates = sorted(a["applied_date"] for a in track.load(self.root) if a["company"] == "Globex")
        self.assertEqual(dates, ["2026-09-03", "2026-09-14"])
        with self.assertRaises(Refused):
            track.apply(self.root, on(14), key="greenhouse-acme-1", again=True)

    def test_the_command_line_says_how_to_answer(self):
        self.run_cli("apply", "--company", "Globex", "--role", "Support Lead", "--date", "2026-09-03",
                     "--channel", "linkedin", "--top-pick", "no")
        code, _, err = self.run_cli("apply", "--company", "Globex", "--role", "Support Lead", "--date", "2026-09-14",
                                    "--channel", "linkedin", "--top-pick", "no")
        self.assertEqual(code, 3)
        self.assertIn("new application", err)
        code, out, _ = self.run_cli("apply", "--company", "Globex", "--role", "Support Lead", "--date", "2026-09-14",
                                    "--channel", "linkedin", "--top-pick", "no", "--again")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["id"], "app-globex-support-lead-2026-09-14")
