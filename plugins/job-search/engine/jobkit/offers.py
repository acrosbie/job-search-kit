"""Offers, side by side: what each company said or wrote, against the user's ask and walk-away number.

What a company has said about pay is kept on its application, in `offer`, as the user gave it:

    stage          said (a recruiter's number or band) or written (the offer itself)
    base_low, base_high   yearly base; one number is both
    bonus          the yearly target bonus, in dollars
    equity         in the user's words ("RSUs, 4 years"); equity_yearly, its yearly value if the company said
    k401           in the user's words ("4% match"); k401_yearly, its yearly value
    travel         in the user's words ("heavier at launch")
    deadline       the day the offer must be answered
    note, date     the user's words, and when

The comparison is arithmetic on those numbers, never a guess at what a company would pay. The user's
ask and walk-away come from what-i-want.md, their last pay from about-me.md, each passed in.
"""

import datetime as dt
import os

from . import track
from .errors import NotFound, Refused

FIELDS_N = ("base_low", "base_high", "bonus", "equity_yearly", "k401_yearly")
FIELDS_T = ("equity", "k401", "travel", "note")


def record(root, clock, ident, stage="said", base=0, base_low=0, base_high=0, bonus=0, equity="", equity_yearly=0,
           k401="", k401_yearly=0, travel="", deadline="", note=""):
    """Add what a company said or wrote about pay to its application. Later numbers replace earlier ones,
    field by field; a written offer replaces what was said."""
    if stage not in ("said", "written"):
        raise Refused("pay a company gave is said (a recruiter's number) or written (the offer)")
    if base:
        base_low = base_high = base
    if base_low and base_high and base_low > base_high:
        raise Refused(f"the base's low ({base_low}) is above its high ({base_high})")
    for n in (base_low, base_high, bonus, equity_yearly, k401_yearly):
        if n and (n < 0 or n > 10_000_000):
            raise Refused(f"{n} isn't a yearly dollar amount")
    if deadline:
        try:
            dt.date.fromisoformat(deadline)
        except ValueError:
            raise Refused(f"the deadline is a date, YYYY-MM-DD, not {deadline!r}") from None
    applications = track.load(root)
    a = track.find(applications, ident)
    if a is None:
        raise NotFound(f"no application {ident}")
    o = dict(a.get("offer") or {})
    if stage == "written" and o.get("stage") != "written":
        o = {}  # the offer itself replaces what was said before it
    o["stage"] = stage
    for k, v in (("base_low", base_low), ("base_high", base_high), ("bonus", bonus), ("equity_yearly", equity_yearly),
                 ("k401_yearly", k401_yearly)):
        if v:
            o[k] = int(v)
    for k, v in (("equity", equity), ("k401", k401), ("travel", travel), ("note", note), ("deadline", deadline)):
        if (v or "").strip():
            o[k] = v.strip()
    o["date"] = clock.today()
    a["offer"] = o
    a["history"].append(track._event(clock, clock.today(), note, event="offer_" + stage,
                                     value=f"{o.get('base_low', 0)}-{o.get('base_high', 0)}"))
    track.save(root, applications)
    return {"application": a["id"], "company": a.get("company", ""), "offer": o}


def _k(n):
    return f"${round(n / 1000)}K" if n else ""


def _range(lo, hi):
    if not (lo or hi):
        return "not said"
    return _k(lo or hi) if (lo or hi) == (hi or lo) else f"{_k(lo)} to {_k(hi)}"


def compare(root, ask=0, walk_away=0, last_base=0):
    """Every open application with pay said or written, side by side, and the arithmetic: the first
    year's total at the low and high end, and how the base stands against the ask, the walk-away
    number and the last job. Writes interviews/offers.md, the same as a table."""
    rows = []
    for a in track.load(root):
        o = a.get("offer")
        if not o or a["status"] not in ("applied", "replied", "screen", "interview", "offer"):
            continue
        lo, hi = o.get("base_low", 0), o.get("base_high", 0)
        extra = o.get("bonus", 0) + o.get("equity_yearly", 0) + o.get("k401_yearly", 0)
        top = hi or lo
        rows.append({
            "application": a["id"], "company": a.get("company", ""), "role": a.get("role", ""), "stage": o["stage"],
            "base_low": lo, "base_high": hi, "bonus": o.get("bonus", 0), "equity": o.get("equity", ""),
            "equity_yearly": o.get("equity_yearly", 0), "k401": o.get("k401", ""), "k401_yearly": o.get("k401_yearly", 0),
            "travel": o.get("travel", ""), "deadline": o.get("deadline", ""), "posted_pay": a.get("posted_pay", ""),
            "first_year_low": (lo or hi) + extra if top else 0, "first_year_high": top + extra if top else 0,
            "base_top_vs_ask": top - ask if (ask and top) else None,
            "base_top_meets_walk_away": (top >= walk_away) if (walk_away and top) else None,
            "base_top_vs_last": top - last_base if (last_base and top) else None,
            "said_on": o.get("date", ""), "note": o.get("note", "")})
    rows.sort(key=lambda r: -(r["base_high"] or r["base_low"]))
    out = {"ask": ask, "walk_away": walk_away, "last_base": last_base, "offers": rows,
           "note": "The numbers each company gave, as you told them. Arithmetic, not a prediction."}
    if rows:
        out["file"] = _write(root, out)
    return out


def _write(root, out):
    lines = ["# Offers side by side", "",
             f"Your ask: {_k(out['ask']) or 'not set'} base. Walk away below: {_k(out['walk_away']) or 'not set'}."
             + (f" Your last base: {_k(out['last_base'])}." if out["last_base"] else ""), "",
             "| | " + " | ".join(r["company"] for r in out["offers"]) + " |",
             "|---|" + "---|" * len(out["offers"])]

    def row(label, f):
        lines.append(f"| {label} | " + " | ".join(f(r) or "not said" for r in out["offers"]) + " |")
    row("Where it stands", lambda r: "written offer" if r["stage"] == "written" else f"said, {r['said_on']}")
    row("Base", lambda r: _range(r["base_low"], r["base_high"]))
    row("Bonus", lambda r: _k(r["bonus"]))
    row("Equity", lambda r: " ".join(x for x in (r["equity"], f"({_k(r['equity_yearly'])} a year)" if r["equity_yearly"] else "") if x))
    row("401(k)", lambda r: " ".join(x for x in (r["k401"], f"({_k(r['k401_yearly'])} a year)" if r["k401_yearly"] else "") if x))
    row("Travel", lambda r: r["travel"])
    row("First year, all in", lambda r: _range(r["first_year_low"], r["first_year_high"]))
    row("Top of base vs your ask", lambda r: "" if r["base_top_vs_ask"] is None else
        ("meets it" if r["base_top_vs_ask"] >= 0 else f"{_k(-r['base_top_vs_ask'])} below"))
    row("Walk-away line", lambda r: "" if r["base_top_meets_walk_away"] is None else
        ("above it" if r["base_top_meets_walk_away"] else "below it, even at the top"))
    row("The posting said", lambda r: r["posted_pay"])
    row("Answer by", lambda r: r["deadline"])
    lines += ["", out["note"], ""]
    rel = "interviews/offers.md"
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return rel
