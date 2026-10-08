"""The records in the user's folder, and the only code that writes them.

    data/postings.json        every matched posting and its status, plus each board's health
    data/postings.backup.json the previous postings.json, rewritten before every save
    data/postings/<key>.md    one saved description per posting
    data/applications.json    every application and what happened next (see track.py)
    data/applications.backup.json  the previous applications.json
    data/decisions.log        every verdict, by rule, Claude or the user; one JSON object a line, append-only
    data/runs.log             one JSON object per scan, append-only
    data/titles-latest.tsv    every title read on the last scan, for testing a title change on real data
    data/reviews.log          one JSON object per weekly review prepared or gone through, append-only
    data/changes.log          every change to the screening rules, and every one declined, append-only
    data/choices.log          every click from the jobs page that was handled, and what happened to it, append-only
    data/review.json          the weekly review last prepared
    data/replay-latest.json   the last replay of a proposed rule change, which saving it must match
    data/page.json            what the jobs page shows (see page.py)
    data/jobs-page.html       the jobs page with its data built in, for Claude to publish
    My jobs.html              the jobs page as a file, at the top of the folder

Nothing here deletes a file. Cowork's workspace on the user's computer isn't allowed to, and
replacing a file by renaming over it may count as deleting. Files are written in place, after the
new content is complete, with the previous postings.json and applications.json kept as backups.

Two commands can run at once: a scheduled scan takes minutes, and the user may record a verdict
meanwhile. So postings.json and applications.json are saved by merging: what this command changed
since it loaded the file is laid onto the file as it is now, record by record and field by field.
Anything another command changed in between stays, unless this one changed the same field. (A lock
file can't be used: the engine couldn't delete it afterwards.)

A file left half-written by a crash is read from its backup instead, and never copied over the
backup.
"""

import copy
import json
import os
import re

STATUSES = ("new", "worth_applying", "your_call", "not_a_fit", "skipped", "applied")


class Loaded(dict):
    """A file's contents as loaded, remembering them as they were, so saving can merge."""
    base = None


def _merge_records(base, mine, theirs):
    """theirs, with every record and field `mine` changed since `base` laid on top. Records are
    dicts keyed by id; a record this writer added is added unless the other writer added it too."""
    out = copy.deepcopy(theirs)
    for k in mine.keys() | base.keys():
        b, m = base.get(k), mine.get(k)
        if m == b:
            continue
        if m is None:  # removed by this writer (the engine never does): leave theirs alone
            continue
        t = out.get(k)
        if b is None or t is None:
            out.setdefault(k, m)
            continue
        if not isinstance(m, dict) or not isinstance(t, dict) or not isinstance(b, dict):
            out[k] = m
            continue
        for f in m.keys() | b.keys():
            if m.get(f, _MISSING) != b.get(f, _MISSING):
                if f in m:
                    t[f] = m[f]
                else:
                    t.pop(f, None)
    return out


_MISSING = object()


