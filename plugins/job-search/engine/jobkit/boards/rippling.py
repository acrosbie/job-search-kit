"""Rippling's own hiring system. The list carries name, url and one place; the detail call
carries the description, every place and the posting date."""

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    token = company["token"]
    base = f"https://api.rippling.com/platform/api/ats/v1/board/{token}/jobs"
    data = fetch_json(base)
    out = []
    for j in data if isinstance(data, list) else data.get("items", []):
        jid = j.get("uuid") or j.get("id")

        def detail(jid=jid):
            d = fetch_json(f"{base}/{jid}")
            locs = [(x.get("label") or "") if isinstance(x, dict) else str(x) for x in d.get("workLocations") or []]
            desc = d.get("description") or ""
            if isinstance(desc, dict):  # {"company": html, "role": html}
                desc = "\n\n".join(desc.get(k) or "" for k in ("role", "company"))
            return {"description": html_to_text(desc),
                    "location": "; ".join(x for x in locs if x),
                    "posted": (d.get("createdOn") or "")[:10]}

        out.append(make_record("rippling", company, jid, j.get("name"), (j.get("workLocation") or {}).get("label"),
                               j.get("url"), "", detail=detail))
    return out
