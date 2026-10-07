#!/usr/bin/env python3
"""Check a Job Search folder after phase 5b's Cowork run: Morgan's resume checked against
about-me.md, then a clean main resume and a copy tailored to one job, each as a Word file and a PDF.

    python tools/check_resume.py "<folder>" tests/personas/accounting-manager-denver/resume-seeds.json

Prints one line per check and exits 1 if any fails. Reads only; writes nothing.
"""

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "plugins", "job-search", "engine"))
sys.dont_write_bytecode = True

from jobkit import __version__, docx, pdf, resume, settings, store  # noqa: E402


def _find(items, seed):
    pattern = re.compile(seed["match"])
    return [it for it in items if it["kind"] in resume.CLAIMS and pattern.search(it["text"])]


def paragraphs(blocks):
    """The paragraphs a Word file made from these blocks holds (docx.text_of)."""
    out = []
    for b in blocks:
        if b[0] == "job":
            _, title, place, dates = b
            out.append(title + ("\t" + dates if dates else ""))
            if place:
                out.append(place)
        else:
            out.append(b[1])
    return out


def made_text(folder, rec):
    """The text of a made resume's Word file and PDF, joined, and whether the Word file holds exactly
    what its source says."""
    word = pdf_text = ""
    same = None
    for f in rec.get("files", []):
        path = os.path.join(folder, f)
        if not os.path.exists(path):
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        if f.endswith(".docx"):
            word = "\n".join(docx.text_of(data))
            with open(os.path.join(folder, rec["source"]), encoding="utf-8") as s:
                same = docx.text_of(data) == paragraphs(resume.blocks(resume.parse_source(s.read())))
        elif f.endswith(".pdf"):
            pdf_text = " ".join(pdf.text_of(data))
    return word, pdf_text, same


def check(folder, seeds):
    results = []

    def ok(passed, what):
        results.append((bool(passed), what))

    kit = os.path.join(folder, ".kit", "engine", "jobkit", "__init__.py")
    if os.path.exists(kit):
        with open(kit, encoding="utf-8") as f:
            have = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)
        ok(have == __version__, f"the folder's engine is {have} (this repo: {__version__})")

    # 1. The check of Morgan's own resume.
    kept = store.Folder(folder).read_json(os.path.join(folder, resume.CHECK_JSON))
    ok(kept, "the check of Morgan's resume was kept (data/resume-check.json)")
    if kept:
        items = kept["items"]
        ok(kept["lines"] >= 18, f"{kept['lines']} lines checked, {kept['flagged']} flagged")
        for seed in seeds["planted"] + [seeds["true_claim"]]:
            found = _find(items, seed)
            flagged = [it for it in found if not it["ok"]]
            why = ", ".join(sorted({p["kind"] for it in flagged for p in it["problems"]}))
            ok(flagged, f"planted '{seed['id']}' ({seed['kind']}): " + (f"flagged ({why})" if flagged else
               ("found but not flagged" if found else "not found in the transcription")))
        for seed in seeds["accurate"]:
            found = _find(items, seed)
            wrong = sorted({p["kind"] for it in found for p in it["problems"] if p["kind"] in seeds["wrong_kinds"]})
            ok(found and not wrong, f"accurate '{seed['id']}': " + ("not found" if not found else
               ("not called wrong" if not wrong else "called wrong: " + ", ".join(wrong))))

    # 2. Morgan's answers in about-me.md.
    entries = resume.read_about(folder)
    claimed = [e.text for e in entries if e.kind in ("confirmed", "owned")]
    true_claim = seeds["true_claim"]
    ok(any(re.search(true_claim["about"], t) for t in claimed), "the true claim is now confirmed in about-me.md")
    for seed in seeds["planted"]:
        hits = [t for t in claimed if re.search(seed["absent"], t)]
        ok(not hits, f"planted '{seed['id']}' kept out of what's confirmed" + (f": {hits[0]!r}" if hits else ""))

    # 3. The clean resume and the tailored copy.
    records = resume.records(folder)
    stale = {s["source"]: s for s in resume.stale(folder)}
    main = next((r for r in records if not r.get("for")), None)
    tailored = next((r for r in records if r.get("for") == seeds["job"]["key"]), None)
    for label, rec in (("clean resume", main), (f"copy for #{seeds['job']['num']} {seeds['job']['company']}", tailored)):
        ok(rec, f"{label}: made" + (f" from {rec['source']}" if rec else ""))
        if not rec:
            continue
        with open(os.path.join(folder, rec["source"]), encoding="utf-8") as f:
            result = resume.check_text(f.read(), entries)
        ok(result["flagged"] == 0, f"{label}: all {result['lines']} lines trace to about-me.md ({result['flagged']} don't)")
        ok(rec["source"] not in stale, f"{label}: its files are up to date with its source and about-me.md")
        exts = sorted(os.path.splitext(f)[1] for f in rec["files"] if os.path.exists(os.path.join(folder, f)))
        ok(exts == [".docx", ".pdf"], f"{label}: Word file and PDF in the folder ({', '.join(exts) or 'none'}), "
                                       f"{rec.get('pages')} page(s)")
        word, pdf_text, same = made_text(folder, rec)
        ok(same, f"{label}: the Word file holds exactly what its source says")
        text = word + "\n" + pdf_text
        for seed in seeds["planted"]:
            hit = re.search(seed["absent"], text)
            ok(not hit, f"{label}: no '{seed['id']}'" + (f" (found {hit.group(0)!r})" if hit else ""))
        if rec is main:
            ok(re.search(true_claim["made"], text), f"{label}: carries the claim Morgan confirmed")
        if rec is tailored:
            lacks = [m.group(0) for p in seeds["job"]["lacks"] for m in [re.search(p, text)] if m]
            ok(not lacks, f"{label}: nothing the job asks for that Morgan lacks" + (f" (found {lacks})" if lacks else ""))
            if main:
                with open(os.path.join(folder, main["source"]), encoding="utf-8") as a, \
                        open(os.path.join(folder, rec["source"]), encoding="utf-8") as b:
                    ok(a.read() != b.read(), f"{label}: differs from the clean resume")

    # 4. The jobs page brought up to date (0.4.1's catch-up).
    s = settings.load(folder)
    if s.page.get("url"):
        data = store.Folder(folder).read_json(store.Folder(folder).page_json) or {}
        ok(s.page.get("pushed") == data.get("digest"), "the jobs page was brought up to date ([page] pushed)")
    return results


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        seeds = json.load(f)
    results = check(argv[0], seeds)
    for passed, what in results:
        print(("ok    " if passed else "FAIL  ") + what)
    failed = sum(not p for p, _ in results)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
