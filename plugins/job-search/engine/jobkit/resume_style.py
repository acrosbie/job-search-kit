"""How a resume looks, shared by the Word file (docx.py) and the PDF (pdf.py), so the two match.

One column of real text, as hiring systems read best. The name and section headings are in a deep
navy, as are the rule under the name and the bullet marks; everything else is near-black or a muted
grey, so it prints well in black and white too. Arial in Word and Helvetica in the PDF share their
letter widths, so a line breaks in the same place in both.

`scale` grows or shrinks the type, and `space` the gaps between things. pdf.fit() picks both so a
resume fills its page well: a short one grows, one that spills a few lines onto a second page
tightens to fit on one.
"""

ACCENT = "1F3A5F"    # deep navy: the name, section headings, the rule under the name, bullet marks
INK = "1A1F24"       # titles and body text
MUTED = "56606B"     # contact lines, companies and places, dates
HAIRLINE = "C3CDD9"  # the rule under each section heading


class Style:
    """Sizes and gaps in points."""

    def __init__(self, scale=1.0, space=1.0):
        self.scale, self.space = scale, space
        s, g = scale, space
        self.name = 22 * s
        self.contact = 9.5 * s
        self.heading = 9.5 * s
        self.tracking = 1.1          # letter-spacing of section headings
        self.title = 10.5 * s
        self.dates = 9.5 * s
        self.place = 9.5 * s
        self.body = 10 * s
        self.leading = 1.32          # line height, as a multiple of the type size
        self.header_rule = 1.2       # the rule under the name and contact lines
        self.after_header = 10 * g
        self.before_section = 12 * g
        self.after_heading = 6 * g
        self.before_job = 8 * g
        self.after_bullet = 2 * g
        self.after_para = 4 * g

    def __repr__(self):
        return f"Style(scale={self.scale}, space={self.space})"


def rgb(hex6):
    """A colour as PDF's "r g b", from its hex."""
    return " ".join(f"{int(hex6[i:i + 2], 16) / 255:.3f}" for i in (0, 2, 4))
