"""The user's resume, made only from what they have confirmed.

Claude writes a resume as a plain source file in the user's folder, under resume/. Every line
that says something about the user carries `from:` lines: words copied exactly from
profile/about-me.md. This module checks each line against about-me.md. A line must trace to a
confirmed claim. It must not bring back a corrected claim, use an unconfirmed one, claim as owned
what the user worked alongside, or carry a number its sources don't have. Only a resume that traces
is made into a Word file and a PDF (docx.py, pdf.py).

The source format (reference/resume-format.md in the plugin):

    # First Last                        the name; anything after a comma (", CPA") is a claim
    City · email · phone                contact lines, up to the first section; not claims
    ## Experience                       a section heading
    ### Title | Company, Place | Dates  a job: a claim
    - A bullet                          a claim
    A line of text                      a claim (a summary, a degree, a list of tools)
      from: <words from about-me.md>    a source for the claim above; one or more
      flag: <kind>: <plain words>       Claude's own finding, when checking the user's own resume

The engine checks what can be checked by rule. Claude still reads each line for wording that widens
its source ("led the audit" where about-me.md says "prepared the schedules"), and says so with a
`flag:` line.
"""

import os
import re

from .errors import BadFile

ABOUT = os.path.join("profile", "about-me.md")

# The sections of about-me.md (reference/profile-format.md), by how their heading starts.
SECTIONS = (("confirmed", "confirmed"), ("corrected", "corrected"), ("not confirmed", "unconfirmed"),
            ("owned hands-on", "owned"), ("facts postings check", "facts"), ("how to present", "present"))

# What a line may rest on. "alongside" may be cited, but never as something the user owned.
ALLOWED = ("confirmed", "now", "owned", "facts", "alongside")

CLAIMS = ("credential", "job", "bullet", "para")

# A line that starts with one of these claims the user owned or led what it describes.
OWNING = {"owned", "own", "owns", "led", "lead", "leads", "built", "build", "builds", "ran", "run", "runs",
          "managed", "manage", "manages", "designed", "design", "designs", "created", "developed",
          "drove", "directed", "headed", "spearheaded", "architected", "launched", "implemented",
          "established", "founded", "oversaw", "oversee", "oversees"}

# "one" is left out: it's far more often a pronoun ("one of", "no one") than a count.
NUMBER_WORDS = {w: str(n) for n, w in enumerate(
    "zero _ two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split()) if w != "_"}
NUMBER_WORDS.update({"thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
                     "eighty": "80", "ninety": "90", "hundred": "100"})

MIN_WORDS = 3  # a source quotes at least this many words, or a whole entry

_PLAIN = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
                        "—": "-", "‑": "-", "−": "-", " ": " ", "*": None, "`": None})


def norm(s):
    """Text as compared: one case, plain quotes and dashes, no markdown emphasis, single spaces."""
    return re.sub(r"\s+", " ", (s or "").translate(_PLAIN)).strip().casefold()


def numbers(s):
    """The numbers a text states: digits ("10", "95,000", "1.5", "$250K" is 250) and number words."""
    s = norm(s)
    for word, digits in NUMBER_WORDS.items():
        s = re.sub(rf"\b{word}\b", digits, s)
    found = set()
    for m in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", s):
        found.add(m.replace(",", "").lstrip("0") or "0")
    return found


def _phrase(p):
    """A regular expression for a phrase, as whole words where it starts or ends with one."""
    start = r"\b" if re.match(r"\w", p) else ""
    end = r"\b" if re.search(r"\w$", p) else ""
    return re.compile(start + re.escape(p) + end)


# ------------------------------------------------------------------ about-me.md


class Entry:
    """One claim in about-me.md: its kind (confirmed, was, now, unconfirmed, owned, alongside,
    facts) and its text."""

    def __init__(self, kind, text):
        self.kind = kind
        self.text = text.strip()
        self.norm = norm(text)

    def __repr__(self):
        return f"Entry({self.kind!r}, {self.text!r})"


def _cells(line):
    parts = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [p.replace("\\|", "|").strip() for p in parts]


def parse_about(text):
    """Every claim in about-me.md, as Entry objects. Tables skip their header row; "How to present
    me" is advice built from the claims, so it isn't a source of its own."""
    entries = []
    section, header_done = None, False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            title = s[3:].strip().casefold()
            section = next((kind for start, kind in SECTIONS if title.startswith(start)), None)
            header_done = False
            continue
        if not s or section in (None, "present"):
            continue
        if s.startswith("|"):
            cells = _cells(s)
            if all(re.fullmatch(r":?-+:?", c.replace(" ", "")) for c in cells if c):
                continue  # the line under a table's header
            if not header_done:
                header_done = True
                continue
            first = cells[0] if cells else ""
            second = cells[1] if len(cells) > 1 else ""
            pairs = {"confirmed": [("confirmed", first)],
                     "corrected": [("was", first), ("now", second)],
                     "owned": [("owned", first), ("alongside", second)],
                     "unconfirmed": [("unconfirmed", " ".join(cells))],
                     "facts": [("facts", " ".join(cells))]}[section]
            entries += [Entry(kind, t) for kind, t in pairs if t]
        elif s.startswith(("- ", "* ")):
            kind = {"owned": "owned", "corrected": "now"}.get(section, section)
            entries.append(Entry(kind, s[2:]))
    return entries


def read_about(root):
    with open(os.path.join(root, ABOUT), encoding="utf-8") as f:
        return parse_about(f.read())


def was_phrases(entries):
    """The words a correction replaced, as they'd appear in a resume: the quoted part of each "Was"
    ("Senior Accounting Manager" from '"Senior Accounting Manager" (LinkedIn)'), or the whole of it
    without anything in brackets."""
    out = []
    for e in entries:
        if e.kind != "was":
            continue
        plain = e.text.translate(_PLAIN)
        for p in re.findall(r'"([^"]+)"', plain) or [re.sub(r"\(.*?\)", "", plain)]:
            p = norm(p)
            if len(p) >= 3:
                out.append(p)
    return out


