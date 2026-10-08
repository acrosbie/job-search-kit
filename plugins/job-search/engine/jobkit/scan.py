"""One scan: read every watched board, keep the titles and places that fit, save what's new,
apply the automatic rejects, and report. Ported from the reference scanner's run(), in the same
order, so a recorded set of board answers gives the same result in both.
"""

import concurrent.futures as cf
import re

from . import health, screen, settings, store
from .boards import READERS, Context, watched_names
from .clock import Clock
from .text import salary_from, salary_range

WORKERS = 16  # boards fetched at once: I/O bound, and polite to any one host

# The system name a board's posting keys start with, where it differs from its `ats` value.
KEY_SYSTEM = {"careers_api": "careers-api"}
LOCATION_CODES = {screen.IN_COUNTRY, screen.REMOTE_ONLY, screen.COUNTRY_WIDE, screen.UNKNOWN}


def key_prefix(ats, slug):
    """The start of every posting key a board gives: <system>-<company slug>-."""
    return f"{KEY_SYSTEM.get(ats, ats)}-{re.sub(r'[^a-z0-9]+', '-', slug.lower()).strip('-')}-"


def owner(key, prefixes):
    """The board a posting key belongs to: the longest board prefix it starts with, so that acme's
    postings are never taken for acme-health's (or the other way round). None if no board's."""
    best = None
    for prefix, name in prefixes:
        if key.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, name)
    return best[1] if best else None


def _group_key(r):
    return r["company"].lower(), re.sub(r"[^a-z0-9]+", " ", r["title"].lower()).strip()


def _flag_text(flags):
    return "; ".join(text for _, text in flags if text)


