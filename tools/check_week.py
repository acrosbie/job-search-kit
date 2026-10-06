#!/usr/bin/env python3
"""Check a Job Search folder after phase 4's scripted week in Cowork: every application, the pasted
posting, the page's clicks and the page files against an expectations file.

    python tools/check_week.py "<folder>" expected.json

expected.json:
    {
      "pasted": {"company": "Initech", "text_from": "link"},       # a manual posting the user pasted
      "applications": [                                            # one per application, by company
        {"company": "Initech", "status": "applied", "top_pick": true, "channel": "linkedin", "route": "find_person"},
        {"company": "Ramp", "status": "screen", "never": ["presumed_rejected"]},
        {"company": "HappyCo", "status": "presumed_rejected"}
      ],
      "page_clicks": 2                                             # decisions recorded from the jobs page
    }

Prints one line per check and exits 1 if any fails. Reads only; writes nothing.
"""

import datetime as dt
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "plugins", "job-search", "engine"))
sys.dont_write_bytecode = True

from jobkit import settings, store, track  # noqa: E402


def check(folder, want, today=None):
    results = []

    def ok(passed, what):
        results.append((bool(passed), what))

    f = store.Folder(folder)
    postings = f.load_postings()["postings"]
    apps = track.load(folder)
    s = settings.load(folder)
    today = today or dt.date.today()

    pasted = want.get("pasted")
    if pasted:
        found = [(k, v) for k, v in postings.items() if v.get("source") == "manual"
                 and v.get("company", "").casefold() == pasted["company"].casefold()]
        ok(len(found) == 1, f"one pasted posting from {pasted['company']} (found {len(found)})")
        if found:
            k, v = found[0]
            ok(k.startswith("manual-"), f"its key is a manual key ({k})")
            ok(v.get("text_from") == pasted.get("text_from", v.get("text_from")), f"read from: {v.get('text_from')}")
            ok(len(f.read_description(k) or "") > 300, "its saved description is the full posting, not a stub")

    for w in want.get("applications", []):
        mine = [a for a in apps if a.get("company", "").casefold() == w["company"].casefold()]
        ok(len(mine) == 1, f"{w['company']}: one application (found {len(mine)})")
        if not mine:
            continue
        a = mine[0]
        statuses = [h.get("status") for h in a["history"] if h.get("status")]
        ok(a["status"] == w["status"], f"{w['company']}: status {a['status']}, expected {w['status']}")
        for field in ("top_pick", "channel"):
            if field in w:
                ok(a.get(field) == w[field], f"{w['company']}: {field} {a.get(field)!r}, expected {w[field]!r}")
        if "route" in w:
            st = track.state(a, today, s)
            ok(st["route"] == w["route"], f"{w['company']}: follow-up route {st['route'] or 'none'}, expected {w['route']}")
        for never in w.get("never", []):
            ok(never not in statuses, f"{w['company']}: never {never} (history: {', '.join(statuses)})")
        if a.get("key"):
            ok(postings.get(a["key"], {}).get("status") == "applied", f"{w['company']}: its posting is marked applied")
        ok(all(h.get("by") in ("user", "engine", "import") for h in a["history"]), f"{w['company']}: every change by the user or the day-21 close")
        closes = [h for h in a["history"] if h.get("status") == "presumed_rejected"]
        ok(all(h.get("by") == "engine" for h in closes), f"{w['company']}: only the engine presumed")

    decisions = f.read_decisions()
    clicks = [d for d in decisions if d.get("choice")]
    if "page_clicks" in want:
        ok(len(clicks) == want["page_clicks"], f"{len(clicks)} decisions from page clicks, expected {want['page_clicks']}")
        ok(len({d['choice'] for d in clicks}) == len(clicks), "no click recorded twice")
        ok(all(d.get("by") == "user" for d in clicks), "page clicks recorded as the user's")
    applied_by_claude = [d for d in decisions if d.get("verdict") == "applied" and d.get("by") != "user"]
    ok(not applied_by_claude, "nothing marked applied except by the user")

    try:
        with open(f.page_json, encoding="utf-8") as fh:
            data = json.load(fh)
        with open(f.page_html, encoding="utf-8") as fh:
            html = fh.read()
        embedded = json.loads(re.search(r'id="jobs-data">(.*?)</script>', html, re.S).group(1))
        ok(embedded == data, "My jobs.html carries the same data as page.json")
        page_status = {x["id"]: x["status"] for x in data["applications"]}
        ok(page_status == {a["id"]: a["status"] for a in apps}, "the page shows every application as recorded")
        ok(s.page.get("url"), f"the jobs page link is saved ({s.page.get('url') or 'none'})")
        ok(s.page.get("route") in ("storage", "republish"), f"the page is kept current by: {s.page.get('route') or 'nothing yet'}")
    except (OSError, ValueError, AttributeError) as e:
        ok(False, f"the page files: {type(e).__name__}: {e}")
    return results


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        want = json.load(fh)
    results = check(argv[0], want)
    for passed, what in results:
        print(("PASS  " if passed else "FAIL  ") + what)
    failed = sum(1 for p, _ in results if not p)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
