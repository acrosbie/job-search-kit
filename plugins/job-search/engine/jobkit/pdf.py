"""A resume as a PDF, standard library only, laid out like the Word file (docx.py): one column of
real text that hiring systems can read, US Letter, Helvetica.

Helvetica is one of the standard fonts every PDF reader has, so nothing is embedded. It draws the
Western European letters (Windows code page 1252). A resume with any other character can't be made
as a PDF here: build() raises CantDraw, and the Word file is still made.

The whole file is plain ASCII: anything else in the text is written as an octal escape. So it
survives any route that copies files as text into the user's folder.
"""

import re


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
GRAY = "0.35"


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

    def text(self, x, size, font, text, gray=False, leading=None):
        """One line of text whose top is at the current position; moves down by `leading`."""
        leading = leading or size * 1.28
        self.room(leading)
        base = self.y - size
        op = f"BT /{FONTS[font][0]} {size:g} Tf {x:.2f} {base:.2f} Td {_literal(text)} Tj ET"
        self.pages[-1].append(f"{GRAY} g {op} 0 g" if gray else op)
        self.y -= leading
        return base

    def rule(self, y):
        self.pages[-1].append(f"q 0.55 G 0.6 w {MARGIN_X:.2f} {y:.2f} m {PAGE_W - MARGIN_X:.2f} {y:.2f} l S Q")


def _lay_out(blocks):
    p = _Pages()
    for b in blocks:
        kind = b[0]
        if kind == "name":
            p.text(MARGIN_X, 18, "bold", b[1], leading=24)
        elif kind == "contact":
            for line in wrap(b[1], "regular", 9.5, TEXT_W):
                p.text(MARGIN_X, 9.5, "regular", line, gray=True, leading=12.5)
        elif kind == "heading":
            p.y -= 9
            p.room(13 + 6 + 3 * 13)  # keep a heading with what follows it
            base = p.text(MARGIN_X, 10.5, "bold", b[1].upper(), leading=13)
            p.rule(base - 3.5)
            p.y -= 5
        elif kind == "job":
            _, title, place, dates = b
            p.y -= 5
            p.room(13 + 12.5 + 13)  # keep a job's first lines together
            room = TEXT_W - (width(dates, "regular", 9.5) + 14 if dates else 0)
            first = True
            for line in wrap(title, "bold", 10.5, room):
                top = p.y
                p.text(MARGIN_X, 10.5, "bold", line, leading=13)
                if first and dates:
                    x = PAGE_W - MARGIN_X - width(dates, "regular", 9.5)
                    p.pages[-1].append(f"{GRAY} g BT /F1 9.5 Tf {x:.2f} {top - 10.5:.2f} Td {_literal(dates)} Tj ET 0 g")
                first = False
            for line in wrap(place, "italic", 10, TEXT_W) if place else []:
                p.text(MARGIN_X, 10, "italic", line, leading=12.5)
            p.y -= 1.5
        elif kind == "bullet":
            for i, line in enumerate(wrap(b[1], "regular", 10, TEXT_W - 14)):
                if i == 0:  # the mark first, so text read from the file comes in reading order
                    p.room(12.8)
                    p.pages[-1].append(f"BT /F1 10 Tf {MARGIN_X + 3:.2f} {p.y - 10:.2f} Td {_literal(chr(8226))} Tj ET")
                p.text(MARGIN_X + 14, 10, "regular", line, leading=12.8)
            p.y -= 1.5
        else:
            for line in wrap(b[1], "regular", 10, TEXT_W):
                p.text(MARGIN_X, 10, "regular", line, leading=12.8)
            p.y -= 3
    return p.pages


def build(blocks, title="", author=""):
    """(the .pdf file's bytes, its number of pages). Raises CantDraw for a character Helvetica
    can't draw."""
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
    pages = _lay_out(blocks)

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
