# Interview files

The interview skill writes these in the user's folder, under `interviews/`:

| File | What it is |
|---|---|
| `interviews/<Company> - <Role>/prep.md` | The prep sheet for one interview, with its debrief added afterwards |
| `interviews/<Company> - <Role>/<date> <screen\|interview>.ics` | The calendar file the engine writes when an interview is recorded |
| `interviews/stories.md` | The story bank |
| `interviews/quick-reference.md` | One page to have open during a call |

The interview itself is kept on its application (`run.py track <id> screen --on …`). `run.py interview list` lists every interview not yet gone through. `due` says which are soon (`interviews_soon`) and which are waiting for a debrief (`debrief_due`).

## The format

Markdown, with `##` sections. Under a claim section, each line or bullet is a claim about the user. It carries `from:` lines underneath, quoting `about-me.md` exactly, as a resume does (`resume-format.md`). Other sections are free text.

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
