# Phase 4 results: the loop

**Result: a scripted week in Cowork left every file and the jobs page correct.** It took a second run: the first, with job-search 0.3.0, showed that LinkedIn can't be read and that a click on the page gave no clear sign it had worked. Version 0.3.1 fixed both, and the re-test passed. Both runs were on 2026-10-06, on Windows, in Cowork, on a copy of the made-up accounting manager's folder from phase 3 (`docs/phase-4/how-to-run.md`).

| Pass condition | Result |
|---|---|
| A pasted LinkedIn link | Saved from the posting's text, which the user pasted when asked, as `manual-mv-transportation-4471959130`, and joined to the application already recorded for it |
| Three applications | MV Transportation (8 days before, through LinkedIn, a top pick), Fivetran (24 days before), Step (22 days before), each with its date, how it was sent and whether it's a top pick |
| One reply | Fivetran's phone screen recorded as `screen`. Though past day 21, it was never closed |
| One day-21 close | Step, closed as presumed rejected by the engine, dated its day 21 |
| Follow-up routing | MV Transportation, a top pick with nobody known, routed to "find a person" |
| The jobs page | Made in the user's own Claude account. Kept current by writing its data into the page's storage (`[page] route = storage`). Shows every application as recorded |
| Clicks read back | All 9 clicks across both runs read back in a new task, recorded once each as the user's, and marked done in the page's storage |
| Files | `tools/check_week.py`: 32 of 33 checks. The one difference is the click count (9, not the 7 the script asked for): the user also skipped a second job and pressed "I applied" on another, which recorded correctly |

The engine side is also proven without Cowork by `tests/test_week.py`: three weeks replayed on the recorded public boards, with every file checked. 115 tests pass on Python 3.10 and 3.12.

## What the first run found, and what 0.3.1 changed

- **LinkedIn job pages can't be read from Cowork.** Claude's web fetch got nothing usable, so Claude recorded the application by company name, with no posting or verdict. Now add-job doesn't try: it asks for the posting's text straight away, says how to copy it, and suggests the company's own apply link as an alternative. A posting saved after the user said they applied is joined to that application. Claude Code's web fetch, in this repository's own session, did read the same link, so a check made outside Cowork doesn't count here.
- **A click on the page didn't visibly land.** One job was clicked five times in 12 seconds (want, skip, skip, skip, want). All five were recorded in order, so the job ended right, but four of them were logged as the user overturning a verdict. Phase 5's review counts those. Now a saved choice moves the job into a boxed "Your choices" section at the top, with a message and an Undo. A second click on a job replaces the first. `record-choices` records only the last click on each job.
- **An answer was recorded against the wrong application.** Step was saved as "through LinkedIn, a top pick", the MV Transportation answers. Now the track skill names the company in each question and lists every application back with how it was sent and whether it's a top pick. The page shows both. In the re-test, the user corrected Step in one sentence.

## Decided by the run

- **How the page stays current:** by writing `page.json` into the page's own storage. This was decision 2's untested item; it works.
- **One page per user:** each is made in the user's own account, with clicks under `data/users/<id>/`. A page that uses storage can't be shared publicly, so one kit page couldn't serve strangers.
- **LinkedIn:** always pasted text.

## Not settled

- **Can a scheduled check bring the page up to date?** The optional step wasn't run. Until it is, the kit promises only that the page shows when it was last brought up to date, and that it catches up the next time the user talks to Claude.
- **Claude's verdict on a job the user applied to before it was saved isn't recorded.** The engine refuses to overwrite the user's own decision, and "applied" is one. The verdict is given in chat but not kept. Phase 5's outcome check, which compares replies against verdicts, will need it. Decide there.
- **The pasted LinkedIn posting's location came out as "not stated".** LinkedIn shows the place above "About the job", where the copied text started. Claude rightly didn't guess it, but the add-job skill could ask for the place when it's missing.

## The reference system

`C:\Users\aidan\career` was read only. Its file listing and `git status` were identical before and after the phase (`Job Search (test)\phase4\career-*-before.txt` and `-after.txt`).
