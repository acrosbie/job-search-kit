# Interview files

The interview skill writes these in the user's folder, under `interviews/`:

| File | What it is |
|---|---|
| `interviews/<Company> - <Role>/prep.md` | The prep sheet for one interview, with its debrief added afterwards |
| `interviews/<Company> - <Role>/<date> <screen\|interview>.ics` | The calendar file the engine writes when an interview is recorded |
| `interviews/<Company> - <Role>/company.md` | The company brief, every line with its source and date |
| `interviews/<Company> - <Role>/<date> <stage> cheat sheet.md` | One round's cheat sheet, at most 60 lines |
| `interviews/stories.md` | The story bank, each story with its `tags:` |
| `interviews/quick-reference.md` | One page to have open during a call |

The interview itself is kept on its application (`run.py track <id> screen --on …`). One that moved: `run.py interview cancel <id> --on <old date>`, then record it again on its new day; one called off: just the cancel. Its calendar file is written again as the same event, cancelled: tell the user to double-click it to take the interview off their calendar. `run.py interview list` lists every interview not yet gone through. `due` says which are soon (`interviews_soon`) and which are waiting for a debrief (`debrief_due`).

## Who's asking

| Asker | What they probe |
|---|---|
| recruiter | Fit, pay, logistics, why this role and why now; one or two questions on the work |
| hiring_manager | How you'd do the job: "how would you...", the gaps, the first 90 days |
| head_of_function | Whether you've done their kind of work: their own field from the inside (for a head of CX, the frontline years), how you lead, and how you'd work with them |
| executive | Judgment and the business: why this matters to the company, trade-offs, a short version of each story |
| peer | Working together day to day: hand-offs, disagreements, what you'd change |
| panel | Each person's own angle; one story told several ways |

## The format

Markdown, with `##` sections. A later round's sheet adds `## From your last round` after At a glance: free text, from the earlier `## Debrief` sections. Under a claim section, each line or bullet is a claim about the user. It carries `from:` lines underneath, quoting `about-me.md` exactly, as a resume does (`resume-format.md`). Other sections are free text.

```
# Acme: recruiter screen, Thu 8 Oct, 10:00

## At a glance
Phone, 30 minutes, with Dana (recruiter). A first screen: fit, pay, logistics.

## Opener
I run a month-end close that I cut from 10 business days to 6, with a team of 4.
from: Cut the month-end close from 10 business days to 6
from: 4 direct reports at Peakline

## Answers
### Why are you looking?
...
from: ...

## Gaps
...

## Questions to ask
- What does success look like in the first 90 days?

## Do not say
- "Senior Accounting Manager" (corrected: Accounting Manager)
```

**Claim sections:** headings that begin Opener, Answers, Stories, Gaps, Strengths or Caveats. `###` questions or story names inside them are headings, not claims; the lines under them are.

**Free sections:** everything else, including At a glance, The company, The role, Comp, Logistics, Questions to ask, Do not say, Ask them and Debrief. Their lines aren't checked. Keep them to facts from the posting, cited pages, `what-i-want.md`, or the user's own words.

## The check

`run.py interview check FILE` checks every claim line with the resume's rules. The problem kinds are listed in `resume-format.md`: `no_source`, `source_not_found`, `too_short`, `unconfirmed`, `corrected`, `alongside_as_owned` and `number`, plus any `flag:` you add. A prep sheet is ready when `flagged` is 0.

Two things only you can catch:
- an answer that's true line by line but leaves a wrong impression;
- a company fact that isn't in the posting or a page you cited.
