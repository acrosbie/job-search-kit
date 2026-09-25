"""The records in the user's folder, and the only code that writes them.

    data/postings.json        every matched posting and its status, plus each board's health
    data/postings.backup.json the previous postings.json, rewritten before every save
    data/postings/<key>.md    one saved description per posting
    data/applications.json    every application (read here only for the "already applied" flag)
    data/decisions.log        every verdict, by rule, Claude or the user; one JSON object a line, append-only
    data/runs.log             one JSON object per scan, append-only
    data/titles-latest.tsv    every title read on the last scan, for testing a title change on real data

Nothing here deletes a file. Cowork's workspace on the user's computer isn't allowed to, and
replacing a file by renaming over it may count as deleting. Files are written in place, after the
new content is complete, with the previous postings.json kept as a backup.
"""

import json
import os
import re

STATUSES = ("new", "worth_applying", "your_call", "not_a_fit", "skipped", "applied")


class Folder:
    def __init__(self, root):
        self.root = root
        self.data = os.path.join(root, "data")
        self.postings_json = os.path.join(self.data, "postings.json")
        self.backup_json = os.path.join(self.data, "postings.backup.json")
        self.descriptions = os.path.join(self.data, "postings")
        self.applications_json = os.path.join(self.data, "applications.json")
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

    # ------------------------------------------------------------ postings

    def load_postings(self):
        if os.path.exists(self.postings_json):
            state = json.loads(self._read(self.postings_json))
            state.setdefault("postings", {})
            state.setdefault("boards", {})
            return state
        return {"postings": {}, "boards": {}}

    def save_postings(self, state):
        text = json.dumps(state, indent=1, ensure_ascii=False)
        if os.path.exists(self.postings_json):
            self._write(self.backup_json, self._read(self.postings_json))
        self._write(self.postings_json, text)

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

    def write_titles(self, rows):
        """rows: (board, title, location) for every posting read this scan."""
        out = ["source\ttitle\tlocation"]
        for board, title, loc in rows:
            out.append(f"{board}\t{(title or '').replace(chr(9), ' ')}\t{(loc or '').replace(chr(9), ' ')}")
        self._write(self.titles_tsv, "\n".join(out) + "\n")

    # ------------------------------------------------------------ applications

    def load_applications(self):
        if not os.path.exists(self.applications_json):
            return []
        return json.loads(self._read(self.applications_json)).get("applications", [])


def _norm_title(s):
    """Loose title key for matching a posting to an application: anything from the first
    parenthesis off, & to and, CX and PM spelled out, punctuation collapsed."""
    s = re.sub(r"\s*\(.*", "", s or "").lower().replace("&", " and ")
    s = re.sub(r"\bcx\b", "customer experience", s)
    s = re.sub(r"\bpm\b", "product manager", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def application_for(posting, applications):
    """The application this posting corresponds to, or None: the same link first, then the same
    company with a matching title. Anything looser is for Claude to judge, not the engine."""
    url = (posting.get("url") or "").rstrip("/")
    for a in applications:
        if url and url in {u.rstrip("/") for u in a.get("urls", [])}:
            return a
    company, title = posting["company"].lower(), _norm_title(posting["title"])
    for a in applications:
        role = _norm_title(a.get("role", ""))
        if a.get("company", "").lower() == company and title and role and (title == role or title in role or role in title):
            return a
    return None
