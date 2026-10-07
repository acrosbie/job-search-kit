"""A resume as a PDF, standard library only, in the look resume_style.py sets out and the Word file
(docx.py) shares: one column of real text that hiring systems can read, US Letter, Helvetica.

Helvetica is one of the standard fonts every PDF reader has, so nothing is embedded. It draws the
Western European letters (Windows code page 1252). A resume with any other character can't be made
as a PDF here: build() raises CantDraw, and the Word file is still made.

The whole file is plain ASCII: anything else in the text is written as an octal escape. So it
survives any route that copies files as text into the user's folder.
"""

import re

from .resume_style import ACCENT, HAIRLINE, INK, MUTED, Style, rgb


def _widths(text):
    return tuple(int(w) for w in text.split())


# Advance widths in 1/1000 em for codes 32 to 255 of WinAnsiEncoding (Windows code page 1252),
# the same as Adobe's Helvetica metrics. Generated once from PyMuPDF's metric-compatible Helvetica.
REGULAR = _widths("""
278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 556
556 278 278 584 584 584 556 1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 667 778
722 667 611 722 667 944 667 667 611 278 278 278 469 556 333 556 556 500 556 556 278 556 556 222 222
500 222 833 556 556 556 556 333 500 278 556 500 722 500 500 500 334 260 334 584 0 556 0 222 556 333
1000 556 556 333 1000 667 333 1000 0 611 0 0 222 222 333 333 350 556 1000 333 1000 500 333 944 0 500
667 278 333 556 556 556 556 260 556 333 737 370 556 584 333 737 333 400 584 333 333 333 556 537 278
333 333 365 556 834 834 834 611 667 667 667 667 667 667 1000 722 667 667 667 667 278 278 278 278 722
722 778 778 778 778 778 584 778 722 722 722 722 667 667 611 556 556 556 556 556 556 889 500 556 556
556 556 278 278 278 278 556 556 556 556 556 556 556 584 611 556 556 556 556 500 556 500
""")
BOLD = _widths("""
278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 556 556 556 556 556 556 556 556 556
556 333 333 584 584 584 611 975 722 722 722 722 667 611 778 722 278 556 722 611 833 722 778 667 778
722 667 611 722 667 944 667 667 611 333 278 333 584 556 333 556 611 556 611 556 333 611 611 278 278
556 278 889 611 611 611 611 389 556 333 611 556 778 556 556 500 389 280 389 584 0 556 0 278 556 500
1000 556 556 333 1000 667 333 1000 0 611 0 0 278 278 500 500 350 556 1000 333 1000 556 333 944 0 500
667 278 333 556 556 556 556 280 556 333 737 370 556 584 333 737 333 400 584 333 333 333 611 556 278
333 333 365 556 834 834 834 611 722 722 722 722 722 722 1000 722 667 667 667 667 278 278 278 278 722
722 778 778 778 778 778 584 778 722 722 722 722 667 667 611 556 556 556 556 556 556 889 556 556 556
556 556 278 278 278 278 611 611 611 611 611 611 611 584 611 611 611 611 611 556 611 556
""")

# name in the page's resources, the standard font, its widths (the oblique has the regular's widths)
FONTS = {"regular": ("F1", "Helvetica", REGULAR), "bold": ("F2", "Helvetica-Bold", BOLD),
         "italic": ("F3", "Helvetica-Oblique", REGULAR)}

PAGE_W, PAGE_H = 612, 792  # US Letter, in points
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 50.4, 43.2, 43.2  # 0.7 and 0.6 inch, as in the Word file
TEXT_W = PAGE_W - 2 * MARGIN_X


class CantDraw(ValueError):
    """The resume has characters Helvetica can't draw. `chars` lists them."""

    def __init__(self, chars):
        self.chars = chars
        super().__init__("the PDF can't show " + ", ".join(repr(c) for c in chars))


def _bytes(text):
    return text.replace("\t", " ").encode("cp1252")


def width(text, font, size):
    table = FONTS[font][2]
    return sum(table[b - 32] for b in _bytes(text) if b >= 32) * size / 1000


def wrap(text, font, size, room):
    """The text in lines no wider than `room`, broken between words; a word too long for a line is
    broken where it must be."""
    lines, line = [], ""
    for word in text.split():
        while width(word, font, size) > room:
            cut = len(word)
            while cut > 1 and width(word[:cut], font, size) > room:
                cut -= 1
            if line:
                lines.append(line)
                line = ""
            lines.append(word[:cut])
            word = word[cut:]
        trial = f"{line} {word}" if line else word
        if width(trial, font, size) <= room:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]


