# Phase 2 results: scan and triage in Cowork

**Result: the plugin works in Cowork, and its triage agreed with a real user's final calls on 15 of 20 postings on the first run.** Every disagreement was explained. Three came from the converted rules' wording and were fixed. Two were deliberate caution, which the user chose to keep. A sixth posting matched on verdict but cited a different rule, which was accepted. Run on 2026-10-05, Windows 11, in Cowork with the job-search plugin 0.1.0.

## The run

| Step | What happened |
|---|---|
| "any new jobs?" | The engine copied itself into the user's folder (`.kit/engine`) and ran in Cowork's workspace on the user's computer. It read 584 boards (6 didn't answer) and 56,351 postings; 211 matched, 31 were new, and 21 were rejected automatically |
| "go through them" | Triage recorded a verdict on all 51 waiting postings (the 20 test postings plus 31 genuinely new ones): 8 worth applying, 10 your call, 33 not a fit, each with a quoted line |

## Agreement with the user's final calls

The answer key was the user's own decision on each posting where they made one on the reference system's page, otherwise the reference triage's. It was kept outside the folder Claude could see.

| | Count |
|---|---|
| Test postings | 20 (4 worth applying, 2 your call, 14 not a fit across 9 rules) |
| Verdicts that agreed, first run | **15** |
| Not-a-fit verdicts citing the same rule | 7 of 8 |
| Postings where the user had overruled the reference triage | 5; the kit matched the user on 4 |

## The five disagreements, and what was done

| Kind | Count | Cause | Outcome |
|---|---|---|---|
| Kit said Your call, answer was Worth applying | 2 | The posting asked for experience the profile doesn't mention either way, or had a line that might trip the level rule. The kit asked instead of guessing | **Kept,** the user's choice: when the profile doesn't say, ask |
| A years bar rejected a posting | 1 | "10+ years" against about nine was stretched to fit the unmet-requirement rule | **Fixed** in the user's rules (a years bar is a note), and in the triage skill for everyone (0.1.1: reject only on what a rule actually says) |
| A hands-on technical requirement was asked about, not rejected | 1 | The converted technical-gate rule didn't name deep hands-on technical work | **Fixed** in the user's rules |
| An escalation-owner role passed | 1 | The user's reason (after-hours escalations) wasn't written down anywhere | **Fixed** in the user's rules, narrowly: replayed over the saved postings, it flips nothing the user applied to or wanted |

The user chose not to re-run triage on the three fixed postings. Verdicts after the fixes are therefore not measured.

## Not measured

- **Usage cost.** It depends on the model each user picks, and isn't a concern at this stage (the user's call).
- **Apple computers, phones, Team and Enterprise plans**, as in phase 0.

## What phase 3 (setup) inherits

- **The profile format** (`plugins/job-search/reference/profile-format.md`) works as triage input.
- **Rules need "doesn't count" notes.** Two of the three fixes were look-alikes a rule shouldn't catch (a years bar, a line that only sounds like a requirement). Setup should ask about the common ones when it writes each rule.
- **Asking beats guessing** when the profile is silent. Setup should record the facts postings most often ask about, so triage has fewer questions to put to the user.
