#!/usr/bin/env python3
"""
Convert the reference scanner's files into job-search-kit's formats. A development tool, not
part of the kit: it exists to prove the engine matches the scanner it was ported from, and to
move that scanner's one user onto the kit.

    python tools/import_reference.py --config config.toml --watchlist watchlist.toml \
        [--pipeline pipeline.md] [--relative-dates dates.json] [--labels labels.json] \
        [--seen seen.json --postings-dir postings/] [--triage-log triage-log.md] \
        [--timezone Area/City] --out <folder>

Writes <folder>/profile/settings.toml, <folder>/profile/companies.toml and
<folder>/data/applications.json; with --seen, also data/postings.json and the saved descriptions;
with --triage-log, also data/decisions.log. It refuses to write inside this repository, because
the result is one person's data.

--relative-dates maps the tracker's relative application dates ("1w") to the date each meant,
as a JSON object. Without it those applications keep an unknown date.

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


def applied_date(cell, relative):
    """(ISO date, estimated): a date written in the cell, or a relative label mapped through `relative`."""
    cell = re.sub(r"[*`]", "", cell or "").strip()
    m = re.search(r"\d{4}-\d{2}-\d{2}", cell)
    if m:
        return m.group(0), False
    if cell in relative:
        return relative[cell], True
    return "", False


def applications(pipeline_text, relative=None):
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
        when, estimated = applied_date(applied, relative or {})
        rows.append({
            "company": company,
            "role": _LINK.sub(r"\1", role).strip(),
            "urls": _LINK_URLS.findall(role),
            "fit": fit, "level": level, "posted_pay": pay,
            "applied": applied,
            "applied_date": when,
            "applied_date_estimated": estimated,
            "followed_up": followed, "status": status, "note": note,
        })
    return rows


STATUS = {"new": "new", "apply": "worth_applying", "maybe": "your_call", "reject": "not_a_fit",
          "skipped": "skipped", "applied": "applied"}
VERDICT = {"APPLY": "worth_applying", "MAYBE": "your_call", "REJECT": "not_a_fit", "SKIPPED": "skipped",
           "APPLIED": "applied"}


def rule_of(note):
    """The kit's rule id for a reference verdict note, or ""."""
    note = note or ""
    if note.startswith("Location rule, applied by the scanner"):
        return "location_remote_only" if " is the outer " in note else "location_in_country"
    if note.startswith("Rule 5, applied by the scanner"):
        return "phrases:renewals"
    if note.startswith("Rule 12, applied by the scanner"):
        return "pay"
    m = re.match(r"\s*Rule (\d+)", note)
    return f"rule_{m.group(1)}" if m else ""


def postings(seen, descriptions_from, out):
    """The reference memory as the kit's postings.json, and its saved descriptions copied across."""
    kit = {"postings": {}, "boards": dict(seen.get("sources", {}))}
    copied = 0
    os.makedirs(os.path.join(out, "data", "postings"), exist_ok=True)
    for k, v in seen.get("postings", {}).items():
        e = {x: v[x] for x in ("salary", "first_seen", "last_seen", "company", "title", "location", "url", "posted",
                               "source", "flag", "file", "note", "triaged", "gone") if x in v}
        e["status"] = STATUS.get(v.get("status"), v.get("status"))
        e["flags"] = [{"code": "imported", "text": t} for t in (v.get("flag") or "").split("; ") if t]
        if rule_of(v.get("note")):
            e["rule"] = rule_of(v.get("note"))
        src = os.path.join(descriptions_from, v.get("file") or f"{k}.md")
        if os.path.exists(src):
            with open(src, encoding="utf-8") as f:
                text = f.read()
            with open(os.path.join(out, "data", "postings", os.path.basename(src)), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            copied += 1
        kit["postings"][k] = e
    return kit, copied


_LOG_ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|([^|]*)\|([^|]*)\|\s*([A-Z]+)\s*\|(.*)\|\s*(\S+)\s*\|\s*$")


def decisions(log_text):
    """The reference triage log as decisions.log rows. A verdict clicked on the reference's own page
    is the user's decision; every other row was Claude's."""
    rows = []
    for line in log_text.splitlines():
        m = _LOG_ROW.match(line)
        if not m:
            continue
        date, company, title, verdict, why, key = m.groups()
        why = why.strip()
        row = {"date": date, "key": key, "company": company.strip(), "title": title.strip(),
               "verdict": VERDICT.get(verdict, verdict.lower()), "reason": why,
               "by": "user" if "page:" in why else "claude"}
        rev = re.search(r"REVERSAL of ([A-Z]+)", why)
        if rev:
            row["reverses"] = VERDICT.get(rev.group(1), rev.group(1).lower())
        if rule_of(why):
            row["rule"] = rule_of(why)
        rows.append(row)
    return rows


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--config", required=True)
    p.add_argument("--watchlist", required=True)
    p.add_argument("--pipeline")
    p.add_argument("--relative-dates")
    p.add_argument("--labels")
    p.add_argument("--seen")
    p.add_argument("--postings-dir")
    p.add_argument("--triage-log")
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
    relative = {}
    if a.relative_dates:
        with open(a.relative_dates, encoding="utf-8") as f:
            relative = json.load(f)
    apps = []
    if a.pipeline:
        with open(a.pipeline, encoding="utf-8") as f:
            apps = applications(f.read(), relative)
    with open(os.path.join(out, "data", "applications.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"applications": apps}, f, indent=1, ensure_ascii=False)
    report = [f"{len(load_file(a.watchlist).get('company', []))} companies", f"{len(apps)} applications"]
    if a.seen:
        with open(a.seen, encoding="utf-8") as f:
            seen = json.load(f)
        kit, copied = postings(seen, a.postings_dir or os.path.join(os.path.dirname(a.seen), "postings"), out)
        with open(os.path.join(out, "data", "postings.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(kit, f, indent=1, ensure_ascii=False)
        report.append(f"{len(kit['postings'])} postings ({copied} descriptions)")
    if a.triage_log:
        with open(a.triage_log, encoding="utf-8") as f:
            rows = decisions(f.read())
        with open(os.path.join(out, "data", "decisions.log"), "w", encoding="utf-8", newline="\n") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        report.append(f"{len(rows)} decisions")
    print(f"wrote settings, {', '.join(report)} to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
