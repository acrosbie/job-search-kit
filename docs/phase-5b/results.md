# Phase 5b results: resume help, on request

**Result: proven in three runs.** Morgan's updated resume had 10 inflated or unconfirmed claims planted among accurate lines, plus one new claim that's true.
- **The check:** every run flagged all 11 and called no accurate line wrong.
- **The answers:** the third run recorded Morgan's answers in `about-me.md`. The first two lost them.
- **The two resumes:** the clean resume and a copy tailored to #72 Grafana Labs, each in Word and PDF, traced line by line to `about-me.md`. Neither carried a planted claim Morgan denied, nor anything Grafana asks for that Morgan lacks.
- **The look:** after a polish pass, the user judged the jobs page and the resume good.

All three runs were in Cowork on Windows, on 2026-10-06 and 07, each on a fresh copy of Morgan's folder from phase 5 (`docs/phase-5b/how-to-run.md`). The run checker is `tools/check_resume.py`.

| Run | Plugin | Checker | What it showed |
|---|---|---|---|
| 1 | 0.5.0 | 48 of 51 | The check worked. The user answered every question, and none reached `about-me.md`, so the clean resume left out the claim Morgan confirmed. The page catch-up from 0.4.1 ran: the page was republished and marked up to date (open item 1, settled). The jobs page and the resume looked "very very rough" |
| 2 | 0.5.1 | 65 of 67 | Polished page and resume. The engine now refused the clean resume while the answers were unrecorded, and Claude got round it by passing the user's request, "make me a clean resume", as the reason for not answering. The tailored copy for #72 passed every check |
| 3 | 0.5.1 (auto-sync lag; 0.5.2 was out) | 43 of 51 | Answers recorded as they were given: 5 corrections, 5 confirmations, and three numbers asked about directly. The 8 failures are three planted claims the user confirmed, against the answer sheet, and the tailored copy, which was skipped because run 2 had passed it. So the kit did what it should: a claim the user confirms is theirs |

## What 5b built

- **The check:** Claude transcribes the user's resume word for word, quotes the `about-me.md` words each line rests on, and flags what goes further. The engine (`resume check`) catches by rule:
  - a line with no source, or one that isn't there;
  - something unconfirmed;
  - a corrected claim coming back;
  - something worked alongside, claimed as owned;
  - a number its sources don't have.

  Claude catches the rest by judgment. In all three runs it caught the three plants only judgment can see (leading the audit, Tableau dashboards, SOX).
- **A clean resume and a tailored copy,** each made by the kit's own code as a Word file and a PDF (`resume render`), and only when every line traces.
- **Only on request.** A guard test keeps every other skill from making a resume.
- **The look:**
  - one column of real text;
  - navy name and section headings, a navy rule under the name;
  - sized to fill the page: Morgan's grew to about 11pt on one page.
- **The jobs page,** rebuilt:
  - urgent first, with a sticky bar of counts;
  - the jobs that need a decision as full cards;
  - applications with a 21-day clock;
  - the new jobs as compact rows with a filter.
- **A resume that no longer matches** `about-me.md` is offered for an update in one line, when catching up.

## What the runs changed

- **0.5.1:** the polish pass. The skill saves each answer as it's given. The engine refuses the clean resume while the check's answers are missing.
- **0.5.2:** the escape hatch run 2 used (`--why`) is gone. The clean resume needs `about-me.md` to have gained an entry since the check: an answer, a correction, or the line recorded as not answered.
- **Plugin 0.5.3:** before a sum of money, a percentage or another measured result is confirmed, Claude asks how it was measured, and records the answer. Run 3's "$250K" was confirmed with a bare "confirmed".

207 tests pass on Python 3.10 and 3.12, including the proof as a test (`tests/test_resume_proof.py`).

## Not settled

- **0.5.2's guard and 0.5.3's money question haven't met Cowork.** Run 3 ran before auto-sync delivered them, and didn't need the guard. The next real use will exercise them.
- **The Word file has been looked at, not tested in Word itself.** The user judged it good; python-docx reads it as built.
- **Where the engine ran** wasn't recorded, so whether a Word file can be copied into the folder from a cloud-only session is still unknown. The PDF is plain ASCII, so it copies either way.

## The reference system

The reference system's repository was read only during planning, on 2026-10-06. Its "after" listing differs from the "before" one (`Job Search (test)\phase5b\career-*-before.txt` and `-after.txt`). Every change is dated 2026-10-07 between 10:17 and 12:33, from the owner's own use of it: a scan, the pipeline, the verified facts and an interview-prep file. This session wrote nothing there.
