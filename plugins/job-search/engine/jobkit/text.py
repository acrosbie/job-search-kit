"""Text helpers: job descriptions from HTML, and pay ranges from descriptions."""

import re
from html.parser import HTMLParser


class _Text(HTMLParser):
    BLOCK = {"p", "br", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "tr", "section", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(s):
    if not s:
        return ""
    p = _Text()
    p.feed(s)
    text = "".join(p.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Pay as postings write it: "$150K to $190K", "$150,000.00 - $190,000.00", "$120-150K", "between $165,000
# and $205,000", "USD 140,000 - 170,000", "104,000.00 - 176,250.00 annually", "$45 to $55 an hour".
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?"
_PER = r"(?:\s?(?:/|per\s|an?\s)\s?(?:hour|hr|year|yr|annum|month|mo)\b)"
_CUR = r"(?:US\$|USD\s?|\$)"
_RANGE = re.compile(
    r"(?P<fx>[£€]|CA\$|C\$|A\$)?(?P<between>between\s+)?(?P<c1>" + _CUR + r")?\s?(?P<a>" + _NUM + r")\s?(?P<ka>[Kk]\b)?(?P<pa>" + _PER + r")?"
    r"\s?(?P<sep>-|–|—|to|and)\s?"
    r"(?P<c2>" + _CUR + r")?\s?(?P<b>" + _NUM + r")\s?(?P<kb>[Kk]\b)?(?P<pb>" + _PER + r")?"
    r"(?P<cur>\s?(?:USD|CAD|EUR|GBP|AUD)\b)?", re.I)
# What a range is for, from the nearest of these words: base pay, or something on top of it.
_BASE_WORDS = r"\bbase\b|\bsalary\b|\bpay\b|compensation|\bwages?\b|hiring range|\bannual(?:ly)?\b"
_EXTRA_WORDS = r"bonus|commission|incentive|\bote\b|on[- ]target|equity|\bstock\b|\brsus?\b|stipend|allowance|sign[- ]on|relocation|reimburs"
_LABEL = re.compile(r"(?P<base>" + _BASE_WORDS + r")|(?P<extra>" + _EXTRA_WORDS + r")", re.I)
# A label written straight after the range: "$20K-$30K annual bonus", "$150K-$190K base salary".
_TAIL_EXTRA = re.compile(r"^[ \t]{0,3}(?:(?:annual|target|yearly|quarterly|sign[- ]on)\s)?(?:bonus|commission|incentive|equity|stipend|allowance|ote)\b", re.I)
_TAIL_BASE = re.compile(r"^[ \t]{0,3}(?:base|salary)\b", re.I)
_PERIOD_AFTER = re.compile(r"^\W{0,3}(?:per\s|an?\s|/)?\s?(?P<p>hour|hr|hourly|year|yr|yearly|annum|annually|month|mo|monthly)\b", re.I)
_HOURS_A_YEAR = 2080


def _amount(num, k):
    return float(num.replace(",", "")) * (1000 if k else 1)


def _ranges(text):
    """Every pay range in the text: (low, high, unit, tier, raw_low, raw_high). low and high are a year's
    pay in dollars (an hourly or monthly range converted); tier is 2 for a range labelled as base pay,
    1 for one with no label, 0 for a bonus, commission, equity or stipend range."""
    out = []
    for m in _RANGE.finditer(text or ""):
        if m.group("fx") or (m.group("cur") and m.group("cur").strip().upper() != "USD"):
            continue  # another currency
        if m.group("sep").lower() == "and" and not m.group("between"):
            continue
        a, b = _amount(m.group("a"), m.group("ka")), _amount(m.group("b"), m.group("kb"))
        if m.group("kb") and not m.group("ka") and a < 1000:
            a *= 1000  # "$120-150K"
        if m.group("ka") and not m.group("kb") and b < 1000:
            b *= 1000
        start = m.start("between") if m.group("between") else m.start("c1") if m.group("c1") else m.start("a")
        # Its label is on its own line, in the same sentence; or on a heading line just above ("Base pay:").
        lines = text[max(0, start - 160):start].split("\n")
        before = re.split(r"[.;]\s", lines[-1])[-1]
        if len(lines) > 1 and lines[-2].rstrip().endswith(":") and not _LABEL.search(before):
            before = lines[-2] + " " + before
        after = text[m.end():m.end() + 40]
        per = (m.group("pa") or "") + (m.group("pb") or "")
        p = _PERIOD_AFTER.search(after)
        per += p.group("p") if p else ""
        unit = "hour" if re.search(r"hour|hr", per, re.I) else "month" if re.search(r"mo", per, re.I) else "year"
        money = m.group("c1") or m.group("c2") or m.group("cur")
        labels = list(_LABEL.finditer(before))
        rest = after[len(p.group(0)):] if p else after
        if _TAIL_EXTRA.search(rest):
            tier = 0
        elif _TAIL_BASE.search(rest):
            tier = 2
        elif labels:
            tier = 2 if labels[-1].group("base") else 0
        else:
            tier = 1
        if not money and not (labels or p or per):
            continue  # "74K to 95K" with nothing saying it's pay
        if unit == "hour":
            if not 15 <= a <= b <= 500:
                continue
            lo, hi = a * _HOURS_A_YEAR, b * _HOURS_A_YEAR
        elif unit == "month":
            if not 4000 <= a <= b <= 100000:
                continue
            lo, hi = a * 12, b * 12
        else:
            lo, hi = a, b
        if lo < 50000 or hi < lo or hi > 1500000:
            continue
        out.append((int(lo), int(hi), unit, tier, a, b))
    return out


def _best(text):
    """The range a posting's pay is: labelled base pay first, then unlabelled; within those, the
    highest top (bands for several levels list the top band last). Never a bonus or equity range."""
    found = [r for r in _ranges(text) if r[3] > 0]
    return max(found, key=lambda r: (r[3], r[1])) if found else None


def salary_range(text):
    """(low, high): a year's pay in dollars, from the best pay range in a description. None if none."""
    best = _best(text)
    return (best[0], best[1]) if best else None


def _money(x):
    return f"${x:,.2f}".replace(".00", "") if x != int(x) else f"${int(x):,}"


def salary_from(text):
    """The best pay range as the page shows it: '$155K to $175K', '$45 to $55 an hour',
    '$8,000 to $10,000 a month'. Empty string if none."""
    best = _best(text)
    if not best:
        return ""
    lo, hi, unit, _, a, b = best
    if unit == "hour":
        return f"{_money(a)} to {_money(b)} an hour"
    if unit == "month":
        return f"{_money(a)} to {_money(b)} a month"
    return f"${lo // 1000}K to ${hi // 1000}K"
