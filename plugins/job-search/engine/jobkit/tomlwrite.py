"""Writing settings.toml and companies.toml. Claude changes settings through the engine's commands
rather than editing the files, so a pattern full of backslashes is always written correctly."""

import json

SECTION_ORDER = ("you", "titles", "places", "description", "pay", "workday", "triage", "tracking", "schedule", "page", "labels")


def value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{json.dumps(k)} = {value(x)}" for k, x in v.items()) + " }"
    return json.dumps(v, ensure_ascii=False)  # JSON strings and string lists are valid TOML


def header_of(text):
    """The comment lines at the top of a file, kept when the file is rewritten."""
    lines = []
    for line in (text or "").splitlines():
        if line.startswith("#") or (not line.strip() and lines):
            lines.append(line)
        else:
            break
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def settings_text(raw, header=""):
    out = [header, ""] if header else []
    sections = [s for s in SECTION_ORDER if s in raw] + [s for s in raw if s not in SECTION_ORDER and s != "phrase_rejects"]
    for name in sections:
        if name == "pay" and raw.get("phrase_rejects"):
            for pr in raw["phrase_rejects"]:  # phrase rules read best just before pay, as in the docs
                out += ["[[phrase_rejects]]"] + [f"{k} = {value(v)}" for k, v in pr.items()] + [""]
        if not isinstance(raw[name], dict):
            continue
        out += [f"[{name}]"] + [f"{k} = {value(v)}" for k, v in raw[name].items()] + [""]
    if raw.get("phrase_rejects") and "pay" not in raw:
        for pr in raw["phrase_rejects"]:
            out += ["[[phrase_rejects]]"] + [f"{k} = {value(v)}" for k, v in pr.items()] + [""]
    return "\n".join(out)


def companies_text(companies, header=""):
    out = [header, ""] if header else []
    for c in companies:
        out.append("[[company]]")
        out += [f"{k} = {value(v)}" for k, v in c.items()]
        out.append("")
    return "\n".join(out)
