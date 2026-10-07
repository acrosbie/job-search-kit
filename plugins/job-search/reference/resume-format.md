# The resume source

A resume is made only when the user asks (the resume skill). Claude writes it as a plain source file in their folder, and the engine makes the Word file and the PDF from it. Every line that says something about the user rests on words from `profile/about-me.md`. The engine checks that before it makes anything.

## Where it lives

| File | What it is |
|---|---|
| `resume/your-resume-<YYYY-MM-DD>.md` | The user's own resume, transcribed word for word, for the check |
| `resume/main.md` | The clean main resume |
| `resume/<Name> resume.docx`, `.pdf` | The main resume as made, beside its source |
| `resume/<Company> - <Role>/resume.md` | A copy tailored to one job, with its Word file and PDF beside it |

The user never opens the `.md` files. They get the Word file and the PDF.

## The format

```
# Morgan Reyes
Denver, CO · morgan.reyes@example.com · (555) 010-0142

## Summary
Accounting manager with ten years across public accounting and in-house finance.
from: Years in accounting: since Aug 2015 (Morgan's words: "ten years")

## Experience
### Accounting Manager | Peakline Software, Denver, CO | Mar 2021 – Present
from: Accounting Manager, Peakline Software, Denver, CO, Mar 2021 to present
- Lead a team of 4 covering the general ledger, accounts payable, payroll accounting and the monthly close.
  from: 4 direct reports at Peakline
  from: The team covers the general ledger, accounts payable, payroll accounting and the monthly close

## Education
BS, Accounting, Front Range State University, 2015
from: BS, Accounting, Front Range State University, 2015
```

- **The first line is `# ` and the name.** Anything after a comma (", CPA", ", MBA") is a claim, and needs a `from:` like any other.
- **Contact lines** come next, up to the first `## `. They come from the user's own resume and aren't checked: city, email, phone, LinkedIn.
- **`## `** starts a section. Use the user's own sections and order.
- **`### Title | Company, Place | Dates`** is a job. The dates go on the right of the first line.
- **`- `** is a bullet. Any other line is a line of text: a summary, a degree, a list of tools.

## `from:` lines

Under each line, one `from:` for each claim it rests on:
- **Copy the words exactly** from `about-me.md`: from Confirmed (the claim, not "how it was established"), the "Now" side of Corrected, Owned hands-on, Worked alongside, or Facts postings check.
- **At least three words**, or a whole entry, so it's clear which claim it is.
- **Every number in the line must be in the claims it cites.** "10 to 6 days" needs a claim that says 10 and 6, and "a team of four" needs one that says 4.

## What the check catches

`resume check` names each problem by its kind:

| Kind | What it means | What to do |
|---|---|---|
| `no_source` | Nothing in about-me.md says this | In their own resume: ask about it. In one you're making: leave it out |
| `source_not_found` | The quoted words aren't in about-me.md | Copy them exactly, or the claim isn't there |
| `too_short` | The quote is too short to tell which claim it is | Quote more of it |
| `unconfirmed` | It rests on "Not confirmed yet" | Ask about it. Never use it until they confirm it |
| `corrected` | It brings back something that was corrected, or quotes the "Was" side | Use what it was corrected to |
| `alongside_as_owned` | It starts with Led, Owned, Built, Managed or the like, but rests on something they worked alongside | Say what they did: "Partnered with …", "Worked with …" |
| `number` | A number its sources don't have | Use their number |

The engine can only check these by rule. Read every line yourself as well. When checking the user's own resume, add a `flag:` line under any line whose wording goes further than its source:

```
- Led the annual external audit.
  from: Prepared schedules and managed requests for Peakline's annual external audit
  flag: inflated: about-me.md says you prepared the schedules and handled requests, not that you led it
```

Use these kinds for `flag:`:
- `inflated`: wider or bigger than its source;
- `contradicts`: about-me.md says otherwise;
- `mismatch`: a title or date differs;
- `not_in_profile`: a claim about-me.md doesn't have.

The words after the kind are for the user, so write them plainly.

`resume render` makes nothing while any line has a problem or a `flag:`. A resume you make never carries a `flag:` line: fix the line, or leave it out.

## The layout

- One column of real text, standard headings, and no tables or text boxes, which is what hiring systems read best.
- Arial in the Word file and Helvetica in the PDF, on US Letter.
- One page is best for most people; two is fine for a long career. `resume render` says how many pages the PDF runs to.
- The PDF can only show Western European letters. If a name or a line has others, the Word file is still made, and `warnings` says why there's no PDF. Tell the user they can save the Word file as a PDF from Word or Google Docs.
