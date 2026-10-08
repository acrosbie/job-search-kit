# Phase 6 results: a real search moved onto the kit

**Result: moved on 2026-10-07, and what real data showed is fixed (engine 0.6.0 and 0.8.0).** No Cowork session has run on the moved folder yet.

The design doc's phase 6 was a real job seeker, not the author, setting the kit up. It became something earlier and narrower: moving the search the kit was built from onto the kit, so a real search runs on it every day. That tests the importer and the kit against a real search's data. A stranger setting it up from the README alone is still to do, and moves to phase 7.

## What moved

`tools/import_reference.py` converted the reference system's files into a new, empty folder: 601 job boards, 294 saved postings with their descriptions, 282 decisions and 59 applications. The reference system was read only, and listed before and after every step to show it unchanged.

## What real data showed

**Found moving it (fixed in 0.6.0):**
- Clicks on the file page not yet sent to Claude were lost when the page was rebuilt.
- A job decided without a note showed Claude's old reason as "You said".
- A job whose place changed lost its other flags (contract, days on site, applied).
- "Gone" went by key prefix, so one board could retire another's jobs.
- Day counts on the page froze when it was built.
- Three jobs carried an old "closed" status the kit doesn't have, and showed nowhere.

**Found in a review of the kit with the data in it (fixed in 0.8.0):**
- **The import:** 51 of 59 application titles ended "(posting)", from the old table's link text, and fit and level kept the table's bold, so "Strong" and "**Strong**" counted apart. How each application was sent was blank on all 59: the old table had no column for it. Fixed in the importer, and the folder repaired in place, through the engine's own store, with before and after listings.
- **Pay:** the reader missed "between $X and $Y", cents, "USD" without "$", and hourly pay, so the page said "pay not stated" on jobs that state it; and a bonus range could be read as the pay. On this search, 21 of 294 saved jobs gained a pay range and 2 read their base pay instead of total cash. No job still open would now meet its pay line.
- **Places:** state codes that are also country codes (DE, IN, IL, CA) let jobs abroad pass as American: 30 of the 57,286 listings read that day.
- **Records:** a long scan saved over changes made while it ran; a new job could join an old application by a loose title; two long roles could share an application id; a failed description fetch was saved and auto-rejected for good.
- **Skills that skipped steps:** "any new jobs?" never heard of an interview soon; a screen could be booked without its day; overturns were grouped by how a note was worded. Each is now a check in the engine (`mark --rule --quote`, `track --on`, `apply --channel --top-pick`, a written debrief).

## Still open

1. The first Cowork session on the moved folder: it installs the engine (`.kit/`), and its runs are checked from the folder's files, engine version first.
2. How each open application was sent, asked once when catching up (planned).
3. Using it from a phone, through Dispatch: untested.
4. A stranger installing and setting up from the README alone (phase 7).
