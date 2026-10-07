# Phase 5 results: the checks

**Result: with two overturns seeded on one rule, the weekly review proposed a rewrite, showed its replay, and saved it with its history only after a yes.** Run on 2026-10-06, on Windows, in Cowork, with job-search 0.4.0. The folder was a copy of the made-up accounting manager's folder from phase 4 (`docs/phase-5/how-to-run.md`). `tools/check_review.py` passed all 11 of its checks.

| Pass condition | Result |
|---|---|
| The review proposes a rewrite | It proposed rewriting Rule 4 ("Owns the month-end close"), because the user had overturned it twice (Workiva, Grafana Labs). It quoted their words |
| It shows its replay | Claude re-read the 4 saved jobs Rule 4 had turned away, under the old and new wording. One would change: DoorDash. Fastly would still fail Rule 8, so loosening Rule 4 alone doesn't let it through. The how-to-run guide expected both to pass; Claude's judgment was the right one |
| A "not now" changes nothing | Logged as declined in `data/changes.log`, with no change to `rules.md` |
| Saved only after a yes | One change, logged after the decline. Rule 4 keeps its number, its new wording names the overturns, and a dated "Changes:" line records the user's words and the replay. The old wording is kept in the log |
| Jobs it now passes | DoorDash went back on the waiting list when the user agreed. Fastly wasn't offered |

The same proof runs in code in `tests/test_checks_proof.py`. The engine's half is covered by the tests of replay on the recorded public boards: a pay or place change has a known effect there, such as raising the pay line turning away exactly one job. The guard, the review's facts and changing a rule are tested too. 159 tests pass on Python 3.10 and 3.12.

## What phase 5 built

- **The weekly review.** A scheduled check prepares it, and the user goes through it in chat, one short part at a time:
  - rules overturned twice, and reasons that sound like rules;
  - a spot-check of ten automatic rejects;
  - twenty titles the filter nearly kept;
  - which rules fire, and which never do;
  - the follow-ups due, and board health.

  Once a month it adds outcomes (counts, never odds) and a check of the profile.
- **Tune.** The one path for changing a rule: plain words and evidence, a replay, what flips named, an explicit yes, then a save with history. The engine replays a scan rule exactly. For a `rules.md` rule, the engine finds the postings the change could touch and Claude re-reads them.
- **The engine's guard.** Once there are saved postings, the engine refuses a change to how they're screened unless:
  - it was replayed that day;
  - the user's words are given;
  - each job they applied to or wanted that it would turn away is accepted by name.

  Setup's own first settings are allowed until the user's first decision on a job, because setup's one-board network check would otherwise trip it.
- **Catching up:** an overdue scan, a ready review, board health, and Claude's verdict kept on a job applied to before it was saved.

## What the run found, and what 0.4.1 changed

- **The jobs page in the user's Claude account wasn't updated during the run.** Each skill's last step, "keep the jobs page current", was skipped:
  - when the review stopped part way;
  - after DoorDash went back on the list;
  - in the check that prepared the review.

  Now `page.json` carries a fingerprint, `page --pushed` records what was last sent, and catch-up sends the page whenever it's behind.
- **"Set up a weekly review" created the task but didn't record it in the user's settings,** so a missed review couldn't be noticed. Setup, scan and review now share `reference/schedules.md`, which records it.

## Not settled

- **The page-behind catch-up hasn't run in Cowork yet.** The follow-up check ran before auto-sync delivered 0.4.1; the folder still had engine 0.4.0. In that run Claude kept the page current on its own: it showed the review notice and DoorDash. The new mechanism is covered by tests, and it will meet Cowork in the next phase's runs.
- **Can a scheduled check update the page?** A review was prepared at 18:06, but the page wasn't updated. Whether that came from a scheduled run, and whether a scheduled run can reach the page at all, wasn't confirmed. Either way, 0.4.1's catch-up covers it the next time the user talks to Claude.

## The reference system

The reference system's repository was read only. Its file listing and `git status` were identical before and after the phase (`Job Search (test)\phase5\career-*-before.txt` and `-after.txt`).
