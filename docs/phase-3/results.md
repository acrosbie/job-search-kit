# Phase 3 results: setup

**Result: a made-up job seeker in a different field got through setup without opening a file, and their first scan found jobs in their field.** The persona was an accounting manager in Denver (`tests/personas/accounting-manager-denver`), played in Cowork from an answer sheet on 2026-10-06, using job-search plugin 0.2.0.

| Pass condition | Result |
|---|---|
| Setup completes, no file opened | Yes, in two sittings: the first stopped during step 6, and "carry on" resumed it from the progress file, as designed |
| All five profile files written and valid | Yes: about-me, what-i-want, rules (9 rules, 9 flags), settings, companies |
| Mismatches between resume and LinkedIn asked about, not guessed | Yes: both the title and the team size (6 against 4) are under Corrected, with the persona's answers |
| First scan finds jobs in their field | Yes: 584 of 589 boards read, 154 accounting and finance postings matched, 80 new, 74 screened out for location |
| First triage together | 10 judged (2 worth applying, 2 your call, 6 not a fit); the persona agreed with all 10 |
| Daily check scheduled | Yes: 9:00 am Denver time, with the folder attached and prompt "any new jobs?" |
| START HERE.md | Yes |

## What setup did well without being told

- It noticed "AR" in place names ("Little Rock, AR") matching the "accounts receivable" title words, and fixed the patterns.
- Its commute lists guard against same-named towns in other states: Aurora, Lakewood, Englewood and Golden are matched only when they're not followed by another state.

## Not exercised in this run

- **Title calibration's adjustment loop.** The persona accepted the first 20 sample titles, so no change was tried. The commands behind it, `titles` and `try-titles`, are covered by unit tests and were checked on a live scan's 54,670 titles before the run.
- **Adding a company by name.** The persona skipped it. `discover` and `companies add` are covered by unit tests, and the answer sheet's company (Ibotta, on Ashby) was confirmed reachable before the run.

## Fixed during this phase

- The US places pack didn't treat Bay Area cities as elsewhere in the country, because in the reference system they sat only in its user's commute lists. Found by the live check before the run.
- **The engine's version wasn't raised with the plugin's,** so an existing user's copy of the engine would never have been refreshed. The engine is now 0.2.0 in plugin 0.2.1, and a guard test ties the two together.