def run(root, only=None, clock=None, workers=WORKERS):
    s = settings.load(root)
    companies = settings.load_companies(root)
    clk = clock or Clock(s.timezone)
    today, stamp = clk.today(), clk.stamp()
    folder = store.Folder(root)
    state = folder.load_postings()
    postings, boards = state["postings"], state["boards"]
    ctx = Context(workday=s.workday, watched=watched_names(companies))

    queue, manual = [], []
    for c in companies:
        if only and c["slug"] != only:
            continue
        ats = c.get("ats", "manual")
        if ats == "manual":
            manual.append(c)
            continue
        queue.append((c["slug"], ats, c))
    # A board no longer on the watchlist, or moved to "manual", loses its health row. Its postings stay.
    if not only:
        live = {c["slug"] for c in companies if c.get("ats", "manual") != "manual"}
        for k in [k for k in boards if k not in live]:
            del boards[k]

    def guarded(job):
        name, ats, c = job
        try:
            if ats not in READERS:
                raise ValueError(f"unknown ats '{ats}'")
            return name, ats, c, READERS[ats](c, ctx), None
        except Exception as e:  # one dead board must not stop the scan
            return name, ats, c, None, f"{type(e).__name__}: {e}"

    answered, failures = [], []
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for name, ats, c, recs, err in pool.map(guarded, queue):
            before = boards.get(name, {})
            # For scan health: when the board was first read, and the last day it listed any job.
            first = before.get("first_read") or today
            if err is None:
                answered.append((name, recs))
                boards[name] = {"ats": ats, "last_ok": stamp, "jobs": len(recs), "error": "", "fails": 0,
                                "first_read": first, "last_listed": today if recs else before.get("last_listed", "")}
            else:
                failures.append({"board": c.get("name", name), "slug": name, "error": err})
                # A failed board must not keep showing last run's numbers as if they were current.
                b = boards.setdefault(name, {"ats": ats, "last_ok": "", "jobs": 0})
                b.update({"error": err, "jobs": "", "matched": "", "stale": True, "fails": before.get("fails", 0) + 1,
                          "first_read": first})

    applications = folder.load_applications()
    new, rejected, matched = [], [], 0
    # Every job a board lists is still there, whether or not it passes the filters today: one added by
    # link, or kept under older title or place settings, mustn't read as gone while it's listed.
    present = {r["key"] for _, recs in answered for r in recs}
    boards_seen = []
    for name, recs in answered:
        n, dropped_title, dropped_loc = 0, 0, 0
        survivors = []
        for r in recs:
            if not screen.title_ok(r["title"], s):
                dropped_title += 1
                continue
            keep, code = screen.location_ok(r["location"], s)
            if not keep:
                dropped_loc += 1
                continue
            survivors.append((r, code))

        # One role listed in several places arrives as several job ids. Collapse them onto one entry,
        # preferring an id already saved so its verdict and history survive, and re-check the place
        # against the merged list: Chicago alone reads as far away; "Chicago; Denver" doesn't.
        groups = {}
        for r, code in survivors:
            groups.setdefault(_group_key(r), []).append((r, code))
        deduped = []
        for members in groups.values():
            rec, code = next((m for m in members if m[0]["key"] in postings), members[0])
            if len(members) > 1:
                places = [m[0]["location"] for m in members if m[0]["location"]]
                rec["location"] = "; ".join(dict.fromkeys(places))
                _, code = screen.location_ok(rec["location"], s)
            deduped.append((rec, code))
        boards_seen.append((name, deduped, dropped_title, dropped_loc))

    # Descriptions for the jobs not saved yet (or saved before their description could be read),
    # fetched together rather than one at a time, then used in the board order above.
    to_read = [r for _, deduped, _, _ in boards_seen for r, _ in deduped
               if r["key"] not in postings or postings[r["key"]].get("unread")]
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        fetched = dict(zip([r["key"] for r in to_read], pool.map(read_description, to_read)))

    for name, deduped, dropped_title, dropped_loc in boards_seen:
        n = 0
        for r, code in deduped:
            matched += 1
            n += 1
            entry = postings.get(r["key"])
            if entry:
                entry["last_seen"] = today
                entry["title"] = r["title"]
                if entry.get("location") != r["location"]:  # a role that moves must not keep its old place flag
                    entry["location"] = r["location"]
                    kept = [(f.get("code", ""), f.get("text", "")) for f in entry.get("flags", [])
                            if f.get("code") not in LOCATION_CODES]  # contract, on-site, applied: still true
                    flags = ([(code, screen.location_flag(code, s))] if code else []) + kept
                    entry["flag"] = _flag_text(flags)
                    entry["flags"] = [{"code": c, "text": t} for c, t in flags]
                if entry.get("unread"):
                    done = read_again(folder, r, entry, fetched[r["key"]], code, s, today, stamp)
                    if done and done.get("rule"):
                        rejected.append(done)
                continue
            desc, place, posted, failed = fetched[r["key"]]
            if place:  # a detail call can also return the real place
                r["location"] = place
                keep, code = screen.location_ok(r["location"], s)
                if not keep:
                    matched -= 1
                    n -= 1
                    dropped_loc += 1
                    continue
            if posted and not r["posted"]:
                r["posted"] = posted
            entry, summary = save_new(folder, r, code, desc, s, applications, postings, today, stamp,
                                      unread=failed)
            if entry.get("rule"):
                rejected.append({**summary, "rule": entry["rule"], "reason": entry["note"]})
            else:
                new.append(summary)
        if name in boards:
            boards[name].update({"matched": n, "dropped_title": dropped_title, "dropped_location": dropped_loc,
                                 "stale": False})

    # Only the board a posting belongs to can retire it, and only when that board answered this scan:
    # missing from its list = gone. Every watched board counts for ownership, answered or not.
    prefixes = [(key_prefix(c.get("ats", ""), c["slug"]), c["slug"]) for c in companies
                if c.get("ats", "manual") != "manual"]
    # A board read only up to a cap (ctx.partial) may still list what it didn't return.
    answered_names = {name for name, _ in answered} - ctx.partial
    for k, v in postings.items():
        if v.get("source") == "manual":
            continue
        if k in present:
            v.pop("gone", None)
            v["last_seen"] = today
        elif owner(k, prefixes) in answered_names:
            v.setdefault("gone", today)

    # Postings added by hand carry no pay yet; read it from their saved description.
    for k, v in postings.items():
        if "salary" not in v:
            text = folder.read_description(k) or ""
            v["salary"] = salary_from(text)

    folder.save_postings(state)
    folder.write_titles([(name, r.get("title"), r.get("location")) for name, recs in answered for r in recs])

    names = {name for name, _ in answered}
    read = sum(len(recs) for _, recs in answered)
    dropped_title = sum(b.get("dropped_title", 0) or 0 for k, b in boards.items() if k in names)
    dropped_loc = sum(b.get("dropped_location", 0) or 0 for k, b in boards.items() if k in names)
    by_rule = {}
    for x in rejected:
        by_rule[x["rule"]] = by_rule.get(x["rule"], 0) + 1
    row = {"at": stamp, "boards": len(answered), "failed": len(failures), "read": read,
           "dropped_title": dropped_title, "dropped_location": dropped_loc, "matched": matched,
           "new": len(new), "rejected_by_rule": by_rule, "total_seen": len(postings)}
    if only:
        row["only"] = only  # one board: not the scan the schedule asks for (schedule.scan_overdue)
    folder.log_run(row)
    return {
        **row,
        "new_postings": new,
        "rejected_postings": rejected,
        "failures": failures,
        "check_by_hand": [{"name": c["name"], "careers_url": c.get("careers_url", "")} for c in manual],
        "health": health.boards(boards, companies, s, today),
    }