def _literal(text):
    """A PDF string, in ASCII: brackets and backslashes escaped, anything else outside printable
    ASCII as an octal escape."""
    out = []
    for b in _bytes(text):
        if b in (40, 41, 92):
            out.append("\\" + chr(b))
        elif 32 <= b < 127:
            out.append(chr(b))
        else:
            out.append(f"\\{b:03o}")
    return "(" + "".join(out) + ")"


def _info_string(text):
    """A document-information string: plain ASCII as it is, anything else as UTF-16 in hex."""
    if all(32 <= ord(c) < 127 for c in text):
        return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"
    return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"


class _Pages:
    """Lays lines down the page, starting a new page when the next one wouldn't fit."""

    def __init__(self):
        self.pages = [[]]
        self.y = PAGE_H - MARGIN_TOP

    def room(self, needed):
        if self.y - needed < MARGIN_BOTTOM:
            self.pages.append([])
            self.y = PAGE_H - MARGIN_TOP

    def draw(self, x, base, size, font, text, color=INK, tracking=0.0):
        """Text with its baseline at `base`, without moving down."""
        tc = f"{tracking:g} Tc " if tracking else ""
        self.pages[-1].append(f"q {rgb(color)} rg BT /{FONTS[font][0]} {size:.2f} Tf {tc}{x:.2f} {base:.2f} Td "
                              f"{_literal(text)} Tj ET Q")

    def text(self, x, size, font, text, leading, color=INK, tracking=0.0):
        """One line of text whose top is at the current position; moves down by `leading`. Returns
        its baseline."""
        self.room(leading)
        base = self.y - size
        self.draw(x, base, size, font, text, color, tracking)
        self.y -= leading
        return base

    def rule(self, y, color, weight):
        self.pages[-1].append(f"q {rgb(color)} RG {weight:g} w {MARGIN_X:.2f} {y:.2f} m {PAGE_W - MARGIN_X:.2f} {y:.2f} l S Q")


def _lay_out(blocks, st):
    """(each page's drawing operations, how full the last page is, from 0 to 1)."""
    p = _Pages()
    header_done, first_in_section, seen_heading = False, False, False
    for b in blocks:
        kind = b[0]
        if kind not in ("name", "contact") and not header_done:
            p.y -= 4
            p.rule(p.y, ACCENT, st.header_rule)
            p.y -= st.after_header
            header_done = True
        if kind == "name":
            p.text(MARGIN_X, st.name, "bold", b[1], leading=st.name * 1.22, color=ACCENT)
        elif kind == "contact":
            for line in wrap(b[1], "regular", st.contact, TEXT_W):
                p.text(MARGIN_X, st.contact, "regular", line, leading=st.contact * 1.45, color=MUTED)
        elif kind == "heading":
            if seen_heading:  # the first one sits under the header rule's own gap
                p.y -= st.before_section
            seen_heading = True
            p.room(st.heading * 1.5 + st.after_heading + 3 * st.body * st.leading)  # keep a heading with what follows
            base = p.text(MARGIN_X, st.heading, "bold", b[1].upper(), leading=st.heading * 1.5, color=ACCENT,
                          tracking=st.tracking)
            p.rule(base - 4, HAIRLINE, 0.6)
            p.y -= st.after_heading
            first_in_section = True
        elif kind == "job":
            _, title, place, dates = b
            if not first_in_section:
                p.y -= st.before_job
            p.room(st.title * 1.35 + st.place * 1.45 + st.body * st.leading)  # keep a job's first lines together
            room = TEXT_W - (width(dates, "regular", st.dates) + 14 if dates else 0)
            for i, line in enumerate(wrap(title, "bold", st.title, room)):
                base = p.text(MARGIN_X, st.title, "bold", line, leading=st.title * 1.35)
                if i == 0 and dates:
                    p.draw(PAGE_W - MARGIN_X - width(dates, "regular", st.dates), base, st.dates, "regular", dates, MUTED)
            for line in wrap(place, "regular", st.place, TEXT_W) if place else []:
                p.text(MARGIN_X, st.place, "regular", line, leading=st.place * 1.45, color=MUTED)
            p.y -= 2
            first_in_section = False
        elif kind == "bullet":
            lead = st.body * st.leading
            for i, line in enumerate(wrap(b[1], "regular", st.body, TEXT_W - 12)):
                if i == 0:  # the mark first, so text read from the file comes in reading order
                    p.room(lead)
                    p.draw(MARGIN_X + 1.5, p.y - st.body, st.body, "regular", chr(8226), ACCENT)
                p.text(MARGIN_X + 12, st.body, "regular", line, leading=lead)
            p.y -= st.after_bullet
            first_in_section = False
        else:
            for line in wrap(b[1], "regular", st.body, TEXT_W):
                p.text(MARGIN_X, st.body, "regular", line, leading=st.body * st.leading)
            p.y -= st.after_para
            first_in_section = False
    if not header_done:
        p.y -= 4
        p.rule(p.y, ACCENT, st.header_rule)
    fill = (PAGE_H - MARGIN_TOP - p.y) / (PAGE_H - MARGIN_TOP - MARGIN_BOTTOM)
    return p.pages, fill


