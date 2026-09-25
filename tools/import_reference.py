#!/usr/bin/env python3
"""
Convert the reference scanner's files into job-search-kit's formats. A development tool, not
part of the kit: it exists to prove the engine matches the scanner it was ported from, and to
move that scanner's one user onto the kit.

    python tools/import_reference.py --config config.toml --watchlist watchlist.toml \
        [--pipeline pipeline.md] [--labels labels.json] [--timezone Area/City] --out <folder>

Writes <folder>/profile/settings.toml, <folder>/profile/companies.toml and
<folder>/data/applications.json. It refuses to write inside this repository, because the result
is one person's data.

--labels is a JSON file of settings.toml [labels] wording (flag_in_country, reason_pay, ...), for
reproducing the reference scanner's exact flag and reason text. Without it the kit's plain
defaults are used.
"""

import argparse
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "plugins", "job-search", "engine"))
sys.dont_write_bytecode = True

from jobkit.toml import load_file  # noqa: E402

# Reference config.toml [location] keys -> settings.toml [places] keys.
PLACES = {"remote": "remote", "bay_core": "hybrid_ok", "bay_outer": "remote_only",
          "us": "in_country", "us_national": "country_wide", "drop": "abroad"}


def toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{json.dumps(k)} = {toml_value(x)}" for k, x in v.items()) + " }"
    return json.dumps(v, ensure_ascii=False)  # JSON strings and string lists are valid TOML


def settings_toml(config, labels, timezone):
    t, loc = config.get("titles", {}), config.get("location", {})
    out = ["# Converted from the reference scanner's config.toml by tools/import_reference.py.", ""]
    out += ["[you]", f"timezone = {toml_value(timezone)}", ""]
    out += ["[titles]"] + [f"{k} = {toml_value(t[k])}" for k in ("function", "level", "exclude") if k in t] + [""]
    out += ["[places]"] + [f"{new} = {toml_value(loc[old])}" for old, new in PLACES.items() if old in loc] + [""]
    desc = {"remote_language": loc.get("remote_language"), "contract": t.get("contract"),
            "onsite_days": loc.get("onsite_days"), "onsite_place": loc.get("onsite_place")}
    out += ["[description]"] + [f"{k} = {toml_value(v)}" for k, v in desc.items() if v] + [""]
    if t.get("renewals"):
        # The reference counts two distinct phrases, with "net revenue retention" and "NRR" as one.
        out += ["[[phrase_rejects]]", 'name = "renewals"', f"phrases = {toml_value(t['renewals'])}", "min_distinct = 2",
                'same_as = { "net revenue retention" = "nrr" }']
        if labels.get("reason_renewals"):
            out.append(f"reason = {toml_value(labels['reason_renewals'])}")
        out.append("")
    out += ["[pay]", f"reject_if_top_below = {int((config.get('pay') or {}).get('reject_if_top_below', 0))}", ""]
    wd = config.get("workday", {})
    out += ["[workday]", f"country_facet = {toml_value(wd.get('country_facet', ''))}",
            f"max_total = {int(wd.get('max_total', 2000))}", ""]
    kit_labels = {k: v for k, v in labels.items() if k != "reason_renewals"}
    if kit_labels:
        out += ["[labels]"] + [f"{k} = {toml_value(v)}" for k, v in kit_labels.items()] + [""]
    return "\n".join(out)


def companies_toml(watchlist):
    out = ["# Converted from the reference scanner's watchlist.toml by tools/import_reference.py.", ""]
    for c in watchlist.get("company", []):
        out.append("[[company]]")
        out += [f"{k} = {toml_value(v)}" for k, v in c.items()]
        out.append("")
    return "\n".join(out)


_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_LINK_URLS = re.compile(r"\]\((https?://[^)]+)\)")


def applications(pipeline_text):
    """Rows of the first table under '## Applied', in the reference tracker's 8- or 9-column shape:
    Company | Role | Fit | Level | Pay | Applied | (Followed up) | Status | Note."""
    m = re.search(r"^## Applied\s*$(.*?)^## ", pipeline_text, re.M | re.S)
    if not m:
        return []
    rows = []
    for line in m.group(1).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) not in (8, 9) or cells[0] == "Company" or set(cells[0]) <= {"-"}:
            continue
        if len(cells) == 8:
            cells.insert(6, "")
        company, role, fit, level, pay, applied, followed, status, note = cells
        rows.append({
            "company": company,
            "role": _LINK.sub(r"\1", role).strip(),
            "urls": _LINK_URLS.findall(role),
            "fit": fit, "level": level, "posted_pay": pay,
            "applied": applied,
            "applied_date": applied if re.fullmatch(r"\d{4}-\d{2}-\d{2}", applied) else "",
            "followed_up": followed, "status": status, "note": note,
        })
    return rows


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--config", required=True)
    p.add_argument("--watchlist", required=True)
    p.add_argument("--pipeline")
    p.add_argument("--labels")
    p.add_argument("--timezone", default="")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    out = os.path.abspath(a.out)
    if os.path.commonpath([out, REPO]) == REPO:
        print("refusing to write inside the repository: the result is personal data", file=sys.stderr)
        return 3
    labels = {}
    if a.labels:
        with open(a.labels, encoding="utf-8") as f:
            labels = json.load(f)
    os.makedirs(os.path.join(out, "profile"), exist_ok=True)
    os.makedirs(os.path.join(out, "data"), exist_ok=True)
    with open(os.path.join(out, "profile", "settings.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(settings_toml(load_file(a.config), labels, a.timezone))
    with open(os.path.join(out, "profile", "companies.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(companies_toml(load_file(a.watchlist)))
    apps = []
    if a.pipeline:
        with open(a.pipeline, encoding="utf-8") as f:
            apps = applications(f.read())
    with open(os.path.join(out, "data", "applications.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"applications": apps}, f, indent=1, ensure_ascii=False)
    print(f"wrote settings, {len(load_file(a.watchlist).get('company', []))} companies and {len(apps)} applications to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
