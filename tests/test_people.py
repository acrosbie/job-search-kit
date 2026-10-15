"""People in the search (decision 4, accepted 2026-10-14): the LinkedIn connections export, who the
user knows at each company, messages counted against 2 a day, follow-ups due to people, the referral
window on a job on hold, a recruiter's sending address, and who "find a person" looks for.

Evidence: of 60 applications, 1 had a contact; the one referral (BCM One) moved fastest."""

import os

from jobkit import contacts, page, queue, settings, start, verdicts
from jobkit.errors import Refused
from tests.test_track import TrackBase, on

CSV = """Notes:
"When exporting your connection data, you may notice that some of the email addresses are missing."

First Name,Last Name,URL,Email Address,Company,Position,Connected On
Dana,Example,https://www.linkedin.com/in/dana-example,dana@acme.example,"Acme, Inc.",Director of Customer Support,04 Mar 2021
Lee,Sample,https://www.linkedin.com/in/lee-sample,,Globex,Support Lead,12 Jan 2023
,,,,,,
"""


def dos(out):
    return [n["do"] for n in out["next"]]


class PeopleTest(TrackBase):
    def import_csv(self):
        path = os.path.join(self.root, "Connections.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(CSV)
        return contacts.import_connections(self.root, on(24), path)

    def test_the_connections_file_never_keeps_an_email(self):
        out = self.import_csv()
        self.assertEqual((out["added"], out["skipped"]), (2, 1))
        dana = contacts.find(contacts.load(self.root), "Dana Example")
        self.assertEqual((dana["company"], dana["title"], dana["email"], dana["source"]),
                         ("Acme, Inc.", "Director of Customer Support", "", "connections"))
        self.assertEqual(dana["how_known"], "LinkedIn connection since 04 Mar 2021")
        again = self.import_csv()
        self.assertEqual((again["added"], again["already_kept"]), (0, 2))
        with open(os.path.join(self.root, "data", "contacts.json"), encoding="utf-8") as f:
            self.assertNotIn("dana@acme.example", f.read())

    def test_a_file_that_isnt_linkedins_is_refused(self):
        path = os.path.join(self.root, "other.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Name,Company\nDana,Acme\n")
        with self.assertRaises(Refused):
            contacts.import_connections(self.root, on(24), path)

    def test_who_you_know_on_the_queue_and_the_page(self):
        self.import_csv()
        q = queue.queue(self.root, on(24))
        acme = next(p for p in q["postings"] if p["company"] == "Acme")
        self.assertEqual([k["name"] for k in acme["known_at_company"]], ["Dana Example"])  # "Acme, Inc." is Acme
        verdicts.mark(self.root, "greenhouse-acme-1", "worth_applying", "claude", note="fits", clock=on(24))
        job = next(j for j in page.build(self.root, on(24))["waiting"] if j["key"] == "greenhouse-acme-1")
        self.assertEqual(job["known"]["count"], 1)

    def test_messages_are_counted_and_followed_up(self):
        contacts.add(self.root, on(20), "Troy Hess", company="BCM One", kind="referrer")
        contacts.touch(self.root, on(18), "Troy Hess", note="referral ask")  # six days ago
        o = contacts.outreach(self.root, on(24))
        self.assertEqual((o["per_day"], o["sent_today"], [p["name"] for p in o["follow_ups_due"]]), (2, 0, ["Troy Hess"]))
        self.assertIn("offer_people_follow_ups", dos(start.start(self.root, on(24))))
        contacts.touch(self.root, on(24), "Troy Hess", direction="in", note="happy to refer")
        self.assertEqual(contacts.outreach(self.root, on(24))["follow_ups_due"], [])
        self.assertEqual(page.build(self.root, on(24))["outreach"]["sent_today"], 0)

    def test_the_count_is_on_from_day_one_and_can_be_stopped(self):
        self.assertEqual(settings.load(self.root).outreach, {"per_day": 2, "follow_up_days": 5})
        from jobkit import configure
        configure.set_value(self.root, "outreach.per_day", "0")
        self.assertIsNone(page.build(self.root, on(24))["outreach"])

    def test_a_job_on_hold_where_they_know_someone_offers_a_referral_ask_once(self):
        self.import_csv()
        verdicts.mark(self.root, "greenhouse-acme-1", "on_hold", "claude", clock=on(24))
        step = next(n for n in start.start(self.root, on(24))["next"] if n["do"] == "offer_referral_ask")
        self.assertEqual([k["name"] for k in step["jobs"][0]["known"]], ["Dana Example"])
        self.assertNotIn("offer_referral_ask", dos(start.start(self.root, on(24))))

    def test_where_a_recruiter_wrote_from(self):
        self.assertTrue(contacts.check_sender("hr.acme@gmail.com", "Acme")["flags"])
        self.assertEqual(contacts.check_sender("dana@acme.com", "Acme")["flags"], [])
        self.assertTrue(contacts.check_sender("dana@acme-careers.net", "Acme")["flags"])
        self.assertTrue(contacts.check_sender("dana@globex.com", "Acme")["flags"])
        self.assertEqual(contacts.check_sender("troy@bcmone.com", "BCM One")["flags"], [])

    def test_same_company(self):
        self.assertTrue(contacts.same_company("Zoom", "Zoom Video Communications"))
        self.assertFalse(contacts.same_company("Zoom", "ZoomInfo"))
        self.assertTrue(contacts.same_company("BCM One, Inc.", "bcm one"))


class FindPersonTest(TrackBase):
    def test_the_field_packs_leaders_by_their_real_titles(self):
        # Decision 4, question 3: who to look for depends on the job's field, generalized by field pack.
        from jobkit import configure
        s = settings.load(self.root)
        self.assertEqual(page.contact_search("Acme", "Customer Support Systems Administrator", s),
                         'Acme "Customer Support Systems Administrator" (director OR head OR VP)')
        configure.set_value(self.root, "page.contact_search", '"Director of Customer Support" OR "Head of Support"')
        s = settings.load(self.root)
        self.assertEqual(page.contact_search("Acme", "Customer Support Systems Administrator", s),
                         'Acme ("Director of Customer Support" OR "Head of Support")')

    def test_the_support_pack_names_its_leaders(self):
        from jobkit.toml import load_file
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pack = load_file(os.path.join(here, "plugins", "job-search", "engine", "starter", "fields", "support-cx.toml"))
        self.assertIn('"Director of Customer Support"', pack["page"]["contact_search"])
