"""A resume as a Word file, built by hand from its parts: a zip of a few XML files, standard library
only. It has the look resume_style.py sets out, which the PDF (pdf.py) shares: one column of real
text, standard heading and bullet styles, no tables or text boxes, Arial on US Letter. The name and
section headings are navy, with a navy rule under the name; dates sit on the right of each job's
first line.

A resume is a list of blocks (resume.blocks):
    ("name", text) ("contact", text) ("heading", text) ("job", title, place, dates)
    ("bullet", text) ("para", text)
"""

import io
import re
import zipfile
from xml.sax.saxutils import escape

from .resume_style import ACCENT, HAIRLINE, INK, MUTED, Style

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"

PAGE_W, PAGE_H = 12240, 15840  # US Letter, in twentieths of a point
MARGIN_X, MARGIN_Y = 1008, 864  # 0.7 and 0.6 inch, as in the PDF
TEXT_W = PAGE_W - 2 * MARGIN_X

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

PACKAGE_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG}">
<Relationship Id="rId1" Type="{REL}/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

DOCUMENT_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PKG}">
<Relationship Id="rId1" Type="{REL}/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="{REL}/numbering" Target="numbering.xml"/>
</Relationships>"""

CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>{title}</dc:title><dc:creator>{author}</dc:creator>
</cp:coreProperties>"""


def _hp(points):
    """A size in Word's half-points."""
    return max(2, round(points * 2))


def _tw(points):
    """A distance in Word's twentieths of a point."""
    return max(0, round(points * 20))


def _line(st):
    """Line spacing for "auto" (240 is single, about 1.15 times the size in Arial), to match the PDF."""
    return round(240 * st.leading / 1.15)


# Element order inside w:pPr and w:rPr follows the schema; Word refuses a file that doesn't.
def _styles(st):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W}">
<w:docDefaults>
<w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/><w:color w:val="{INK}"/><w:sz w:val="{_hp(st.body)}"/><w:szCs w:val="{_hp(st.body)}"/><w:lang w:val="en-US"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="0" w:line="{_line(st)}" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:before="0" w:after="40" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:b/><w:bCs/><w:color w:val="{ACCENT}"/><w:sz w:val="{_hp(st.name)}"/><w:szCs w:val="{_hp(st.name)}"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:pBdr><w:bottom w:val="single" w:sz="4" w:space="2" w:color="{HAIRLINE}"/></w:pBdr><w:spacing w:before="{_tw(st.before_section)}" w:after="{_tw(st.after_heading)}"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:bCs/><w:caps/><w:color w:val="{ACCENT}"/><w:spacing w:val="{_tw(st.tracking)}"/><w:sz w:val="{_hp(st.heading)}"/><w:szCs w:val="{_hp(st.heading)}"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/>
<w:pPr><w:numPr><w:numId w:val="1"/></w:numPr><w:spacing w:after="{_tw(st.after_bullet)}"/><w:ind w:left="240" w:hanging="240"/></w:pPr></w:style>
</w:styles>"""


def _numbering(st):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{W}">
<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/>
<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>
<w:pPr><w:ind w:left="240" w:hanging="240"/></w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:color w:val="{ACCENT}"/></w:rPr></w:lvl>
</w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>"""


def _clean(text):
    """Text Word accepts: XML-escaped, and without control characters XML can't hold."""
    return escape("".join(c for c in text if c in "\t\n" or ord(c) >= 32))


def _run(text, bold=False, color=None, size=None):
    props = ("<w:b/><w:bCs/>" if bold else "")
    props += f'<w:color w:val="{color}"/>' if color else ""
    props += f'<w:sz w:val="{_hp(size)}"/><w:szCs w:val="{_hp(size)}"/>' if size else ""
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{_clean(text)}</w:t></w:r>'


