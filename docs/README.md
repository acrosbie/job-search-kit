# Docs

**Using the kit**
- [Getting started](install.md): install, set up, and what to do when something goes wrong.

**How it's built**
- [Decisions](decisions/README.md): where the engine runs, how the jobs page saves clicks, how checks are scheduled, and the evidence for each.
- [The engine](../plugins/job-search/engine/README.md): every command, and the format of every file in a user's folder.
- [Job-board sites](../plugins/job-search/reference/job-board-domains.md): the sites the engine reads, for network settings.

**The build log**, each phase with how it was tested and what it showed:

| Phase | What it proved |
|---|---|
| [Platform check](platform-check/how-to-run.md) | Cowork can fetch job boards, save clicks on a page, and run scheduled checks |
| [1. Engine](phase-1/equivalence.md) | 0 differences from the scanner it was ported from, over 590 boards |
| [2. Scan and triage](phase-2/results.md) | Triage agreed with a real user's final calls on 15 of 20 postings |
| [3. Setup](phase-3/results.md) | A made-up job seeker in another field got through setup without opening a file |
| [4. The daily loop](phase-4/results.md) | A pasted job, applications, a reply and a day-21 close left every file right |
| [5. The weekly review](phase-5/results.md) | A rule overturned twice was rewritten, tried on saved jobs, and saved only after a yes |
| [5b. Resume help](phase-5b/results.md) | Every planted inflated claim flagged; the resumes made trace line by line |
| [6. A real search](phase-6/results.md) | The search the kit was built from now runs on it; what its data showed is fixed |
