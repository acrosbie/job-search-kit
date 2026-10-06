"""Recording the choices the user made on the jobs page.

Claude gathers the clicks, from the page's own storage or from the "Copy my choices" text pasted into
chat, into a JSON list and runs `record-choices FILE`. Each choice is the user's own decision, so it
is recorded with by=user, exactly as if they had said it in chat:

    want, skip                    a verdict on a posting (worth applying, skipped)
    applied                       track.apply, with how they applied and whether it's a top pick
    followed_up, replied, screen, interview, offer, rejected, withdrawn, contact
                                  track.track on an application

Every choice carries an id, kept on what it recorded, so the same click is never recorded twice.
Choices are taken oldest first, and one is skipped as superseded when the user decided the same
thing later in chat: their latest word stands.
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


def record(root, clock, choices):
    """Record a list of page choices. Returns what happened to each, in four lists."""
    out = {"recorded": [], "already": [], "superseded": [], "unknown": []}
    done = recorded_ids(root)
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
