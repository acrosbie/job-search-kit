"""The user's triage rules, profile/rules.md: what a change to one could touch, and saving the change
with its history.

Setup writes rules.md and triage reads it (reference/profile-format.md). Each rule is a section,
"### Rule N: <plain name>", with "- Not a fit when:", "- Doesn't count:", "- Why:" and "- Changes:"
lines. Numbers never change; a retired rule keeps its number.

Claude applies these rules by reading, so Claude also replays a change to one: `evidence` lists the
postings it fired on, the user's overturns of it, and the passing postings whose text has the rule's
words, with those lines quoted; Claude judges each under the old and new wording and writes what
would flip. `change` saves the new wording only with that replay, the user's words, and their
acceptance of any job they applied to or wanted that it would turn away (the same guard as a
setting, changes.py), then appends a dated "Changes:" line and logs it.
"""

import json
import os
import re

from . import changes, store, verdicts
from .errors import NotFound, Refused

HEADING = re.compile(r"^### Rule (\d+):\s*(.*?)\s*$")
CANDIDATES_MAX = 40
SNIPPETS = 3


def path(root):
    return os.path.join(root, "profile", "rules.md")


def read(root):
    with open(path(root), encoding="utf-8") as f:
        return f.read()


def write(root, text):
    with open(path(root), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sections(lines):
    """{number: (name, first line, end line)} for every "### Rule N:" section."""
    out = {}
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if not m:
            continue
        end = i + 1
        while end < len(lines) and not lines[end].startswith(("### ", "## ")):
            end += 1
        out[int(m.group(1))] = (m.group(2), i, end)
    return out


def cites(reason, n):
    """Whether a verdict's note cites rule n ("Rule 4 (Owns the close): ...")."""
    return bool(re.match(rf"\s*Rule {n}(?!\d)", reason or ""))


def _snippets(text, rx):
    out = []
    for m in rx.finditer(text):
        lo, hi = max(0, m.start() - 110), min(len(text), m.end() + 110)
        out.append(re.sub(r"\s+", " ", text[lo:hi]).strip())
        if len(out) >= SNIPPETS:
            break
    return out


def evidence(root, n, words=None):
    lines = read(root).splitlines()
    found = sections(lines)
    if n not in found:
        raise NotFound(f"there's no Rule {n} in rules.md")
    name, start, end = found[n]
    folder = store.Folder(root)
    postings = folder.load_postings()["postings"]
    decisions = folder.read_decisions()
    since = changes.last_change(folder.read_changes(), f"rule {n}")

    fired, overturned = {}, []
    for d in decisions:
        k = d.get("key")
        if d.get("by") == "claude" and d.get("verdict") == "not_a_fit" and cites(d.get("reason"), n):
            fired[k] = d
        elif d.get("by") == "user" and k in fired and d.get("reverses") == "not_a_fit":
            overturned.append({"key": k, "num": postings.get(k, {}).get("num"), "company": d.get("company", ""),
                               "title": d.get("title", ""), "now": d.get("verdict"), "their_words": d.get("reason", ""),
                               "date": d.get("date", ""), "since_last_change": d.get("at", "") > since,
                               "rule_said": fired[k].get("reason", "")})

    def brief(k, v):
        return {"key": k, "num": v.get("num"), "company": v.get("company", ""), "title": v.get("title", ""),
                "status": v.get("status", ""), "description_file": f"data/postings/{v.get('file') or k + '.md'}"}

    out = {"rule": n, "name": name, "text": "\n".join(lines[start:end]).strip(), "last_changed": since,
           "fired": [{**brief(k, postings.get(k, {})), "quote": d.get("reason", ""), "date": d.get("date", "")}
                     for k, d in fired.items()],
           "overturned": overturned, "candidates": []}
    if words:
        rx = re.compile(words, re.I)
        for k, v in sorted(postings.items(), key=lambda kv: kv[1].get("first_seen", ""), reverse=True):
            if k in fired or v.get("status") == "not_a_fit":
                continue
            text = folder.read_description(k) or ""
            hits = _snippets(text.partition("\n---\n")[2] or text, rx)
            if hits:
                out["candidates"].append({**brief(k, v), "lines": hits})
            if len(out["candidates"]) >= CANDIDATES_MAX:
                break
    return out


def _replay(root, replay_file):
    """Claude's replay of a rule change: {"checked": [keys], "flips": [{"key", "after", "quote"}]},
    where "after" is not_a_fit, your_call or passes. Returns it with the engine's own reading of
    which flips need the user's acceptance."""
    with open(replay_file, encoding="utf-8") as f:
        rep = json.load(f)
    folder = store.Folder(root)
    postings = folder.load_postings()["postings"]
    last = changes.last_decisions(folder)
    checked = list(dict.fromkeys(rep.get("checked") or []))
    flips = []
    for f in rep.get("flips") or []:
        k = f.get("key")
        if k not in postings:
            raise Refused(f"the replay names a posting that isn't saved: {k}")
        if f.get("after") not in ("not_a_fit", "your_call", "passes"):
            raise Refused(f"a flip's \"after\" is not_a_fit, your_call or passes, not {f.get('after')!r}")
        v = postings[k]
        flips.append({"key": k, "num": v.get("num"), "company": v.get("company", ""), "title": v.get("title", ""),
                      "status": v.get("status", ""), "decided_by": last.get(k, {}).get("by", ""),
                      "after": f["after"], "quote": f.get("quote", "")})
    return {
        "kind": "rule", "checked": len(checked), "flips": flips,
        "wanted": [f["key"] for f in flips if f["after"] == "not_a_fit" and changes.wanted(postings[f["key"]], last.get(f["key"]))],
        "would_pass": [f["key"] for f in flips if f["after"] != "not_a_fit" and postings[f["key"]].get("status") == "not_a_fit"
                       and last.get(f["key"], {}).get("by") != "user"],
    }


def _clean(text):
    """The new wording: its own lines, without a heading or history, which the engine writes."""
    keep = [line.rstrip() for line in text.strip().splitlines()
            if line.strip() and not line.startswith(("### ", "## ")) and not line.lstrip().startswith("- Changes:")]
    if not keep:
        raise Refused("the new wording is empty")
    return keep


def _history_line(clock, why, rep):
    names = "; ".join(f"{f['company']}, {f['title']} ({f['after'].replace('_', ' ')})" for f in rep["flips"][:6])
    more = f" and {len(rep['flips']) - 6} more" if len(rep["flips"]) > 6 else ""
    return (f"- Changes: {clock.today()}: \"{why.strip()}\". Replayed over {rep['checked']} saved postings: "
            + (f"{len(rep['flips'])} would change: {names}{more}." if rep["flips"] else "nothing would change."))


def change(root, clock, n=None, text_file=None, why="", replay_file=None, accept=(), retire=False, flag_file=None,
           new_name="", name=""):
    """Change, retire or add a rule. Returns what was saved, with the replay and the jobs that would now pass."""
    if not (why or "").strip():
        raise Refused("give the user's own words for this change with --why")
    if not replay_file:
        raise Refused("replay this change first: judge the postings rule-evidence lists, and give the result with --replay")
    rep = _replay(root, replay_file)
    missing = [k for k in rep["wanted"] if k not in set(accept)]
    if missing:
        postings = store.Folder(root).load_postings()["postings"]
        names = "; ".join(f"{postings[k].get('company', '')}, {postings[k].get('title', '')}" for k in missing)
        raise Refused(f"this change would turn away jobs the user applied to or wanted ({names}). Save it only if "
                      f"they accept that, naming each one with --accept-flips")

    before = read(root)
    lines = before.splitlines()
    found = sections(lines)
    body = []
    if text_file:
        with open(text_file, encoding="utf-8") as f:
            body = _clean(f.read())

    if new_name:
        n = max(found, default=0) + 1
        kind, what, old = "added", f"rule {n}", None
        flags_at = next((i for i, line in enumerate(lines) if line.startswith("## Flags")), len(lines))
        section = [f"### Rule {n}: {new_name.strip()}"] + body + [_history_line(clock, why, rep), ""]
        lines[flags_at:flags_at] = section
    else:
        if n not in found:
            raise NotFound(f"there's no Rule {n} in rules.md")
        current, start, end = found[n]
        old = "\n".join(lines[start:end]).strip()
        history = [line for line in lines[start + 1:end] if line.lstrip().startswith("- Changes:")]
        if retire:
            kind = "retired"
            heading = f"### Rule {n}: {re.sub(r' [(]retired .*[)]$', '', current)} (retired {clock.today()})"
            body = [f"- Retired: \"{why.strip()}\"."] + [line for line in lines[start + 1:end]
                                                      if line.strip() and not line.lstrip().startswith("- Changes:")]
        else:
            kind = "changed"
            if not body:
                raise Refused("give the rule's new wording with --text")
            heading = f"### Rule {n}: {(name or current).strip()}"
        section = [heading] + body + history + [_history_line(clock, why, rep), ""]
        lines[start:end] = section
        what = f"rule {n}"

    if retire and flag_file:
        with open(flag_file, encoding="utf-8") as f:
            flag = [line.rstrip() for line in f.read().strip().splitlines()]
        if not flag or not flag[0].startswith("### "):
            raise Refused("a flag starts with its own '### <plain name>' line")
        scan_at = next((i for i, line in enumerate(lines) if line.startswith("## Rules the scan applies")), len(lines))
        lines[scan_at:scan_at] = flag + [""]

    text = "\n".join(lines).rstrip("\n") + "\n"
    write(root, text)
    saved = text.splitlines()
    _, start, end = sections(saved)[n]
    new = "\n".join(saved[start:end]).strip()
    summary = {**changes.summary(rep), "flipped": [f"{f['company']}, {f['title']}" for f in rep["flips"]][:20]}
    changes.log(root, clock, what, kind, old, new, why, summary, accept)
    return {"rule": n, "kind": kind, "replay": summary, "would_pass": rep["would_pass"]}


def decline(root, clock, what, why, proposal=""):
    """A proposal the user turned down: logged, so the weekly review leaves it alone for four weeks."""
    if not (why or "").strip():
        raise Refused("give the user's own words for turning it down with --why")
    return changes.log(root, clock, what, "declined", None, proposal or None, why)


def requeue(root, clock, keys, why):
    """Put jobs a rule turned away back on the waiting list, after the rule was loosened. Never one the
    user decided: their decision stands."""
    done, refused = [], []
    postings = store.Folder(root).load_postings()["postings"]
    for k in keys:
        v = postings.get(k)
        if not v:
            refused.append({"key": k, "why": "not a saved posting"})
            continue
        if v.get("status") != "not_a_fit":
            refused.append({"key": k, "why": f"it isn't turned away (it's {v.get('status', '').replace('_', ' ')})"})
            continue
        try:
            verdicts.mark(root, k, "new", "claude", note=f"Back on your list: {why}", clock=clock)
        except Refused as e:
            refused.append({"key": k, "why": str(e)})
            continue
        done.append({"key": k, "num": v.get("num"), "company": v.get("company", ""), "title": v.get("title", "")})
    return {"requeued": done, "refused": refused}
