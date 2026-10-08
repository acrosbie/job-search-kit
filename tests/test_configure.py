"""Changing settings and companies through the engine, on the made-up Denver support manager."""

import contextlib
import io
import os
import shutil
import tempfile
import unittest

from jobkit import cli, configure, settings
from tests.test_screen import EXAMPLE


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class ConfigureTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "profile"))
        self.settings_path = os.path.join(self.root, "profile", "settings.toml")
        with open(self.settings_path, "w", encoding="utf-8") as f:
            f.write("# Written by setup.\n# Claude changes this file.\n" + EXAMPLE)
        with open(os.path.join(self.root, "profile", "companies.toml"), "w", encoding="utf-8") as f:
            f.write('# Watched companies.\n\n[[company]]\nname = "Acme"\nslug = "acme"\nats = "greenhouse"\ntoken = "acme"\n')

    def test_set_a_pattern_with_backslashes(self):
        old, new = configure.set_value(self.root, "titles.level", r"\bmanager\b|\bhead\b")
        self.assertEqual(old, r"\bmanager\b|\bdirector\b")
        s = settings.load(self.root)
        self.assertEqual(s.level.pattern, r"\bmanager\b|\bhead\b")
        self.assertEqual(s.hybrid_ok.pattern, "denver|aurora|lakewood")  # everything else intact
        self.assertTrue(read(self.settings_path).startswith("# Written by setup.\n# Claude changes this file.\n"))

    def test_the_previous_settings_are_kept(self):
        before = read(self.settings_path)
        configure.set_value(self.root, "titles.level", r"\bmanager\b|\bhead\b")
        self.assertEqual(read(os.path.join(self.root, "profile", "settings.backup.toml")), before)

    def test_refusals_leave_the_file_alone(self):
        before = read(self.settings_path)
        for key, value in (("titles.function", "support(("), ("pay.reject_if_top_below", "lots"),
                           ("titles.colour", "x"), ("nonsense", "x"), ("labels.reason_pay", "under {line}K")):
            with self.assertRaises(configure.Refused, msg=key):
                configure.set_value(self.root, key, value)
        self.assertEqual(read(self.settings_path), before)

    def test_numbers_labels_and_new_keys(self):
        configure.set_value(self.root, "pay.reject_if_top_below", "85000")
        configure.set_value(self.root, "labels.reason_pay", "Pays up to ${top_k}K, under your ${line_k}K")
        configure.set_value(self.root, "titles.field_words", r"support|customer care")
        configure.set_value(self.root, "triage.cooldown_days", "45")
        s = settings.load(self.root)
        self.assertEqual((s.pay_top_below, s.cooldown_days), (85000, 45))
        self.assertEqual(s.label("reason_pay", top_k=80, low_k=60, line_k=85), "Pays up to $80K, under your $85K")
        self.assertEqual(s.raw["titles"]["field_words"], r"support|customer care")

    def test_phrase_rule_add_and_replace(self):
        configure.phrase_reject(self.root, "travel", r"\btravel\b|on the road", 1, "Lots of travel: {hits}")
        configure.phrase_reject(self.root, "quota", "quota|book of business", 3)
        rules = {r.name: r for r in settings.load(self.root).phrase_rejects}
        self.assertEqual(set(rules), {"quota", "travel"})
        self.assertEqual(rules["quota"].min_distinct, 3)
        self.assertEqual(rules["quota"].same_as, {})  # replaced whole, as given
        with self.assertRaises(configure.Refused):
            configure.phrase_reject(self.root, "bad", "quota", 1, "uses {nothing}")

    def test_companies(self):
        configure.add_company(self.root, {"name": "Globex", "slug": "globex", "ats": "lever", "token": "globex"})
        configure.add_company(self.root, {"name": "Initech", "slug": "initech", "ats": "workday",
                                          "host": "initech.wd5.myworkdayjobs.com", "tenant": "initech", "site": "Careers"})
        self.assertEqual([c["slug"] for c in configure.list_companies(self.root)], ["acme", "globex", "initech"])
        for bad in ({"name": "X", "slug": "x", "ats": "lever"},                       # no token
                    {"name": "X", "slug": "X Co", "ats": "lever", "token": "x"},       # bad slug
                    {"name": "Acme", "slug": "acme", "ats": "lever", "token": "a"},    # already there
                    {"name": "X", "slug": "x", "ats": "icims", "token": "x"}):         # no reader
            with self.assertRaises(configure.Refused):
                configure.add_company(self.root, bad)
        self.assertEqual(configure.drop_company(self.root, "globex"), 2)
        with self.assertRaises(configure.Refused):
            configure.drop_company(self.root, "globex")
        self.assertTrue(read(os.path.join(self.root, "profile", "companies.toml")).startswith("# Watched companies."))

    def test_cli_refusal_is_exit_3(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["settings", "set", "--folder", self.root, "titles.function", "support(("])
        self.assertEqual(code, 3)
        self.assertIn("doesn't work", err.getvalue())


if __name__ == "__main__":
    unittest.main()
