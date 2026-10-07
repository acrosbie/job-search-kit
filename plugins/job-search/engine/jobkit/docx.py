"""A resume as a Word file, built by hand from its parts: a zip of a few XML files, standard library
only. The layout is the one hiring systems read best: a single column of real text, standard
headings, and no tables or text boxes. Arial, US Letter, bullets that are real Word bullets, and
dates on the right of each job's first line.

A resume is a list of blocks (resume.blocks):
    ("name", text) ("contact", text) ("heading", text) ("job", title, place, dates)
    ("bullet", text) ("para", text)
"""

import io
import zipfile
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"

PAGE_W, PAGE_H = 12240, 15840  # US Letter, in twentieths of a point
MARGIN_X, MARGIN_Y = 1008, 864  # 0.7 and 0.6 inch
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

# Element order inside w:pPr and w:rPr follows the schema; Word refuses a file that doesn't.
STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W}">
<w:docDefaults>
<w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/><w:color w:val="1A1A1A"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:lang w:val="en-US"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="40" w:line="252" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:spacing w:before="0" w:after="40"/></w:pPr><w:rPr><w:b/><w:bCs/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="8C8C8C"/></w:pBdr><w:spacing w:before="220" w:after="80"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:bCs/><w:caps/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/>
<w:pPr><w:numPr><w:numId w:val="1"/></w:numPr><w:spacing w:after="30"/><w:ind w:left="360" w:hanging="240"/></w:pPr></w:style>
</w:styles>"""

NUMBERING = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{W}">
<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/>
<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>
<w:pPr><w:ind w:left="360" w:hanging="240"/></w:pPr><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/></w:rPr></w:lvl>
</w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>"""

CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>{title}</dc:title><dc:creator>{author}</dc:creator>
</cp:coreProperties>"""


def _clean(text):
    """Text Word accepts: XML-escaped, and without control characters XML can't hold."""
    return escape("".join(c for c in text if c in "\t\n" or ord(c) >= 32))


def _run(text, bold=False, italic=False, color=None, size=None):
    props = ("<w:b/><w:bCs/>" if bold else "") + ("<w:i/><w:iCs/>" if italic else "")
    props += f'<w:color w:val="{color}"/>' if color else ""
    props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else ""
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{_clean(text)}</w:t></w:r>'


def _para(runs, style=None, ppr=""):
    pstyle = f'<w:pStyle w:val="{style}"/>' if style else ""
    props = pstyle + ppr
    return f"<w:p>{'<w:pPr>' + props + '</w:pPr>' if props else ''}{''.join(runs)}</w:p>"


def _block(b):
    kind = b[0]
    if kind == "name":
        return _para([_run(b[1])], "Title")
    if kind == "contact":
        return _para([_run(b[1], color="595959", size=19)])
    if kind == "heading":
        return _para([_run(b[1])], "Heading1")
    if kind == "job":
        _, title, place, dates = b
        tabs = f'<w:keepNext/><w:tabs><w:tab w:val="right" w:pos="{TEXT_W}"/></w:tabs><w:spacing w:before="140" w:after="0"/>'
        runs = [_run(title, bold=True, size=21)]
        if dates:
            runs.append(f'<w:r><w:tab/></w:r>{_run(dates, color="595959", size=19)}')
        out = _para(runs, ppr=tabs)
        if place:
            out += _para([_run(place, italic=True)], ppr='<w:keepNext/><w:spacing w:before="0" w:after="40"/>')
        return out
    if kind == "bullet":
        return _para([_run(b[1])], "ListBullet", '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')
    return _para([_run(b[1])], ppr='<w:spacing w:after="80"/>')


def build(blocks, title="", author=""):
    """The .docx file's bytes."""
    body = "".join(_block(b) for b in blocks)
    sect = (f'<w:sectPr><w:pgSz w:w="{PAGE_W}" w:h="{PAGE_H}"/>'
            f'<w:pgMar w:top="{MARGIN_Y}" w:right="{MARGIN_X}" w:bottom="{MARGIN_Y}" w:left="{MARGIN_X}" '
            f'w:header="432" w:footer="432" w:gutter="0"/></w:sectPr>')
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                f'<w:document xmlns:w="{W}" xmlns:r="{REL}"><w:body>{body}{sect}</w:body></w:document>')
    parts = [("[Content_Types].xml", CONTENT_TYPES), ("_rels/.rels", PACKAGE_RELS),
             ("word/document.xml", document), ("word/_rels/document.xml.rels", DOCUMENT_RELS),
             ("word/styles.xml", STYLES), ("word/numbering.xml", NUMBERING),
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
    import re
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    out = []
    for p in re.findall(r"<w:p>.*?</w:p>", xml, re.S):
        bits = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>|(<w:tab/>)", p, re.S)
        out.append("".join("\t" if tab else t for t, tab in bits)
                   .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    return out
