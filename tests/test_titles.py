"""Title calibration on a made-up list of titles, for the made-up Denver support manager."""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

from jobkit import cli, titles
from tests.test_screen import EXAMPLE

TITLES = [
    ("acme", "Customer Support Manager", "Denver, CO"),        # kept
    ("acme", "Customer Support Manager", "Remote"),            # kept (same title again)
    ("acme", "Support Operations Director", "Aurora"),         # kept
    ("acme", "Customer Support Specialist", "Denver"),         # near: function, no level
    ("acme", "Sales Customer Support Manager", "Denver"),      # near: excluded
    ("acme", "Customer Care Lead", "Denver"),                  # near: field word only
    ("acme", "Customer Support Manager", "London"),            # place fails: neither
    ("acme", "Software Engineer", "Denver"),                   # neither
]


class TitlesTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, "profile"))
        os.makedirs(os.path.join(self.root, "data"))
        with open(os.path.join(self.root, "profile", "settings.toml"), "w", encoding="utf-8") as f:
            f.write(EXAMPLE.replace('[titles]\n', '[titles]\nfield_words = "support|customer care"\n', 1))
        with open(os.path.join(self.root, "data", "titles-latest.tsv"), "w", encoding="utf-8") as f:
            f.write("source\ttitle\tlocation\n" + "".join(f"{b}\t{t}\t{l}\n" for b, t, l in TITLES))

    def test_summary(self):
        out = titles.summary(self.root, sample=10)
        self.assertEqual((out["titles_read"], out["kept"], out["kept_distinct"], out["near_misses"]), (8, 3, 2, 3))
        self.assertEqual({x["title"] for x in out["near_sample"]},
                         {"Customer Support Specialist", "Sales Customer Support Manager", "Customer Care Lead"})
        self.assertEqual(next(x for x in out["kept_sample"] if x["title"] == "Customer Support Manager")["count"], 2)

    def test_try_a_wider_level(self):
        out = titles.try_patterns(self.root, level=r"\bmanager\b|\bdirector\b|\bspecialist\b|\blead\b")
        self.assertEqual((out["kept_now"], out["kept_with_change"], out["gained"], out["lost"]), (3, 4, 1, 0))
        self.assertEqual([x["title"] for x in out["gained_sample"]], ["Customer Support Specialist"])
        out = titles.try_patterns(self.root, exclude=r"\bsales\b|associate|\bdirector\b")
        self.assertEqual((out["lost"], out["lost_sample"][0]["title"]), (1, "Support Operations Director"))

    def test_cli(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(["titles", "--folder", self.root, "--sample", "1"]), 0)
        self.assertEqual(len(json.loads(out.getvalue())["kept_sample"]), 1)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["try-titles", "--folder", self.root, "--function", "support(("]), 3)


if __name__ == "__main__":
    unittest.main()
