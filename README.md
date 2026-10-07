# job-search-kit

A free, open-source plugin for Claude Cowork that helps a job seeker who has never used a terminal set up and run an AI-assisted job search. It finds postings on public job boards, screens them against rules built from the person's own background and wishes, and tracks what they apply to. Everything personal stays with the user, in a folder on their own computer and their own Claude account, never in this repo.

**Status: phase 5 done.** To try the kit, follow [docs/install.md](docs/install.md). Setup, scan, triage, tracking and a weekly review run in Cowork: the weekly review proposed rewriting a rule the user had overturned twice, replayed it over their saved jobs, and saved it with its history only after a yes (`docs/phase-5/results.md`); a scripted week of use left every file and the user's jobs page correct (`docs/phase-4/results.md`); a made-up job seeker in a different field got through setup and found jobs in their field (`docs/phase-3/results.md`); triage agreed with a real user's final calls on 15 of 20 postings (`docs/phase-2/results.md`); and the engine matched the scanner it was ported from with 0 differences (`docs/phase-1/equivalence.md`). Next: resume help on request (phase 5b), then a real job seeker (phase 6).

Tests: `python -m unittest discover -s tests -t .` (Python 3.10 or later).