class Folder:
    def __init__(self, root):
        self.root = root
        self.data = os.path.join(root, "data")
        self.postings_json = os.path.join(self.data, "postings.json")
        self.backup_json = os.path.join(self.data, "postings.backup.json")
        self.descriptions = os.path.join(self.data, "postings")
        self.applications_json = os.path.join(self.data, "applications.json")
        self.applications_backup_json = os.path.join(self.data, "applications.backup.json")
        self.page_json = os.path.join(self.data, "page.json")
        self.page_publish_html = os.path.join(self.data, "jobs-page.html")
        self.reviews_log = os.path.join(self.data, "reviews.log")
        self.changes_log = os.path.join(self.data, "changes.log")
        self.choices_log = os.path.join(self.data, "choices.log")
        self.review_json = os.path.join(self.data, "review.json")
        self.replay_json = os.path.join(self.data, "replay-latest.json")
        self.page_html = os.path.join(root, "My jobs.html")
        self.decisions_log = os.path.join(self.data, "decisions.log")
        self.runs_log = os.path.join(self.data, "runs.log")
        self.titles_tsv = os.path.join(self.data, "titles-latest.tsv")

    # ------------------------------------------------------------ plumbing

    @staticmethod
    def _read(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _append(self, path, obj):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # A crash mid-write leaves a line with no newline; start a fresh line so this one survives.
        broken = False
        if os.path.exists(path) and os.path.getsize(path):
            with open(path, "rb") as f:
                f.seek(-1, os.SEEK_END)
                broken = f.read(1) != b"\n"
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(("\n" if broken else "") + json.dumps(obj, ensure_ascii=False) + "\n")

    def _lines(self, path):
        if not os.path.exists(path):
            return []
        rows = []
        for line in self._read(path).splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:  # a truncated last line must not break a scan
                continue
        return rows

    def _read_json_or_backup(self, path, backup):
        """(contents, read from the backup) for a JSON file; its backup when the file itself is
        half-written. None when neither exists."""
        if not os.path.exists(path):
            return None, False
        try:
            return json.loads(self._read(path)), False
        except ValueError:
            if os.path.exists(backup):
                return json.loads(self._read(backup)), True
            raise

    def _save_merged(self, path, backup, read, base, new_content):
        """Write `new_content`, keeping the previous good file as the backup. When the file no longer
        holds `read` (what this command read from it), another command wrote it meanwhile: then only
        what changed between `base` (the same records as this command first held them) and
        `new_content` is laid onto the file as it is now."""
        current, from_backup = self._read_json_or_backup(path, backup)
        if read is not None and base is not None and current is not None and current != read:
            new_content = self._merge(base, new_content, current)
        if current is not None and not from_backup:
            self._write(backup, self._read(path))
        self._write(path, json.dumps(new_content, indent=1, ensure_ascii=False))

    # ------------------------------------------------------------ postings

    def load_postings(self):
        state, _ = self._read_json_or_backup(self.postings_json, self.backup_json)
        state = Loaded(state or {})
        state.setdefault("postings", {})
        state.setdefault("boards", {})
        state.base = copy.deepcopy(dict(state))
        return state

    @staticmethod
    def _merge(base, mine, theirs):
        if "applications" in mine:
            key = lambda rows: {a.get("id") or f"#{i}": a for i, a in enumerate(rows)}
            merged = _merge_records(key(base.get("applications", [])), key(mine["applications"]),
                                    key(theirs.get("applications", [])))
            order = [a.get("id") or f"#{i}" for i, a in enumerate(theirs.get("applications", []))]
            order += [k for k in key(mine["applications"]) if k not in order]
            return {**theirs, "applications": [merged[k] for k in order if k in merged]}
        out = dict(theirs)
        for part in ("postings", "boards"):
            out[part] = _merge_records(base.get(part, {}), mine.get(part, {}), theirs.get(part, {}))
        return out

    def save_postings(self, state):
        base = state.base if isinstance(state, Loaded) else None
        self._save_merged(self.postings_json, self.backup_json, base, base, dict(state))

    def description_path(self, key):
        return os.path.join(self.descriptions, f"{key}.md")

    def save_description(self, rec, description, today):
        """The same header as the reference scanner's saved postings, so a person can read it."""
        header = "\n".join([
            f"# {rec['title']}",
            "",
            f"- Company: {rec['company']}",
            f"- Location: {rec['location'] or '(not stated)'}",
            f"- URL: {rec['url']}",
            f"- Posted: {rec['posted'] or '(unknown)'}",
            f"- Source: {rec['ats']}",
            f"- Fetched: {today}",
            f"- Key: {rec['key']}",
            "",
            "---",
            "",
        ])
        self._write(self.description_path(rec["key"]), header + (description or "(no description returned)") + "\n")
        return f"{rec['key']}.md"

    def read_description(self, key):
        p = self.description_path(key)
        return self._read(p) if os.path.exists(p) else None

    # ------------------------------------------------------------ logs

    def log_run(self, row):
        self._append(self.runs_log, row)

    def read_runs(self, limit=None):
        rows = self._lines(self.runs_log)
        return rows[-limit:] if limit else rows

    def log_decision(self, row):
        self._append(self.decisions_log, row)

    def read_decisions(self):
        return self._lines(self.decisions_log)

    def log_review(self, row):
        self._append(self.reviews_log, row)

    def read_reviews(self):
        return self._lines(self.reviews_log)

    def log_change(self, row):
        self._append(self.changes_log, row)

    def read_changes(self):
        return self._lines(self.changes_log)

    def log_choice(self, row):
        self._append(self.choices_log, row)

    def read_choices(self):
        return self._lines(self.choices_log)

    def write_json(self, path, obj):
        self._write(path, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")

    def read_json(self, path):
        return json.loads(self._read(path)) if os.path.exists(path) else None

    def write_titles(self, rows):
        """rows: (board, title, location) for every posting read this scan."""
        out = ["source\ttitle\tlocation"]
        for board, title, loc in rows:
            out.append(f"{board}\t{(title or '').replace(chr(9), ' ')}\t{(loc or '').replace(chr(9), ' ')}")
        self._write(self.titles_tsv, "\n".join(out) + "\n")

    # ------------------------------------------------------------ applications

    def load_applications(self):
        """The records as written. track.load() is the same list with older shapes brought up to date."""
        data, _ = self._read_json_or_backup(self.applications_json, self.applications_backup_json)
        return (data or {}).get("applications", [])

    def save_applications(self, applications, read=None, base=None):
        """`read`: the records as this command read them from the file; `base`: the same, as it first
        held them (track.load brings older shapes up to date). With both, a save merges with anything
        written since."""
        self._save_merged(self.applications_json, self.applications_backup_json,
                          None if read is None else {"applications": read},
                          None if base is None else {"applications": base},
                          {"applications": applications})


def _norm_title(s):
    """Title key for matching a posting to an application: anything from the first parenthesis off,
    & to and, CX, PM, Sr. and Mgr spelled out, punctuation collapsed."""
    s = re.sub(r"\s*\(.*", "", s or "").lower().replace("&", " and ")
    s = re.sub(r"\bcx\b", "customer experience", s)
    s = re.sub(r"\bpm\b", "product manager", s)
    s = re.sub(r"\bsr\b\.?", "senior", s)
    s = re.sub(r"\bmgr\b\.?", "manager", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _contains(longer, shorter):
    return f" {shorter} " in f" {longer} "


def application_for(posting, applications, loose=False):
    """The application this posting corresponds to, or None: the same link first, then the same
    company with the same title once tidied. That is what joining a posting to an application, or
    marking it applied, goes by: "Manager" isn't "Engineering Manager".

    `loose` also takes one title inside the other when the shorter has three words or more
    ("Support Operations Manager" in "Senior Support Operations Manager, Americas"): enough to flag a
    new posting "you already applied here" for the user to judge, never to record anything."""
    url = (posting.get("url") or "").rstrip("/")
    for a in applications:
        if url and url in {u.rstrip("/") for u in a.get("urls", [])}:
            return a
    company, title = posting["company"].lower(), _norm_title(posting["title"])
    if not title:
        return None
    same = [a for a in applications if a.get("company", "").lower() == company]
    for a in same:
        if _norm_title(a.get("role", "")) == title:
            return a
    if loose:
        for a in same:
            role = _norm_title(a.get("role", ""))
            short, long_ = sorted((role, title), key=len)
            if role and len(short.split()) >= 3 and _contains(long_, short):
                return a
    return None


def pasted_match(company, title, postings):
    """The key of a posting the user pasted in by hand that is this same job (same company, same
    title once tidied), or None. A scan finding it again flags it rather than making a second copy."""
    c, t = (company or "").casefold(), _norm_title(title)
    for k, v in postings.items():
        if v.get("source") == "manual" and v.get("company", "").casefold() == c and t and _norm_title(v.get("title")) == t:
            return k
    return None
