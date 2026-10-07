"""Recording the choices the user made on the jobs page.

Claude gathers the clicks, from the page's own storage or from the "Copy my choices" text pasted into
chat, into a JSON list and runs `record-choices FILE`. Each choice is the user's own decision, so it
is recorded with by=user, exactly as if they had said it in chat:

    want, skip                    a verdict on a posting (worth applying, skipped)
    applied                       track.apply, with how they applied and whether it's a top pick
    followed_up, replied, screen, interview, offer, rejected, withdrawn, contact
                                  track.track on an application

Every choice carries an id, kept on what it recorded, so the same click is never recorded twice.
Choices are taken oldest first, and one is skipped as superseded when the user changed it: a later
click on the same job, or a later decision in chat. Only their last word is recorded, so changing
their mind on the page never reads as overturning a verdict several times.

Whatever happens to a click is also written to data/choices.log (recorded, already, superseded, or
unknown with the reason), once per click. The page reads the recent ones back (page.json `handled`),
so a page opened from the folder can drop the clicks Claude has dealt with and keep the rest.
"""

import datetime as dt
import json

from . import store, track, verdicts
from .errors import NotFound, Refused

POSTING_ACTIONS = {"want": "worth_applying", "skip": "skipped", "applied": "applied"}
APP_ACTIONS = ("followed_up", "replied", "screen", "interview", "offer", "rejected", "withdrawn", "contact")
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def _when(s):
    try:
        t = dt.datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return _EPOCH
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def recorded_ids(root):
    ids = {d["choice"] for d in store.Folder(root).read_decisions() if d.get("choice")}
    for a in track.load(root):
        ids |= {h["choice"] for h in a.get("history", []) if h.get("choice")}
    return ids


def _later_in_chat(root, c):
    """True when the user decided the same thing after this click."""
    at = _when(c.get("at"))
    if c.get("action") in POSTING_ACTIONS:
        last = verdicts.last_user_decision(store.Folder(root).read_decisions(), c.get("key"))
        return bool(last and _when(last.get("at")) > at)
    if c.get("action") in ("followed_up", "contact"):
        return False  # a dated event or a name: nothing to overrule
    a = track.find(track.load(root), c.get("app", ""))
    later = [h for h in (a or {}).get("history", []) if h.get("status") and h.get("by") == "user" and _when(h.get("at")) > at]
    return bool(later)


def _changed_on_the_page(choices, done):
    """Ids of clicks the user replaced with a later click on the same job before Claude recorded
    either: only their last word on a job counts. Follow-ups and contacts are kept, every one."""
    last = {}
    for c in sorted(choices, key=lambda c: _when(c.get("at"))):
        if c.get("id") in done:
            continue
        if c.get("action") in POSTING_ACTIONS:
            slot = ("job", c.get("key"))
        elif c.get("action") in APP_ACTIONS and c.get("action") not in ("followed_up", "contact"):
            slot = ("application", c.get("app"))
        else:
            continue
        last[slot] = c.get("id")
    keep = set(last.values())
    return {c.get("id") for c in choices if c.get("id") not in done and c.get("id") not in keep
            and (c.get("action") in POSTING_ACTIONS
                 or (c.get("action") in APP_ACTIONS and c.get("action") not in ("followed_up", "contact")))}


def record(root, clock, choices):
    """Record a list of page choices. Returns what happened to each, in four lists."""
    out = {"recorded": [], "already": [], "superseded": [], "unknown": []}
    done = recorded_ids(root)
    replaced = _changed_on_the_page(choices, done)
    folder = store.Folder(root)
    logged = {(r.get("id"), r.get("outcome")) for r in folder.read_choices()}
    for c in sorted(choices, key=lambda c: _when(c.get("at"))):
        cid, action = c.get("id", ""), c.get("action", "")
        brief = {"id": cid, "action": action, "num": c.get("num"), "label": c.get("label", ""),
                 "key": c.get("key", ""), "app": c.get("app", "")}
        if not cid or (action not in POSTING_ACTIONS and action not in APP_ACTIONS):
            out["unknown"].append({**brief, "why": "not a choice the page makes"})
            continue
        if cid in done:
            out["already"].append(brief)
            continue
        if cid in replaced:
            out["superseded"].append({**brief, "why": "changed on the page"})
            continue
        # Recorded as of when the user clicked, in their own time zone: that is when they decided.
        clicked = min(_when(c.get("at")), clock.now()).astimezone(clock.now().tzinfo)
        at, day = clicked.isoformat(timespec="seconds"), clicked.date().isoformat()
        try:
            if _later_in_chat(root, c):
                out["superseded"].append(brief)
                continue
            note = (c.get("note") or "").strip()
            if action == "applied":
                top = {"yes": True, "no": False}.get(c.get("top_pick") or "")
                track.apply(root, clock, key=c.get("key", ""), date=day, channel=c.get("channel") or "", top_pick=top,
                            contact=c.get("contact") or "", note=note, choice=cid, at=at)
            elif action in POSTING_ACTIONS:
                verdicts.mark(root, c.get("key", ""), POSTING_ACTIONS[action], "user", note=note, clock=clock,
                              choice=cid, at=at)
            elif action == "contact":
                track.track(root, clock, c.get("app", ""), note=note, contact=c.get("contact") or "", choice=cid, at=at)
            else:
                track.track(root, clock, c.get("app", ""), action, date=day, note=note,
                            contact=(c.get("contact") or None), choice=cid, at=at)
        except (NotFound, Refused) as e:
            out["unknown"].append({**brief, "why": str(e)})
            continue
        done.add(cid)
        out["recorded"].append(brief)
    for outcome in ("recorded", "already", "superseded", "unknown"):
        for c in out[outcome]:
            if c["id"] and (c["id"], outcome) not in logged:
                logged.add((c["id"], outcome))
                folder.log_choice({"at": clock.stamp(), "id": c["id"], "outcome": outcome, "why": c.get("why", "")})
    return out


def handled(root, clock, days=30):
    """{click id: {"outcome", "why"}} for the clicks dealt with in the last `days` days: what the page
    needs to drop the ones Claude has recorded and show the ones it couldn't."""
    since = (clock.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    out = {}
    for r in store.Folder(root).read_choices():
        if r.get("id") and (r.get("at") or "") >= since[:10]:
            out[r["id"]] = {"outcome": r.get("outcome", ""), "why": r.get("why", "")}
    return out


def record_file(root, clock, path):
    """The same, from a file: a JSON list of choices, or {"choices": [...]}, or the text the page's
    "Copy my choices" button makes, with its [choices: ...] block."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    start = text.find("[choices:")
    if start >= 0:
        text = text[start + len("[choices:"):text.rindex("]")]
    data = json.loads(text)
    return record(root, clock, data["choices"] if isinstance(data, dict) else data)
