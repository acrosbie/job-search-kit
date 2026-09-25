"""Greenhouse: the public job-board API. The list has titles and places; each description is a
second call, made only for titles that pass the filter."""

import html

from ..net import fetch_json
from ..text import html_to_text
from .common import make_record


def read(company, ctx):
    token = company["token"]
    data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    out = []
    for j in data.get("jobs", []):
        jid = j["id"]

        def detail(jid=jid):
            d = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{jid}")
            return html_to_text(html.unescape(d.get("content", "")))

        out.append(make_record("greenhouse", company, jid, j.get("title"), (j.get("location") or {}).get("name"),
                               j.get("absolute_url"), j.get("updated_at"), detail=detail))
    return out