def _check(blocks):
    bad = set()
    for b in blocks:
        for part in b[1:]:
            for c in part:
                try:
                    c.encode("cp1252")
                except UnicodeEncodeError:
                    bad.add(c)
    if bad:
        raise CantDraw(sorted(bad))


GROW = (1.03, 1.06, 1.09)  # body type up to about 11pt
SPREAD = (1.2, 1.4, 1.6)
TIGHTEN = ((1.0, 0.9), (0.97, 0.9), (0.97, 0.8), (0.94, 0.8))  # body type down to about 9.5pt
FULL = 0.93


def fit(blocks):
    """The Style that fills the page best. A resume that fits on one page grows its type, then its
    gaps, while it stays on one page and no more than 93% full. One that spills onto a second page
    by less than a third of it tightens until it fits on one. A longer one keeps the normal size."""
    _check(blocks)

    def measure(style):
        pages, fill = _lay_out(blocks, style)
        return len(pages), fill

    best = Style()
    pages, fill = measure(best)
    if pages == 1:
        for scale in GROW:
            n, f = measure(Style(scale))
            if n > 1 or f > FULL:
                break
            best = Style(scale)
        for space in SPREAD:
            n, f = measure(Style(best.scale, space))
            if n > 1 or f > FULL:
                break
            best = Style(best.scale, space)
    elif pages == 2 and fill < 0.33:
        for scale, space in TIGHTEN:
            if measure(Style(scale, space))[0] == 1:
                return Style(scale, space)
    return best


def build(blocks, title="", author="", style=None):
    """(the .pdf file's bytes, its number of pages). Raises CantDraw for a character Helvetica
    can't draw. Without a style, the one fit() picks."""
    _check(blocks)
    pages, _ = _lay_out(blocks, style or fit(blocks))

    objects = []  # object n is objects[n - 1]

    def add(body):
        objects.append(body)
        return len(objects)

    catalog = add("")  # filled in once the page tree's number is known
    tree = add("")
    fonts = {name: add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} /Encoding /WinAnsiEncoding >>")
             for name, base, _ in FONTS.values()}
    resources = "<< /Font << " + " ".join(f"/{n} {o} 0 R" for n, o in fonts.items()) + " >> >>"
    kids = []
    for ops in pages:
        stream = "\n".join(ops)
        content = add(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        kids.append(add(f"<< /Type /Page /Parent {tree} 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
                        f"/Resources {resources} /Contents {content} 0 R >>"))
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {tree} 0 R >>"
    objects[tree - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    info = add(f"<< /Title {_info_string(title)} /Author {_info_string(author)} >>")

    out, offsets = "%PDF-1.4\n", []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("ascii"), len(pages)


def text_of(data):
    """Every piece of text the file draws, in order, for tests and for checking a made file."""
    out = []
    for m in re.finditer(rb"\((?:\\.|[^\\)])*\) Tj", data):
        raw, body, i = m.group(0)[1:-4], bytearray(), 0
        while i < len(raw):
            c = raw[i]
            if c == 92:  # a backslash
                nxt = raw[i + 1:i + 4]
                digits = re.match(rb"[0-7]{1,3}", nxt)
                if digits:
                    body.append(int(digits.group(0), 8))
                    i += 1 + len(digits.group(0))
                    continue
                body.append(raw[i + 1])
                i += 2
                continue
            body.append(c)
            i += 1
        out.append(body.decode("cp1252"))
    return out
