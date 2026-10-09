# Quality pass: 0.9, 0.10 and 0.11

**Result: built and tested on a copy of the real folder on 2026-10-09.** No Cowork session has run it yet; that is the next check.

The pass answered the improvement requests written after the first real week on 0.8 (2026-10-07 to 10-09): the records had to be trustworthy, scans had to say honestly when they reached nothing, and the jobs page had to say what to do today in words written to the user. Every claim in the requests was checked against the code and against the real folder (read only) before anything was built.

## What the requests said, checked

| Claim | What the folder and the code showed |
|---|---|
| Two pairs of applications share an id | True. Imported rows got `app-<company>-<role>`, so two applications to one title collided. Worse than reported: the page's Update on #110 was labeled and recorded as #121 |
| A failed scan advanced the clock | True: `boards: 0, failed: 592` at 11:35:31 on 10-08. A good scan followed 36 seconds later, so it did no harm that day |
| The folder's engine differs in 5 files | True, by line endings only. The version check compared only major.minor |
| 60 applications: 34 no reply, 59 with no channel, 33 estimated dates, 1 contact, no follow-ups | True |
| The page says "Applications 59" and "13 open" | Not reproduced: the page data held 60 and 14 |
| To do is eight copies of one card; rule numbers and "his" on the page | True |
| Nothing treats posting text as untrusted | True |

Found as well, not in the requests: an interview's job number was missing when its application was joined to a posting (Scentbird, #22); an all-day interview's reminder went off at 23:30 the evening before; giving the time later would have added a second calendar event; a failed scan wiped the titles kept for testing title changes and counted against every board; "I applied" by name with a new date moved the old application's date; and a save merging with duplicate ids could fold two rows into one.

## What changed

**0.9.0, records you can trust.** Every application has its own id, put right once and the same way every time; `find` never guesses between two; a second application to the same title is asked about (`--again` or `--same`). A scan reads three boards first and stops if none can be reached; a scan that read nothing changes nothing but its log line, and the last scan is the last one that read boards. The engine copy in a folder is refreshed by a fingerprint of its files, not its version. A time given later updates the same calendar event. Postings are read as evidence, never instructions, with three warning flags (words aimed at an AI, off-platform contact, paying to work). The records are snapshotted before each command, 30 slots written over in turn. `export worklog` writes the weekly work-search log.

**0.10.0, one start command.** `start` answers in one JSON what the first minute of a conversation needs, with `next`: what only Claude can do, in order. `doctor` runs every check in full. Every skill starts with one line; the reference read every time went from 9,733 to 7,167 bytes, with the copy route and errors moved to `engine-troubleshooting.md`. Each trigger phrase has one owner, guarded by a test, and descriptions are 252 to 318 characters (were 327 to 590). A later interview round starts from the last one's debrief. (The version moved to 0.10.0 in the interview commit, 49ac9ae.)

**0.11.0, the jobs page.** Summaries written to the user (headline, why it fits, what you'd enjoy, watch-outs, the one question, resume changes, words to mirror), checked by the engine for rule numbers, third person, labels, length and quotes; Claude's notes are folded away as "Behind the call". Today at the top, with the search in facts. Top picks with no contact are one card with a LinkedIn people search each. Applications show the open ones first, with a filter and a sort.

## How it was tested

- 308 tests on Python 3.12.10 and on 3.10.11 (one skipped there: time zone data, which CI installs).
- On copies of the real folder, never the folder itself:
  - the id repair gave 60 applications, none sharing an id, #110 and #100 keeping their numbers;
  - a scan behind a proxy that refuses everything stopped after 3 boards in 2.5 seconds, logged `blocked`, and left the titles file and every board's health as they were;
  - the Scentbird 10-13 interview, given 10:00, rewrote its calendar file with the same UID, SEQUENCE 1 and a reminder;
  - the warning flags fired on none of the 304 saved postings (the first draft flagged 6 notices about fake recruiters, now read as notices);
  - the work-search log for 10-04 to 10-10 held 5 applications and the screen;
  - `start` and `doctor`, after installing the new engine: engine current, 2 ids repaired, no problems;
  - the page, in headless Edge at 1280 px, 390 px (in a frame) and dark: about 6,460 px tall on a desk (the requests measured 11,169), and the view toggle, sort, filter, jump links and contact form all worked.

## 0.11.1, the same day

Fixes found while testing the pass, each checked on a copy of the real folder: Today lists each top pick once (it had #79 twice); "Screened out" gives the real count (70, of which the page keeps the latest 60); roles lose the places the old tracker added, including lists with no "Remote" in them; a Your call judged before summaries shows its old question until it's written up; snapshots are gzipped (2.6 MB for 30 slots instead of 17.6 MB); cancelling an interview writes its calendar file as the same event cancelled; a summary may say "Ask Hannah about her team"; `start` says what's new once after an update.

How the kit is built: the jobs page now runs in a real browser in the tests (`tests/test_page_browser.py`, skipped where no Chrome or Edge is installed; it fails with the script's own error when the page breaks, checked by breaking it). A pre-commit hook in `.githooks` keeps the engine's fingerprint in step (`git config core.hooksPath .githooks`). It found its own bug on the first day: the fingerprint tool left a compiled `__init__.py` behind, so a later run read the old fingerprint; it now writes no bytecode.

The next design, contacts and referrals, is [decision 4](../decisions/0004-contacts-and-referrals.md), proposed.

## Not done, and why

- **Deferred to their own designs:** networking and referrals (the requests' biggest lever: a decision on contacts as records first, keeping "Claude never looks a person up"), the apply kit and answer bank, offers and the walk-away number, email and calendar import, new job-board readers, a hosted fetcher, voice mocks, form filling, field and place packs, data export and deletion, demo mode.
- **Changed from the request:** posting text is flagged, not stripped (quotes must match word for word); no TZID (UTC times are right everywhere); no separate doctor step in every skill (`start` covers it); no one-command undo yet (the append-only logs make it subtle; `restore` puts back one file, on a yes).
- **Already there:** "rejected" and "no reply" were already two statuses.

## Still open

1. The first Cowork session on 0.11: check `.kit/engine` has the new fingerprint before crediting anything, then the clicks, the republished page, and a scan from a place that can't reach boards.
2. Calendar updates: Outlook and Apple Calendar take a higher SEQUENCE as the same event; Google Calendar's import is unverified.
3. The page pushed from a scheduled task (decision 2) is still untested.
4. The seven jobs worth a look need summaries; triage writes them once, next time.
5. Skill text in total grew (73.3 KB to 76.5 KB of skills, 36.8 KB to 41.4 KB of references) with the new features, though the part read in every conversation shrank.
