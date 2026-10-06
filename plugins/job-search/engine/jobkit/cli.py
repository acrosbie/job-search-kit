"""Command line for the engine. Claude runs these; the user never does.

Results are printed as JSON so Claude can read them exactly. Exit codes: 0 done, 1 something is
wrong with the folder or its files, 2 a mistake in the command, 3 refused on purpose (the message
says why).
"""

import argparse
import datetime as dt
import json
import re
import sys

from . import __version__, net, scan, settings, store
from . import add, choices, configure, page, replay, rules, titles, track, verdicts
from . import init as starter
from . import queue as triage_queue
from .clock import Clock
from .discover import discover
from .errors import NotFound, Refused


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
    clock = _clock(a.folder)
    if a.as_of:  # replays compare dates, so they pin the clock
        clock = Clock(settings.load(a.folder).timezone, fixed=dt.datetime.fromisoformat(a.as_of))
    summary = scan.run(a.folder, only=a.only, clock=clock)
    due = track.due(a.folder, clock)  # every scan also runs the day-21 close
    summary["closed_day_21"] = due["closed_now"]
    summary["follow_ups_due"] = {k: len(due[k]) for k in ("send", "find_person", "closing")}
    _out(summary)
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
    _out(add.add_file(a.folder, a.file, _clock(a.folder), text_from=a.text_from or "", anyway=a.anyway))
    return 0


def cmd_add_link(a):
    _out(add.add_link(a.folder, a.url, _clock(a.folder), company=a.company or ""))
    return 0


def cmd_page(a):
    return 0  # the page is written after every command that changes something; see main()


def cmd_record_choices(a):
    _out(choices.record_file(a.folder, _clock(a.folder), a.file))
    return 0


def cmd_settings(a):
    if a.action == "show":
        _out(configure.show(a.folder))
    elif a.action == "set":
        old, new = configure.set_value(a.folder, a.key, a.value, why=a.why or "", accept=a.accept_flips or (),
                                       clock=_clock(a.folder))
        _out({"setting": a.key, "was": old, "now": new})
    else:
        same_as = json.loads(a.same_as) if a.same_as else None
        _out(configure.phrase_reject(a.folder, a.name, a.phrases, a.min_distinct, a.reason, same_as,
                                     why=a.why or "", accept=a.accept_flips or (), clock=_clock(a.folder)))
    return 0


def cmd_replay(a):
    phrase = None
    if a.phrase_reject:
        phrase = {"name": a.phrase_reject, "phrases": a.phrases or "", "min_distinct": a.min_distinct,
                  "reason": a.reason or ""}
    _out(replay.settings_change(a.folder, _clock(a.folder), sets=a.set or [], phrase=phrase))
    return 0


def cmd_rule_evidence(a):
    _out(rules.evidence(a.folder, a.number, words=a.words))
    return 0


def cmd_change_rule(a):
    if a.new is None and a.number is None:
        raise Refused("give the rule's number, or --new and its plain name")
    _out(rules.change(a.folder, _clock(a.folder), n=a.number, text_file=a.text, why=a.why or "", replay_file=a.replay,
                      accept=a.accept_flips or (), retire=a.retire, flag_file=a.flag_text, new_name=a.new or "",
                      name=a.name or ""))
    return 0


def cmd_decline(a):
    _out(rules.decline(a.folder, _clock(a.folder), a.what, a.why or "", proposal=a.proposal or ""))
    return 0


