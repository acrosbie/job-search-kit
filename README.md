# job-search-kit

A free, open-source plugin for Claude Cowork that helps a job seeker who has never used a terminal set up and run an AI-assisted job search. It finds postings on public job boards, screens them against rules built from the person's own background and wishes, and tracks what they apply to. Everything personal stays with the user, in a folder on their own computer and their own Claude account, never in this repo.

**Status: phase 1 done, awaiting review.** The engine in `plugins/job-search/engine/` fetches public job boards and screens postings, and matched the scanner it was ported from with 0 differences over 590 boards (`docs/phase-1/equivalence.md`). Phase 0's platform decisions are in `docs/decisions/`. The plugin and its skills come in phase 2.

Tests: `python -m unittest discover -s tests -t .` (Python 3.10 or later).
