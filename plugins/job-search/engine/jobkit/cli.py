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
from . import configure, titles, track, verdicts
from . import init as starter
from . import queue as triage_queue
from .clock import Clock
from .discover import discover
from .errors import NotFound, Refused
from .text import salary_from


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


def cmd_queue(a):
    _out(triage_queue.queue(a.folder, _clock(a.folder)))
    return 0


def cmd_show(a):
    text = store.Folder(a.folder).read_description(a.key)
    if text is None:
        print(f"no saved posting for {a.key}", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


def cmd_mark(a):
    if a.status == "applied":
        if a.by != "user":
            raise Refused("only the user marks a posting applied")
        _out(track.apply(a.folder, _clock(a.folder), key=a.key, note=a.note))
        return 0
    _out(verdicts.mark(a.folder, a.key, a.status, a.by, note=a.note, force=a.force, clock=_clock(a.folder)))
    return 0


def _yes_no(v):
    return None if v is None else v == "yes"


def cmd_apply(a):
    _out(track.apply(a.folder, _clock(a.folder), key=a.key or "", company=a.company or "", role=a.role or "",
                     url=a.url or "", date=a.date or "", estimated=a.estimated, channel=a.channel or "",
                     top_pick=_yes_no(a.top_pick), contact=a.contact or "", note=a.note or "", choice=a.choice or ""))
    return 0


def cmd_track(a):
    _out(track.track(a.folder, _clock(a.folder), a.id, status=a.status or "", date=a.date or "", note=a.note or "",
                     contact=a.contact, top_pick=_yes_no(a.top_pick), channel=a.channel, choice=a.choice or ""))
    return 0


def cmd_applications(a):
    _out({"applications": track.listing(a.folder, _clock(a.folder))})
    return 0


def cmd_due(a):
    _out(track.due(a.folder, _clock(a.folder)))
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


def cmd_settings(a):
    if a.action == "show":
        _out(configure.show(a.folder))
    elif a.action == "set":
        old, new = configure.set_value(a.folder, a.key, a.value)
        _out({"setting": a.key, "was": old, "now": new})
    else:
        same_as = json.loads(a.same_as) if a.same_as else None
        _out(configure.phrase_reject(a.folder, a.name, a.phrases, a.min_distinct, a.reason, same_as))
    return 0


def cmd_companies(a):
    if a.action == "list":
        _out(configure.list_companies(a.folder))
    elif a.action == "add":
        entry = {"name": a.name, "slug": a.slug, "ats": a.ats, "token": a.token, "host": a.host, "tenant": a.tenant,
                 "site": a.site, "queries": a.query or [], "careers_url": a.careers_url}
        _out(configure.add_company(a.folder, entry))
    else:
        _out({"dropped": a.slug, "companies_left": configure.drop_company(a.folder, a.slug)})
    return 0


def cmd_titles(a):
    _out(titles.summary(a.folder, sample=a.sample, seed=a.seed))
    return 0


def cmd_try_titles(a):
    try:
        _out(titles.try_patterns(a.folder, function=a.function, level=a.level, exclude=a.exclude,
                                 field_words=a.field_words, sample=a.sample, seed=a.seed))
    except re.error as e:
        print(f"that pattern doesn't work: {e}", file=sys.stderr)
        return 3
    return 0


def cmd_init(a):
    try:
        _out(starter.init(a.folder, field=a.field, places=a.places, timezone=a.timezone))
    except starter.AlreadySetUp as e:
        print(str(e), file=sys.stderr)
        return 3
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
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

    s = sub.add_parser("queue", help="the postings waiting for triage, with cooldown facts")
    s.add_argument("--folder", required=True)
    s.set_defaults(func=cmd_queue)

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

    s = sub.add_parser("apply", help="record that the user applied (the user only)")
    s.add_argument("--folder", required=True)
    s.add_argument("key", nargs="?", help="the posting's key; or give --company and --role")
    s.add_argument("--company")
    s.add_argument("--role")
    s.add_argument("--url")
    s.add_argument("--date", help="YYYY-MM-DD, the day they applied (default today)")
    s.add_argument("--estimated", action="store_true", help="the date is only roughly known")
    s.add_argument("--channel", choices=track.CHANNELS)
    s.add_argument("--top-pick", choices=("yes", "no"))
    s.add_argument("--contact")
    s.add_argument("--note")
    s.add_argument("--choice", help="the id of the jobs-page click this came from")
    s.set_defaults(func=cmd_apply)

    s = sub.add_parser("track", help="record what happened to an application")
    s.add_argument("--folder", required=True)
    s.add_argument("id", help="the application's id or its posting's key")
    s.add_argument("status", nargs="?", choices=tuple(x for x in track.STATUSES if x != "presumed_rejected") + ("followed_up",))
    s.add_argument("--date", help="YYYY-MM-DD, the day it happened (default today)")
    s.add_argument("--note")
    s.add_argument("--contact", help="a person at the company the user named")
    s.add_argument("--top-pick", choices=("yes", "no"))
    s.add_argument("--channel", choices=track.CHANNELS)
    s.add_argument("--choice", help="the id of the jobs-page click this came from")
    s.set_defaults(func=cmd_track)

    s = sub.add_parser("applications", help="every application, with its day count and what's due")
    s.add_argument("--folder", required=True)
    s.set_defaults(func=cmd_applications)

    s = sub.add_parser("due", help="close applications at day 21, then list the follow-ups due")
    s.add_argument("--folder", required=True)
    s.set_defaults(func=cmd_due)

    s = sub.add_parser("add", help="register a posting saved by hand")
    s.add_argument("--folder", required=True)
    s.add_argument("file")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("settings", help="show or change one setting, checked before it's saved")
    acts = s.add_subparsers(dest="action", required=True)
    x = acts.add_parser("show")
    x.add_argument("--folder", required=True)
    x = acts.add_parser("set")
    x.add_argument("--folder", required=True)
    x.add_argument("key", help="section.name, for example titles.function")
    x.add_argument("value")
    x = acts.add_parser("phrase-reject")
    x.add_argument("--folder", required=True)
    x.add_argument("name")
    x.add_argument("--phrases", required=True)
    x.add_argument("--min-distinct", type=int, default=2)
    x.add_argument("--reason", default="")
    x.add_argument("--same-as", help='JSON object, for example {"net revenue retention": "nrr"}')
    s.set_defaults(func=cmd_settings)

    s = sub.add_parser("companies", help="list, add or drop a watched company")
    acts = s.add_subparsers(dest="action", required=True)
    x = acts.add_parser("list")
    x.add_argument("--folder", required=True)
    x = acts.add_parser("add")
    x.add_argument("--folder", required=True)
    x.add_argument("--name", required=True)
    x.add_argument("--slug", required=True)
    x.add_argument("--ats", required=True)
    for opt in ("--token", "--host", "--tenant", "--site", "--careers-url"):
        x.add_argument(opt)
    x.add_argument("--query", action="append", help="a search phrase, for an aggregator; repeat for several")
    x = acts.add_parser("drop")
    x.add_argument("--folder", required=True)
    x.add_argument("slug")
    s.set_defaults(func=cmd_companies)

    s = sub.add_parser("init", help="start a new user's folder from the starter boards and a field pack")
    s.add_argument("--folder", required=True)
    s.add_argument("--field", default="custom", help="a field pack (see starter/fields), or custom")
    s.add_argument("--places", default="us")
    s.add_argument("--timezone", default="", help="for example America/Denver")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("titles", help="what the title filter keeps and nearly keeps, from the last scan's titles")
    s.add_argument("--folder", required=True)
    s.add_argument("--sample", type=int, default=10)
    s.add_argument("--seed", type=int, default=1)
    s.set_defaults(func=cmd_titles)

    s = sub.add_parser("try-titles", help="what a change to the title patterns would gain and lose, without fetching")
    s.add_argument("--folder", required=True)
    for opt in ("--function", "--level", "--exclude", "--field-words"):
        s.add_argument(opt)
    s.add_argument("--sample", type=int, default=10)
    s.add_argument("--seed", type=int, default=1)
    s.set_defaults(func=cmd_try_titles)

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
    except NotFound as e:
        print(str(e), file=sys.stderr)
        return 1
    except Refused as e:
        print(str(e), file=sys.stderr)
        return 3