def _para(runs, style=None, ppr=""):
    pstyle = f'<w:pStyle w:val="{style}"/>' if style else ""
    props = pstyle + ppr
    return f"<w:p>{'<w:pPr>' + props + '</w:pPr>' if props else ''}{''.join(runs)}</w:p>"


def _body(blocks, st):
    out = []
    header = [i for i, b in enumerate(blocks) if b[0] in ("name", "contact")]
    last_header = header[-1] if header else -1
    rule = (f'<w:pBdr><w:bottom w:val="single" w:sz="{round(st.header_rule * 8)}" w:space="5" w:color="{ACCENT}"/></w:pBdr>'
            f'<w:spacing w:after="{_tw(st.after_header + 4)}"/>')
    first_in_section, seen_heading = False, False
    for i, b in enumerate(blocks):
        kind = b[0]
        if kind == "name":
            out.append(_para([_run(b[1])], "Title", rule if i == last_header else ""))
        elif kind == "contact":
            spacing = "" if i == last_header else '<w:spacing w:after="20"/>'
            out.append(_para([_run(b[1], color=MUTED, size=st.contact)], ppr=rule if i == last_header else spacing))
        elif kind == "heading":  # the first one sits under the header rule's own gap
            out.append(_para([_run(b[1])], "Heading1", "" if seen_heading else '<w:spacing w:before="0"/>'))
            first_in_section, seen_heading = True, True
        elif kind == "job":
            _, title, place, dates = b
            before = 0 if first_in_section else st.before_job
            tabs = (f'<w:keepNext/><w:tabs><w:tab w:val="right" w:pos="{TEXT_W}"/></w:tabs>'
                    f'<w:spacing w:before="{_tw(before)}" w:after="0" w:line="240" w:lineRule="auto"/>')
            runs = [_run(title, bold=True, size=st.title)]
            if dates:
                runs.append(f'<w:r><w:tab/></w:r>{_run(dates, color=MUTED, size=st.dates)}')
            out.append(_para(runs, ppr=tabs))
            if place:
                out.append(_para([_run(place, color=MUTED, size=st.place)],
                                 ppr='<w:keepNext/><w:spacing w:before="20" w:after="60"/>'))
            first_in_section = False
        elif kind == "bullet":
            out.append(_para([_run(b[1])], "ListBullet", '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'))
            first_in_section = False
        else:
            out.append(_para([_run(b[1])], ppr=f'<w:spacing w:after="{_tw(st.after_para)}"/>'))
            first_in_section = False
    return "".join(out)


def build(blocks, title="", author="", style=None):
    """The .docx file's bytes, in the given Style (the one the PDF was laid out in)."""
    st = style or Style()
    sect = (f'<w:sectPr><w:pgSz w:w="{PAGE_W}" w:h="{PAGE_H}"/>'
            f'<w:pgMar w:top="{MARGIN_Y}" w:right="{MARGIN_X}" w:bottom="{MARGIN_Y}" w:left="{MARGIN_X}" '
            f'w:header="432" w:footer="432" w:gutter="0"/></w:sectPr>')
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<w:document xmlns:w="{W}" xmlns:r="{REL}"><w:body>{_body(blocks, st)}{sect}</w:body></w:document>')
    parts = [("[Content_Types].xml", CONTENT_TYPES), ("_rels/.rels", PACKAGE_RELS),
             ("word/document.xml", document), ("word/_rels/document.xml.rels", DOCUMENT_RELS),
             ("word/styles.xml", _styles(st)), ("word/numbering.xml", _numbering(st)),
             ("docProps/core.xml", CORE.format(title=_clean(title), author=_clean(author)))]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in parts:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


def text_of(data):
    """The paragraphs' text, for tests and for checking a made file: one string per paragraph, a tab
    where Word puts one."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"<w:p>.*?</w:p>", xml, re.S):
        bits = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>|(<w:tab/>)", p, re.S)
        out.append("".join("\t" if tab else t for t, tab in bits)
                   .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    return out