def cmd_requeue(a):
    _out(rules.requeue(a.folder, _clock(a.folder), a.keys, a.why))
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
        patterns = {"function": a.function, "level": a.level, "exclude": a.exclude, "field_words": a.field_words}
        result = titles.try_patterns(a.folder, sample=a.sample, seed=a.seed, **patterns)
        replay.record_titles(a.folder, _clock(a.folder), patterns, result)  # the replay a title change needs
        _out(result)
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

    s = sub.add_parser("add", help="save a posting the user found: a file with the scan's header, from anywhere")
    s.add_argument("--folder", required=True)
    s.add_argument("file")
    s.add_argument("--text-from", choices=("link", "pasted"), help="Claude read it from the link, or the user pasted it")
    s.add_argument("--anyway", action="store_true", help="save it even though it looks like one already saved")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("add-link", help="save a posting from a link to a job board the engine reads")
    s.add_argument("--folder", required=True)
    s.add_argument("url")
    s.add_argument("--company", help="the company's name, when its board isn't one the user watches")
    s.set_defaults(func=cmd_add_link)

    s = sub.add_parser("page", help="write the jobs page: data/page.json, data/jobs-page.html and My jobs.html")
    s.add_argument("--folder", required=True)
    s.set_defaults(func=cmd_page)

    s = sub.add_parser("record-choices", help="record the choices the user made on the jobs page")
    s.add_argument("--folder", required=True)
    s.add_argument("file", help="a JSON list of choices, or the pasted 'Copy my choices' text")
    s.set_defaults(func=cmd_record_choices)

    s = sub.add_parser("settings", help="show or change one setting, checked before it's saved")
    acts = s.add_subparsers(dest="action", required=True)
    x = acts.add_parser("show")
    x.add_argument("--folder", required=True)
    x = acts.add_parser("set")
    x.add_argument("--folder", required=True)
    x.add_argument("key", help="section.name, for example titles.function")
    x.add_argument("value")
    x.add_argument("--why", help="the user's own words for a change to how jobs are screened")
    x.add_argument("--accept-flips", nargs="*", metavar="KEY", help="jobs the user agreed this change may turn away")
    x = acts.add_parser("phrase-reject")
    x.add_argument("--folder", required=True)
    x.add_argument("name")
    x.add_argument("--phrases", required=True)
    x.add_argument("--min-distinct", type=int, default=2)
    x.add_argument("--reason", default="")
    x.add_argument("--same-as", help='JSON object, for example {"net revenue retention": "nrr"}')
    x.add_argument("--why", help="the user's own words for this rule")
    x.add_argument("--accept-flips", nargs="*", metavar="KEY", help="jobs the user agreed this rule may turn away")
    s.set_defaults(func=cmd_settings)

    s = sub.add_parser("replay", help="what a change to the scan's rules would do to every saved posting")
    s.add_argument("--folder", required=True)
    s.add_argument("--set", nargs=2, action="append", metavar=("KEY", "VALUE"), help="a setting to change; repeat for several")
    s.add_argument("--phrase-reject", metavar="NAME", help="a phrase rule to add or change, with --phrases")
    s.add_argument("--phrases")
    s.add_argument("--min-distinct", type=int, default=2)
    s.add_argument("--reason")
    s.set_defaults(func=cmd_replay)

    s = sub.add_parser("rule-evidence", help="what a change to one of the user's triage rules could touch")
    s.add_argument("--folder", required=True)
    s.add_argument("number", type=int)
    s.add_argument("--words", help="a pattern of the rule's words, to find passing postings it could newly catch")
    s.set_defaults(func=cmd_rule_evidence)

    s = sub.add_parser("change-rule", help="change, retire or add a triage rule in rules.md, with its replay and history")
    s.add_argument("--folder", required=True)
    s.add_argument("number", type=int, nargs="?")
    s.add_argument("--text", help="a file holding the rule's new lines (Not a fit when, Doesn't count, Why)")
    s.add_argument("--why", help="the user's own words for the change")
    s.add_argument("--replay", help="a JSON file: the postings checked, and each one that would flip")
    s.add_argument("--accept-flips", nargs="*", metavar="KEY", help="jobs the user agreed this change may turn away")
    s.add_argument("--retire", action="store_true", help="retire the rule; its number is kept")
    s.add_argument("--flag-text", help="with --retire: a file holding the flag it becomes")
    s.add_argument("--new", metavar="NAME", help="add a rule with the next number and this plain name")
    s.add_argument("--name", help="rename the rule")
    s.set_defaults(func=cmd_change_rule)

    s = sub.add_parser("decline", help="record a proposed rule change the user turned down")
    s.add_argument("--folder", required=True)
    s.add_argument("--what", required=True, help='what it would have changed: "rule 4", "setting places.hybrid_ok", "phrase rule NAME"')
    s.add_argument("--why", help="the user's own words")
    s.add_argument("--proposal", help="the change, in plain words")
    s.set_defaults(func=cmd_decline)

    s = sub.add_parser("requeue", help="put jobs a loosened rule turned away back on the waiting list")
    s.add_argument("--folder", required=True)
    s.add_argument("keys", nargs="+")
    s.add_argument("--why", required=True, help="the change that lets them through, in plain words")
    s.set_defaults(func=cmd_requeue)

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


# Commands after which the jobs page is written again, so it always shows the records as they are.
REFRESHES = {"scan", "mark", "add", "add-link", "apply", "track", "due", "record-choices", "page", "requeue"}


def _refresh_page(folder, report):
    try:
        summary = page.refresh(folder, _clock(folder))
    except Exception as e:  # the page must never cost the user the change they just made
        print(f"the jobs page wasn't updated: {type(e).__name__}: {e}", file=sys.stderr)
        return
    if report:
        _out(summary)


def main(argv):
    p = parser()
    a = p.parse_args(argv)
    if not getattr(a, "func", None):
        p.print_help()
        return 0
    try:
        code = a.func(a)
        if code == 0 and a.command in REFRESHES:
            _refresh_page(a.folder, a.command == "page")
        return code
    except FileNotFoundError as e:
        print(f"missing file: {e.filename}", file=sys.stderr)
        return 1
    except NotFound as e:
        print(str(e), file=sys.stderr)
        return 1
    except Refused as e:
        print(str(e), file=sys.stderr)
        return 3