def read_description(r):
    """(description, place, posted date, failed) for one record a reader returned. Some boards need a
    second call for the description, made only now; it can also return the real place and date ("" if
    not). `failed` is the error, in a few words, when that call didn't answer ("" when it did)."""
    try:
        desc = r["description"] if r["description"] is not None else (r["detail"]() if r["detail"] else "")
        if isinstance(desc, dict):
            return desc["description"], desc.get("location") or "", desc.get("posted") or "", ""
        return desc, "", "", ""
    except Exception as e:
        return "", "", "", f"{type(e).__name__}: {e}"


def read_again(folder, r, entry, got, code, s, today, stamp):
    """A posting saved while its description couldn't be read: if it can be now, save the text, read
    its pay, and screen it as a new posting is screened, unless someone has decided it already.
    Returns the summary of an automatic reject, or None."""
    desc, _, _, failed = got
    if failed:
        return None
    folder.save_description(r, desc, today)
    rng = salary_range(desc)
    entry.update({"salary": salary_from(desc), "pay_low": rng[0] if rng else None, "pay_high": rng[1] if rng else None})
    entry.pop("unread", None)
    flags = [(f.get("code", ""), f.get("text", "")) for f in entry.get("flags", []) if f.get("code") != "unread"]
    status, rule, reason, more = screen.assess(entry.get("location", ""), code, desc, s)
    flags += [f for f in more if f[0] not in {c for c, _ in flags}]
    entry["flag"] = _flag_text(flags)
    entry["flags"] = [{"code": c, "text": t} for c, t in flags]
    if entry.get("status") != "new" or not reason:
        return None
    entry.update({"status": status, "note": reason, "rule": rule, "triaged": today})
    folder.log_decision({"at": stamp, "date": today, "key": r["key"], "company": entry.get("company", ""),
                         "title": entry.get("title", ""), "verdict": status, "rule": rule, "reason": reason, "by": "rule"})
    return {"key": r["key"], "company": entry.get("company", ""), "title": entry.get("title", ""),
            "location": entry.get("location", ""), "flag": entry["flag"], "salary": entry["salary"],
            "rule": rule, "reason": reason}


def save_new(folder, r, code, desc, s, applications, postings, today, stamp, reject=None, extra_flags=(), unread=""):
    """Save one newly found posting: its description file, its record with the automatic verdict and
    flags, and a decisions.log line when a rule rejected it. Scan, add and add-link all come through
    here, so a posting is screened the same way however it arrived. `reject` is (rule, reason) for a
    rejection decided before this point. `unread` is why its description couldn't be fetched: then no
    rule that reads the description is applied (an error message has no remote wording), and the next
    scan tries again. Returns (entry, summary); the caller saves postings.json."""
    body = desc if isinstance(desc, str) else ""
    status, rule, reason, flags = screen.assess(r["location"], code, body, s)
    if unread:
        status, rule, reason = "new", "", ""
        flags = [f for f in flags if f[0] in LOCATION_CODES] + [("unread", s.label("flag_unread"))]
        desc = f"(The description couldn't be read on {today}: {unread}. The next scan tries again.)"
    if reject:
        status, (rule, reason) = "not_a_fit", reject
    # An application made outside the scan (LinkedIn, a company site) is flagged, never marked
    # applied: that is the user's action.
    app = store.application_for({"company": r["company"], "title": r["title"], "url": r["url"]}, applications, loose=True)
    if app:
        flags.append(("applied", s.label("flag_applied", applied=app.get("applied_date") or app.get("applied", ""))))
    pasted = store.pasted_match(r["company"], r["title"], postings) if r["ats"] != "manual" else None
    if pasted:
        flags.append(("pasted", s.label("flag_pasted", date=postings[pasted].get("first_seen", ""))))
    flags += list(extra_flags)

    rng = salary_range(body)
    entry = {
        "salary": salary_from(body),
        "pay_low": rng[0] if rng else None,
        "pay_high": rng[1] if rng else None,
        "status": status,
        "first_seen": today,
        "last_seen": today,
        "company": r["company"],
        "title": r["title"],
        "location": r["location"],
        "url": r["url"],
        "posted": r["posted"],
        "source": r["ats"],
        "flag": _flag_text(flags),
        "flags": [{"code": c, "text": t} for c, t in flags],
        "file": folder.save_description(r, desc, today),
    }
    if unread:
        entry["unread"] = True
    postings[r["key"]] = entry
    summary = {"key": r["key"], "company": r["company"], "title": r["title"], "location": r["location"],
               "flag": entry["flag"], "salary": entry["salary"]}
    if reason:
        entry.update({"note": reason, "rule": rule, "triaged": today})
        folder.log_decision({"at": stamp, "date": today, "key": r["key"], "company": r["company"],
                             "title": r["title"], "verdict": status, "rule": rule, "reason": reason, "by": "rule"})
    return entry, summary
