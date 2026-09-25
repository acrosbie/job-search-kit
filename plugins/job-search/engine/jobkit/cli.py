"""Command line for the engine. Claude runs these; the user never does.

Results are printed as JSON so Claude can read them exactly. Exit codes: 0 done, 1 something is
wrong with the folder or its files, 2 a mistake in the command, 3 refused on purpose (the message
says why).
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

from . import __version__, net, scan, settings, store
from .clock import Clock
from .discover import discover
from .text import salary_from

# A verdict that contradicts an earlier one, for spotting when the user overturns Claude or a rule.
OPPOSED = {"worth_applying": {"not_a_fit", "skipped"}, "not_a_fit": {"worth_applying", "applied"}}


def _out(obj):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def _clock(folder):
    try:
        return Clock(settings.load(folder).timezone)
    except Exception:
        return Clock()


def cmd_scan(a):
    if a.record:
        net.use(net.Record(a.record))
    elif a.replay:
        net.use(net.Replay(a.replay))
    clock = None
    if a.as_of:  # replays compare dates, so they pin the clock
        clock = Clock(settings.load(a.folder).timezone, fixed=dt.datetime.fromisoformat(a.as_of))
    _out(scan.run(a.folder, only=a.only, clock=clock))
    return 0


def cmd_show(a):
    text = store.Folder(a.folder).read_description(a.key)
    if text is None:
        print(f"no saved posting for {a.key}", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


def cmd_mark(a):
    folder = store.Folder(a.folder)
    state = folder.load_postings()
    entry = state["postings"].get(a.key)
    if not entry:
        print(f"unknown key {a.key}", file=sys.stderr)
        return 1
    if a.status == "applied" and a.by != "user":
        print("only the user marks a posting applied", file=sys.stderr)
        return 3
    earlier = [d for d in folder.read_decisions() if d.get("key") == a.key]
    if a.by != "user" and any(d.get("by") == "user" for d in earlier) and not a.force:
        last = [d for d in earlier if d.get("by") == "user"][-1]
        print(f"the user already decided this one ({last.get('verdict')} on {last.get('date')}); their decision stands",
              file=sys.stderr)
        return 3
    clk = _clock(a.folder)
    reversal = ""
    if a.by == "user" and earlier and a.status in OPPOSED.get(earlier[-1].get("verdict"), set()):
        reversal = earlier[-1].get("verdict")
    entry["status"] = a.status
    entry["triaged"] = clk.today()
    if a.note:
        entry["note"] = a.note
    folder.save_postings(state)
    row = {"at": clk.stamp(), "date": clk.today(), "key": a.key, "company": entry["company"], "title": entry["title"],
           "verdict": a.status, "reason": a.note, "by": a.by}
    if reversal:
        row["reverses"] = reversal
    folder.log_decision(row)
    _out(row)
    return 0


def cmd_add(a):
    """Register a posting saved by hand (a pasted link, LinkedIn) as data/postings/manual-<company>-<short>.md,
    with the same header a scan writes: '# Title', then '- Company:', '- Location:', '- URL:', '- Posted:'."""
    folder = store.Folder(a.folder)
    path = os.path.abspath(a.file)
    if os.path.dirname(path) != os.path.abspath(folder.descriptions):
        print(f"the file must be in {folder.descriptions}", file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fields = dict(re.findall(r"^- (\w+): (.*)$", text, re.M))
    title = re.search(r"^# (.+)$", text, re.M)
    if not title or "Company" not in fields:
        print("header missing: need '# Title' and '- Company:' lines", file=sys.stderr)
        return 1
    key = os.path.splitext(os.path.basename(path))[0]
    clk = _clock(a.folder)
    state = folder.load_postings()
    state["postings"][key] = {
        "salary": salary_from(text),
        "status": "new",
        "first_seen": clk.today(),
        "last_seen": clk.today(),
        "company": fields.get("Company", ""),
        "title": title.group(1).strip(),
        "location": fields.get("Location", "").replace("(not stated)", ""),
        "url": fields.get("URL", ""),
        "posted": fields.get("Posted", "").replace("(unknown)", ""),
        "source": "manual",
        "flag": "",
        "flags": [],
        "file": os.path.basename(path),
    }
    folder.save_postings(state)
    _out({"key": key, **state["postings"][key]})
    return 0


def cmd_discover(a):
    _out({"slug": a.slug, **discover(a.slug, page=a.page)})
    return 0


def cmd_version(a):
    print(f"job-search-kit engine {__version__}, Python {sys.version.split()[0]}")
    return 0


def parser():
    p = argparse.ArgumentParser(prog="run.py", description=f"job-search-kit engine {__version__}")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("scan", help="read every watched board and save what's new")
    s.add_argument("--folder", required=True)
    s.add_argument("--only", help="one company slug")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--record", metavar="DIR", help="also save every board answer to this cassette folder")
    g.add_argument("--replay", metavar="DIR", help="read board answers from this cassette folder, not the network")
    s.add_argument("--as-of", metavar="TIME", help="pretend it is this time (ISO, with offset); for replays")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("show", help="print a saved posting")
    s.add_argument("--folder", required=True)
    s.add_argument("key")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("mark", help="record a verdict on a posting")
    s.add_argument("--folder", required=True)
    s.add_argument("key")
    s.add_argument("status", choices=store.STATUSES)
    s.add_argument("--note", default="")
    s.add_argument("--by", choices=("claude", "user"), required=True)
    s.add_argument("--force", action="store_true", help="overwrite the user's own decision (only when they ask)")
    s.set_defaults(func=cmd_mark)

    s = sub.add_parser("add", help="register a posting saved by hand")
    s.add_argument("--folder", required=True)
    s.add_argument("file")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("discover", help="which public job board a company uses")
    s.add_argument("slug")
    s.add_argument("--page", help="the company's careers page, to look for an embedded board")
    s.set_defaults(func=cmd_discover)

    s = sub.add_parser("version")
    s.set_defaults(func=cmd_version)
    return p


def main(argv):
    p = parser()
    a = p.parse_args(argv)
    if not getattr(a, "func", None):
        p.print_help()
        return 0
    try:
        return a.func(a)
    except FileNotFoundError as e:
        print(f"missing file: {e.filename}", file=sys.stderr)
        return 1
