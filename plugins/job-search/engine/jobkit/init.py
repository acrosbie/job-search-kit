"""Starting a new user's folder from the starter data (engine/starter/), which travels with the engine.

    profile/settings.toml   defaults + a places pack + a field pack (or empty title patterns for a
                            field setup will build), and the user's time zone
    profile/companies.toml  the starter boards, plus an aggregator entry when the field pack has queries
    data/applications.json  empty

It never touches a folder that already has a profile: setup changes an existing profile through the
settings and companies commands instead.
"""

import json
import os

from . import settings, tomlwrite
from .toml import load_file

STARTER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "starter")
HEADER = ("# Your job-search settings. Claude changes this file for you, through the engine, after telling you\n"
          "# what will change; there's no need to open it.")
COMPANIES_HEADER = ("# The job boards your scans read. Ask Claude to add a company you're interested in, or to\n"
                    "# drop one; it checks a company's board answers before adding it.")


class AlreadySetUp(Exception):
    pass


def available():
    fields = sorted(f[:-5] for f in os.listdir(os.path.join(STARTER, "fields")) if f.endswith(".toml"))
    places = sorted(f[:-5] for f in os.listdir(os.path.join(STARTER, "places")) if f.endswith(".toml"))
    return {"fields": fields + ["custom"], "places": places}


def _merge(base, extra):
    for section, values in extra.items():
        if isinstance(values, dict):
            base.setdefault(section, {}).update(values)
        else:
            base[section] = values
    return base


def init(folder, field="custom", places="us", timezone=""):
    profile = os.path.join(folder, "profile")
    existing = [n for n in ("settings.toml", "companies.toml") if os.path.exists(os.path.join(profile, n))]
    if existing:
        raise AlreadySetUp(f"this folder already has {', '.join(existing)}; nothing was changed")
    opts = available()
    if field not in opts["fields"]:
        raise ValueError(f"unknown field pack {field!r}; one of {', '.join(opts['fields'])}")
    if places not in opts["places"]:
        raise ValueError(f"unknown places pack {places!r}; one of {', '.join(opts['places'])}")

    raw = {"you": {"timezone": timezone}}
    _merge(raw, load_file(os.path.join(STARTER, "defaults.toml")))
    _merge(raw, load_file(os.path.join(STARTER, "places", f"{places}.toml")))
    queries = []
    if field == "custom":
        raw["titles"] = {"function": "", "level": "", "exclude": "", "field_words": ""}
    else:
        pack = load_file(os.path.join(STARTER, "fields", f"{field}.toml"))
        queries = pack.pop("aggregator", {}).get("queries", [])
        _merge(raw, pack)
    settings.parse(raw)  # the starting file must load

    boards = load_file(os.path.join(STARTER, "boards.toml"))["company"]
    if queries:
        boards = boards + [{"name": "Himalayas", "slug": "himalayas", "ats": "himalayas", "queries": queries}]

    os.makedirs(profile, exist_ok=True)
    os.makedirs(os.path.join(folder, "data"), exist_ok=True)
    with open(os.path.join(profile, "settings.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(tomlwrite.settings_text(raw, HEADER))
    with open(os.path.join(profile, "companies.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(tomlwrite.companies_text(boards, COMPANIES_HEADER))
    apps = os.path.join(folder, "data", "applications.json")
    if not os.path.exists(apps):
        with open(apps, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"applications": []}, f)
    return {"field": field, "places": places, "boards": len(boards), "timezone": timezone,
            "titles_set": field != "custom"}
