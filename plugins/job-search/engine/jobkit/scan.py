"""One scan: read every watched board, keep the titles and places that fit, save what's new,
apply the automatic rejects, and report. Ported from the reference scanner's run(), in the same
order, so a recorded set of board answers gives the same result in both.
"""

import concurrent.futures as cf
import re

from . import screen, settings, store
from .boards import READERS, Context, watched_names
from .clock import Clock
from .text import salary_from, salary_range

WORKERS = 16  # boards fetched at once: I/O bound, and polite to any one host

# The system name a board's posting keys start with, where it differs from its `ats` value.
KEY_SYSTEM = {"careers_api": "careers-api"}


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
            if err is None:
                answered.append((name, recs))
                boards[name] = {"ats": ats, "last_ok": stamp, "jobs": len(recs), "error": ""}
            else:
                failures.append({"board": c.get("name", name), "slug": name, "error": err})
                # A failed board must not keep showing last run's numbers as if they were current.
                b = boards.setdefault(name, {"ats": ats, "last_ok": "", "jobs": 0})
                b.update({"error": err, "jobs": "", "matched": "", "stale": True})

    applications = folder.load_applications()
    new, rejected, matched = [], [], 0
    present = set()
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

        for r, code in deduped:
            matched += 1
            n += 1
            present.add(r["key"])
            entry = postings.get(r["key"])
            if entry:
                entry["last_seen"] = today
                entry["title"] = r["title"]
                if entry.get("location") != r["location"]:  # a role that moves must not keep its old flag
                    entry["location"] = r["location"]
                    flags = [(code, screen.location_flag(code, s))] if code else []
                    entry["flag"] = _flag_text(flags)
                    entry["flags"] = [{"code": c, "text": t} for c, t in flags]
                continue
            try:
                desc = r["description"] if r["description"] is not None else (r["detail"]() if r["detail"] else "")
                if isinstance(desc, dict):  # a detail call can also return the real place and date
                    if desc.get("location"):
                        r["location"] = desc["location"]
                        keep, code = screen.location_ok(r["location"], s)
                        if not keep:
                            matched -= 1
                            n -= 1
                            dropped_loc += 1
                            present.discard(r["key"])
                            continue
                    if desc.get("posted") and not r["posted"]:
                        r["posted"] = desc["posted"]
                    desc = desc["description"]
            except Exception as e:
                desc = f"(description fetch failed: {type(e).__name__}: {e})"
            body = desc if isinstance(desc, str) else ""

            status, rule, reason, flags = screen.assess(r["location"], code, body, s)
            # An application made outside the scan (LinkedIn, a company site) is flagged, never marked
            # applied: that is the user's action.
            app = store.application_for({"company": r["company"], "title": r["title"], "url": r["url"]}, applications)
            if app:
                flags.append(("applied", s.label("flag_applied", applied=app.get("applied", ""))))

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
            postings[r["key"]] = entry
            summary = {"key": r["key"], "company": r["company"], "title": r["title"], "location": r["location"],
                       "flag": entry["flag"], "salary": entry["salary"]}
            if reason:
                entry.update({"note": reason, "rule": rule, "triaged": today})
                folder.log_decision({"at": stamp, "date": today, "key": r["key"], "company": r["company"],
                                     "title": r["title"], "verdict": status, "rule": rule, "reason": reason, "by": "rule"})
                rejected.append({**summary, "rule": rule, "reason": reason})
            else:
                new.append(summary)
        if name in boards:
            boards[name].update({"matched": n, "dropped_title": dropped_title, "dropped_location": dropped_loc,
                                 "stale": False})

    # Only a board that answered this scan can retire its postings: missing from its list = gone.
    prefixes = set()
    for name, _ in answered:
        ats = boards.get(name, {}).get("ats", "")
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        prefixes.add(f"{KEY_SYSTEM.get(ats, ats)}-{slug}-")
    for k, v in postings.items():
        if v.get("source") == "manual":
            continue
        if k in present:
            v.pop("gone", None)
        elif any(k.startswith(p) for p in prefixes):
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
    folder.log_run(row)
    return {
        **row,
        "new_postings": new,
        "rejected_postings": rejected,
        "failures": failures,
        "check_by_hand": [{"name": c["name"], "careers_url": c.get("careers_url", "")} for c in manual],
    }
