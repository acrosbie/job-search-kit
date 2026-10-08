"""Adding one posting the user found themselves: a link they pasted, or the text of one.

Two routes, both ending in the record a scan would make, screened the same way:

- add_link: a link to a job board the engine already reads (Greenhouse, Lever, Ashby, SmartRecruiters,
  Workday, Rippling). The engine reads that board itself, so the text is exactly the posting's, and the
  key is the one a scan gives it, so a later scan finds it already saved.
- add_file: anything else (LinkedIn, a company's own site, an email). Claude reads the link, or the
  user pastes the text, into a file with the scan's header ('# Title', then '- Company:',
  '- Location:', '- URL:', '- Posted:', then '---' and the description). The engine names it
  manual-<company>-<short>, where short is the LinkedIn job id when the link has one.

Either way a duplicate is refused, naming the posting already saved. A posting the user chose is
never dropped on its title: a title outside their search is flagged instead. One abroad is rejected
with a reason rather than silently dropped, so they hear why.
"""

import os
import re

from . import scan, screen, settings, store, track
from .boards import READERS, Context, watched_names
from .errors import Refused

# (system, pattern capturing the board's token and the job id) for the boards the engine reads.
LINKS = (
    ("greenhouse", re.compile(r"(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/([A-Za-z0-9_-]+)/jobs/(\d+)", re.I)),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)/([0-9a-f]{8}-[0-9a-f-]{27})", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f]{8}-[0-9a-f-]{27})", re.I)),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)/(\d+)", re.I)),
    ("rippling", re.compile(r"ats\.rippling\.com/([A-Za-z0-9_-]+)/jobs/([0-9a-f]{8}-[0-9a-f-]{27})", re.I)),
)
# Workday job ids contain dashes (JR-0109564), so its postings are matched on the whole link instead.
WORKDAY = re.compile(r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)/job/", re.I)

# Where a job board's own id sits in a link that isn't one the engine reads.
_LINK_IDS = (
    re.compile(r"linkedin\.com/.*?(?:jobs/view/(?:[^/?#]*?-)?(\d{6,})|currentJobId=(\d{6,}))", re.I),
    re.compile(r"[?&](?:jk|gh_jid|jobId|job_id|jid)=([A-Za-z0-9-]{4,})", re.I),
    re.compile(r"/(\d{6,})(?:[/?#]|$)"),
)
_KEEP_QUERY = re.compile(r"(?:^|&)((?:currentJobId|jk|gh_jid|jobId|job_id|jid)=[^&]+)", re.I)


def _slug(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n].strip("-")


def link_id(url):
    for rx in _LINK_IDS:
        m = rx.search(url or "")
        if m:
            return next(g for g in m.groups() if g).lower()
    return ""


def norm_url(url):
    """A link reduced to what identifies the job: no scheme, www, language segment, tracking query
    or trailing slash. LinkedIn's many shapes for one job all become its job id."""
    url = (url or "").strip()
    if not url:
        return ""
    m = _LINK_IDS[0].search(url)
    if m:
        return "linkedin:" + next(g for g in m.groups() if g)
    url = re.sub(r"^https?://(www\.)?", "", url.split("#")[0], flags=re.I)
    path, _, query = url.partition("?")
    path = re.sub(r"/[a-z]{2}-[a-z]{2}(?=/)", "", path.lower(), count=1).rstrip("/")
    keep = "&".join(x.lower() for x in _KEEP_QUERY.findall(query))
    return path + ("?" + keep if keep else "")


def manual_key(company, url, title):
    return f"manual-{_slug(company, 30) or 'company'}-{link_id(url) or _slug(title) or 'job'}"


def duplicate(postings, url, company, title):
    """A saved posting that is this same job: the same link, or the same company and title while it
    is still on its board. None if there isn't one."""
    u = norm_url(url)
    if u:
        for k, v in postings.items():
            if norm_url(v.get("url")) == u:
                return k
    c, t = (company or "").casefold(), store._norm_title(title)
    for k, v in postings.items():
        if t and not v.get("gone") and v.get("company", "").casefold() == c and store._norm_title(v.get("title")) == t:
            return k
    return None


def _refuse_duplicate(postings, key):
    v = postings[key]
    status = {"new": "waiting to be gone through"}.get(v.get("status"), (v.get("status") or "").replace("_", " "))
    raise Refused(f"already saved as {key}: {v.get('company')}, {v.get('title')}, first seen "
                  f"{v.get('first_seen', '')} ({status})")


def _save(root, rec, desc, clock, text_from):
    s = settings.load(root)
    folder = store.Folder(root)
    state = folder.load_postings()
    keep, code = screen.location_ok(rec["location"], s)
    reject = None if keep else ("location_abroad", s.label("reason_abroad", location=screen.norm_loc(rec["location"])))
    extra = [] if screen.title_ok(rec["title"], s) else [("title", s.label("flag_title"))]
    entry, _ = scan.save_new(folder, rec, code, desc, s, folder.load_applications(), state["postings"],
                             clock.today(), clock.stamp(), reject=reject, extra_flags=extra)
    entry["text_from"] = text_from
    folder.save_postings(state)
    joined = track.link(root, clock, rec["key"])  # the user already said they applied to it
    if joined:
        entry = folder.load_postings()["postings"][rec["key"]]
    return {"saved": True, "key": rec["key"], **entry, "application": joined["id"] if joined else ""}


