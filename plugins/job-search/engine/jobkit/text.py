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


_SAL = re.compile(r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?[Kk])\s?(?:-|–|—|to)\s?\$?\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?[Kk])")


def _dollars(tok):
    tok = tok.replace(",", "")
    return int(float(tok[:-1]) * 1000) if tok[-1] in "kK" else int(tok)


def salary_range(text):
    """(low, high) in dollars for the highest-topped pay range above $50K in a description, so
    stipends and bonuses are skipped. None if no range written with a $ is found."""
    best = None
    for m in _SAL.finditer(text or ""):
        lo, hi = _dollars(m.group(1)), _dollars(m.group(2))
        if lo < 50000 or hi < lo or hi > 1500000:
            continue
        if best is None or hi > best[1]:
            best = (lo, hi)
    return best


def salary_from(text):
    """salary_range() as '$155K to $175K'. Empty string if none."""
    best = salary_range(text)
    return f"${best[0] // 1000}K to ${best[1] // 1000}K" if best else ""
