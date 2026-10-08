"""Testing title patterns on real titles, without fetching anything.

Every scan saves every title it read to data/titles-latest.tsv. `summary` shows what the current
settings keep and what they nearly kept; `try_patterns` shows what a change would gain and lose.
Setup uses both to calibrate a new user's titles in seconds, and the weekly review uses `summary`
to catch good titles the filter is dropping.
"""

import os
import random
import re

from . import screen, settings


def read_titles(folder):
    path = os.path.join(folder, "data", "titles-latest.tsv")
    if not os.path.exists(path):
        raise FileNotFoundError(2, "no scan has saved its titles yet: run a scan first", path)
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        next(f, None)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3 and parts[1]:
                rows.append((parts[0], parts[1], parts[2]))
    return rows


def _has(rx, s):
    return bool(rx and rx.search(s))


def is_near_miss(title, s):
    """Dropped, but close: it carries a field word, or the function words but not the level, or it
    passed both and an exclusion took it out."""
    if screen.title_ok(title, s):
        return False
    if _has(s.field_words, title):
        return True
    return _has(s.function, title) and (not _has(s.level, title) or _has(s.exclude, title))


def _distinct(rows):
    """One entry per title, with how many times it appeared and one board and place it came from."""
    seen = {}
    for board, title, loc in rows:
        k = re.sub(r"\s+", " ", title.strip().lower())
        if k in seen:
            seen[k]["count"] += 1
        else:
            seen[k] = {"title": title.strip(), "board": board, "location": loc, "count": 1}
    return list(seen.values())


def _sample(items, n, seed):
    items = sorted(items, key=lambda x: x["title"].lower())
    random.Random(seed).shuffle(items)
    return items[:n]


def classify(rows, s):
    """(kept, near) rows. Both only where the place would pass, since a title in a place the user
    would never take isn't worth asking them about."""
    kept, near = [], []
    for board, title, loc in rows:
        if not screen.location_ok(loc, s)[0]:
            continue
        if screen.title_ok(title, s):
            kept.append((board, title, loc))
        elif is_near_miss(title, s):
            near.append((board, title, loc))
    return kept, near


def summary(folder, sample=10, seed=1):
    s = settings.load(folder)
    rows = read_titles(folder)
    kept, near = classify(rows, s)
    k, n = _distinct(kept), _distinct(near)
    return {"titles_read": len(rows), "kept": len(kept), "kept_distinct": len(k),
            "near_misses": len(near), "near_distinct": len(n),
            "kept_sample": _sample(k, sample, seed), "near_sample": _sample(n, sample, seed)}


def try_patterns(folder, function=None, level=None, exclude=None, field_words=None, sample=10, seed=1):
    """What keeping titles with these patterns would change, compared with the current settings."""
    current = settings.load(folder)
    raw = dict(current.raw)
    t = dict(raw.get("titles", {}))
    for key, v in (("function", function), ("level", level), ("exclude", exclude), ("field_words", field_words)):
        if v is not None:
            re.compile(v, re.I)  # a broken pattern fails here, before anything is compared
            t[key] = v
    raw["titles"] = t
    candidate = settings.parse(raw)
    rows = read_titles(folder)
    now, _ = classify(rows, current)
    then, near = classify(rows, candidate)
    now_set, then_set = set(now), set(then)
    gained = [r for r in then if r not in now_set]
    lost = [r for r in now if r not in then_set]
    return {"titles_read": len(rows), "kept_now": len(now), "kept_with_change": len(then),
            "gained": len(gained), "lost": len(lost),
            "gained_sample": _sample(_distinct(gained), sample, seed),
            "lost_sample": _sample(_distinct(lost), sample, seed),
            "near_misses_with_change": len(near)}
