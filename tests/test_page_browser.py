"""The jobs page in a real browser: its script runs, and its controls do what they say. The page's
JavaScript is checked nowhere else. Runs where Chrome, Chromium or Edge is installed (CI has them), and
skips elsewhere; JOBKIT_BROWSER names one to use."""

import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from jobkit import page, track, verdicts
from tests.test_scan import ScanBase
from tests.test_track import on

CANDIDATES = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def browser():
    if os.environ.get("JOBKIT_BROWSER"):
        return os.environ["JOBKIT_BROWSER"]
    for c in CANDIDATES:
        found = shutil.which(c) or (c if os.path.isabs(c) and os.path.exists(c) else None)
        if found:
            return found
    return None


# Drives the page inside a frame, then writes what it saw as JSON for the test to read.
HARNESS = """<!doctype html><html><body><pre id="out">running</pre>
<iframe id="f" src="%s" style="width:1200px;height:900px"></iframe>
<script>
var out = {};
document.getElementById("f").addEventListener("load", function () {
  try {
    var w = this.contentWindow, d = w.document;
    function n(s) { return d.querySelectorAll(s).length; }
    function shown(s) { return Array.prototype.filter.call(d.querySelectorAll(s), function (e) { return !e.hidden; }).length; }
    out.today = n("#s-today");
    out.headline = (d.querySelector("#s-look .headline") || {}).textContent || "";
    out.behind = n("details.behind");
    out.people = n(".people li");
    out.linkedin = (d.querySelector(".people a.btn") || {}).href || "";
    out.open_rows = n("li.app");
    d.querySelector('[data-apps-view="all"]').click();
    out.all_rows = n("li.app");
    var f = d.getElementById("filter-apps");
    f.value = "globex"; f.dispatchEvent(new w.Event("input", { bubbles: true }));
    out.filtered = shown("li.app");
    var sel = d.getElementById("sort-apps");
    sel.value = "company"; sel.dispatchEvent(new w.Event("change", { bubbles: true }));
    out.sorted_first = d.querySelector("li.app .app-name b").textContent;
    var add = d.querySelector('.people [data-open="contact"]');
    if (add) add.click();
    out.contact_form = n(".people .panel #f-contact");
    out.time_not_set = d.body.textContent.indexOf("time not set") >= 0;
  } catch (e) { out.error = String(e); }
  document.getElementById("out").textContent = JSON.stringify(out);
});
</script></body></html>"""


@unittest.skipUnless(browser(), "no Chrome, Chromium or Edge to run the page in")
class BrowserTest(ScanBase):
    def setUp(self):
        super().setUp()
        self.scan()
        self.folder.save_applications([])
        track.apply(self.root, on(1), key="greenhouse-acme-4", date="2026-09-01", channel="company_site", top_pick=True)
        track.apply(self.root, on(2), company="Globex", role="Support Lead (Remote, USA)", date="2026-09-02",
                    channel="linkedin", top_pick=False)
        track.track(self.root, on(5), "app-globex-support-lead-remote-usa", "rejected", date="2026-09-05")
        track.apply(self.root, on(2), company="Initech", role="Head of Support", date="2026-09-02", channel="other",
                    top_pick=True)  # a top pick with nobody to follow up with, by day 8
        from jobkit import interviews
        interviews.schedule(self.root, on(10), "greenhouse-acme-4", "2026-09-14", status="screen")
        verdicts.mark(self.root, "greenhouse-acme-1", "worth_applying", "claude", note="Tailor: lead with the team",
                      clock=on(10), summary={"headline": "A close match, near home.",
                                             "fits": ["You'd lead the Denver team."], "tailor": ["Lead with the team."]})
        page.refresh(self.root, on(10))

    def run_page(self):
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work, True)
        target = pathlib.Path(self.root, "My jobs.html").resolve().as_uri()
        harness = pathlib.Path(work, "harness.html")
        harness.write_text(HARNESS % target, encoding="utf-8")
        cmd = [browser(), "--headless=new", "--disable-gpu", f"--user-data-dir={os.path.join(work, 'profile')}",
               "--allow-file-access-from-files", "--virtual-time-budget=5000", "--dump-dom", harness.resolve().as_uri()]
        if sys.platform.startswith("linux"):
            cmd.insert(1, "--no-sandbox")
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)
        m = re.search(r'<pre id="out">(.*?)</pre>', done.stdout, re.S)
        self.assertIsNotNone(m, done.stderr[-2000:])
        return json.loads(html.unescape(m.group(1)))

    def test_the_page_runs_and_its_controls_work(self):
        got = self.run_page()
        self.assertNotIn("error", got)
        self.assertEqual(got["today"], 1)
        self.assertEqual(got["headline"], "A close match, near home.")
        self.assertGreaterEqual(got["behind"], 1)
        self.assertTrue(got["time_not_set"])
        self.assertEqual((got["open_rows"], got["all_rows"], got["filtered"]), (2, 3, 1))  # Globex turned it down
        self.assertEqual(got["sorted_first"], "Acme")
        self.assertEqual(got["people"], 1)
        self.assertIn("linkedin.com/search/results/people/?keywords=Initech", got["linkedin"])
        self.assertEqual(got["contact_form"], 1)


if __name__ == "__main__":
    unittest.main()