# ------------------------------------------------------------ a link to a board the engine reads

def parse_link(url):
    """(system, company entry fields, job id) for a link to a board the engine reads, or None.
    The job id is "" for Workday, whose postings are matched on the whole link."""
    m = WORKDAY.search(url or "")
    if m:
        tenant, wd, site = m.group(1).lower(), m.group(2).lower(), m.group(3)
        return "workday", {"host": f"{tenant}.{wd}.myworkdayjobs.com", "tenant": tenant, "site": site}, ""
    for system, rx in LINKS:
        m = rx.search(url or "")
        if m:
            return system, {"token": m.group(1)}, m.group(2)
    return None


def _board(companies, system, fields, name):
    """The watched company for this board, or a stand-in entry for one that isn't watched."""
    for c in companies:
        if c.get("ats") != system:
            continue
        if system == "workday":
            if c.get("host", "").lower() == fields["host"] and c.get("site", "").lower() == fields["site"].lower():
                return c, True
        elif c.get("token", "").lower() == fields["token"].lower():
            return c, True
    label = name or fields.get("tenant") or fields.get("token")
    return {"name": label, "slug": _slug(label) or "company", "ats": system, **fields}, False


def _same_job(rec, url, system, slug, jid):
    if jid:
        return rec["key"].lower().endswith(f"-{jid.lower()}")
    own_id = rec["key"][len(f"{system}-{_slug(slug, 200)}-"):].lower()
    target = norm_url(url)  # a Workday link ends <title>_<id>, sometimes with -1 after it
    return norm_url(rec["url"]) == target or bool(own_id and re.search(rf"_{re.escape(own_id)}(?:-\d+)?$", target))


def add_link(root, url, clock, company=""):
    """Read a pasted board link through the engine's own reader and save it as a scan would.
    Returns {"saved": False, "why": ...} when the link isn't one it reads, the board doesn't answer,
    or the job isn't on it; then Claude reads the link another way."""
    found = parse_link(url)
    if not found:
        return {"saved": False, "why": "not_a_board_link"}
    system, fields, jid = found
    s = settings.load(root)
    companies = settings.load_companies(root)
    board, watched = _board(companies, system, fields, company)
    try:
        recs = READERS[system](board, Context(workday=s.workday, watched=watched_names(companies)))
    except Exception as e:  # a board that doesn't answer is reported, never a traceback
        return {"saved": False, "why": "board_failed", "board": board["name"], "error": f"{type(e).__name__}: {e}"}
    rec = next((r for r in recs if _same_job(r, url, system, board["slug"], jid)), None)
    if rec is None:
        return {"saved": False, "why": "not_on_board", "board": board["name"]}

    postings = store.Folder(root).load_postings()["postings"]
    if rec["key"] in postings:
        _refuse_duplicate(postings, rec["key"])
    desc, place, posted, failed = scan.read_description(rec)
    if failed:  # the board listed it, but its page didn't answer: Claude reads the link another way
        return {"saved": False, "why": "board_failed", "board": board["name"], "error": failed}
    if place:
        rec["location"] = place
    if posted and not rec["posted"]:
        rec["posted"] = posted
    dup = duplicate(postings, rec["url"], rec["company"], rec["title"])
    if dup:
        _refuse_duplicate(postings, dup)
    return {**_save(root, rec, desc, clock, "board"), "watched": watched}


# ------------------------------------------------------------ a posting saved as text

def parse_file(text):
    """(title, fields, description) from a file in the scan's header format."""
    title = re.search(r"^# (.+)$", text, re.M)
    head, sep, body = text.partition("\n---")
    field = re.compile(r"^- (\w[\w ]*?): (.*)$", re.M)
    if sep:
        body = body.lstrip("-").strip()
    else:  # no '---' line: everything that isn't the title or a header line is the description
        head = text
        body = "\n".join(x for x in text.splitlines() if not (x.startswith("# ") or field.match(x))).strip()
    return (title.group(1).strip() if title else ""), dict(field.findall(head)), body


def add_file(root, path, clock, text_from="", anyway=False):
    folder = store.Folder(root)
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    title, fields, body = parse_file(text)
    company = fields.get("Company", "").strip()
    if not title or not company:
        raise Refused("header missing: need '# Title' and '- Company:' lines")
    url = fields.get("URL", "").strip()
    postings = folder.load_postings()["postings"]

    path = os.path.abspath(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    in_place = os.path.dirname(path) == os.path.abspath(folder.descriptions) and stem.startswith("manual-")
    key = stem if in_place else manual_key(company, url, title)  # a file already named as a key keeps its name
    if not anyway:
        if key in postings:
            _refuse_duplicate(postings, key)
        dup = duplicate(postings, url, company, title)
        if dup:
            _refuse_duplicate(postings, dup)
    n, base = 2, key
    while key in postings:  # the user says it's a different job with the same name
        key, n = f"{base}-{n}", n + 1

    rec = {"key": key, "ats": "manual", "company": company, "title": title,
           "location": fields.get("Location", "").replace("(not stated)", "").strip(), "url": url,
           "posted": fields.get("Posted", "").replace("(unknown)", "").strip(), "description": body, "detail": None}
    return _save(root, rec, body, clock, text_from or "pasted")