# ------------------------------------------------------------------ the resume source


def parse_source(text):
    """The resume's lines, in order: dicts with `kind` (name, credential, contact, heading, job,
    bullet, para), `text`, `section`, `line`, and for claims `from` and `flags`."""
    items, section, name_seen = [], "", False

    def add(kind, body, n):
        items.append({"kind": kind, "text": body.strip(), "section": section, "line": n, "from": [], "flags": []})

    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        low = s.casefold()
        if low.startswith(("from:", "flag:")):
            if not items or items[-1]["kind"] not in CLAIMS:
                raise BadFile(f"line {n}: a {low[:5]} line must come right under the line it is about")
            body = s[5:].strip()
            if low.startswith("from:"):
                items[-1]["from"].append(body)
            else:
                kind, _, detail = body.partition(":")
                items[-1]["flags"].append({"kind": kind.strip() or "claude", "detail": (detail or kind).strip(),
                                           "by": "claude"})
            continue
        if not name_seen:
            if not s.startswith("# "):
                raise BadFile(f"line {n}: a resume starts with the name, as '# First Last'")
            name, _, credential = s[2:].partition(",")
            add("name", name, n)
            if credential.strip():
                add("credential", credential, n)
            name_seen = True
        elif s.startswith("### "):
            add("job", s[4:], n)
        elif s.startswith("## "):
            section = s[3:].strip()
            add("heading", section, n)
        elif not section:
            add("contact", s, n)
        elif s.startswith(("- ", "* ", "• ")):
            add("bullet", s[2:], n)
        else:
            add("para", s, n)
    if not name_seen:
        raise BadFile("the resume is empty: it starts with the name, as '# First Last'")
    return items


def check_items(items, entries):
    """Fill in each claim's `problems` and `ok`. A problem is {"kind", "detail"}: the kinds are
    no_source, source_not_found, too_short, unconfirmed, corrected, alongside_as_owned and number,
    plus whatever Claude flagged."""
    was = was_phrases(entries)
    for it in items:
        if it["kind"] not in CLAIMS:
            continue
        problems = list(it["flags"])
        if not it["from"] and not problems:
            problems.append({"kind": "no_source", "detail": "nothing in about-me.md says this"})
        rests_on, alongside = [], False
        for frag in it["from"]:
            f = norm(frag)
            hits = [e for e in entries if f and f in e.norm]
            usable = [e for e in hits if e.kind in ALLOWED]
            if not hits:
                problems.append({"kind": "source_not_found", "detail": f'"{frag}" isn\'t in about-me.md'})
            elif not usable:
                if any(e.kind == "unconfirmed" for e in hits):
                    problems.append({"kind": "unconfirmed", "detail": f'"{frag}" is under "Not confirmed yet"'})
                else:
                    problems.append({"kind": "corrected",
                                     "detail": f'"{frag}" is what was corrected; use what it was corrected to'})
            elif len(f.split()) < MIN_WORDS and not any(f == e.norm for e in usable):
                problems.append({"kind": "too_short",
                                 "detail": f'"{frag}" is too short to show which claim it is; quote more of it'})
            else:
                rests_on += usable
                alongside |= any(e.kind == "alongside" or "alongside" in e.norm for e in usable)
        body = norm(it["text"])
        if rests_on:
            first = re.sub(r"^\W+", "", body).split(" ", 1)[0]
            if alongside and first in OWNING:
                problems.append({"kind": "alongside_as_owned",
                                 "detail": f'about-me.md says they worked alongside this; "{first}" says they owned it'})
            have = set().union(*(numbers(e.text) for e in rests_on))
            missing = sorted(numbers(it["text"]) - have, key=lambda x: float(x))
            if missing:
                problems.append({"kind": "number",
                                 "detail": f"{', '.join(missing)} isn't in what this line rests on"})
        for p in was:
            if _phrase(p).search(body) and not any(_phrase(p).search(e.norm) for e in rests_on):
                problems.append({"kind": "corrected", "detail": f'"{p}" was corrected in about-me.md'})
        it["problems"] = problems
        it["ok"] = not problems
    return items


def _job(text):
    """A job heading's title, place and dates: "Title | Company, Place | Dates". With two parts, the
    second is the dates if it has a digit or says "present"."""
    parts = [p.strip() for p in text.split("|")]
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        dated = re.search(r"\d|present|current", parts[1], re.I)
        return (parts[0], "", parts[1]) if dated else (parts[0], parts[1], "")
    return parts[0], " | ".join(parts[1:-1]), parts[-1]


def blocks(items):
    """The resume as the Word and PDF makers lay it out (docx.py): the name (with a traced
    credential), contact lines, headings, jobs, bullets and lines of text."""
    out = []
    for it in items:
        if it["kind"] == "credential":
            out[0] = ("name", f"{out[0][1]}, {it['text']}")
        elif it["kind"] == "job":
            out.append(("job",) + _job(it["text"]))
        else:
            out.append((it["kind"], it["text"]))
    return out


def check_text(text, entries):
    """The whole check, as a summary for Claude: each line, what it rests on, and its problems."""
    items = check_items(parse_source(text), entries)
    claims = [it for it in items if it["kind"] in CLAIMS]
    kinds = {}
    for it in claims:
        for p in it["problems"]:
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    name = next(it["text"] for it in items if it["kind"] == "name")
    return {"name": name, "lines": len(claims), "traced": sum(it["ok"] for it in claims),
            "flagged": sum(not it["ok"] for it in claims), "problems": kinds, "items": items}
