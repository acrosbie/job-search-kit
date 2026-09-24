# 3. How checks are scheduled

- **Status:** proposed, awaiting review
- **Date:** 2026-09-24
- **Tested on:** Windows 11 Home, Claude Desktop, Pro plan. Not tested: Apple computers, Team and Enterprise plans.

## Decision

Periodic checks are **Cowork scheduled tasks with the user's folder attached**, and they **run the check themselves** rather than only reminding the user. When one runs, it can do the whole job with nobody there: fetch the boards, read and write the folder, record the result. The kit assumes these tasks **run only while the computer is on and the Claude app is open**, and says so to the user. Every session also starts by catching up: if the last scan is older than the schedule says it should be, Claude runs one before anything else.

Scheduled tasks **without** a folder aren't used for checks, because they can't save anything.

## What we found

| | Task with the folder attached | Task with no folder |
|---|---|---|
| Where it ran | The Linux workspace on the user's computer | The workspace on Anthropic's servers only; no laptop workspace was available |
| Reached the folder | **Yes, directly.** The run counter went 1 → 2 | No. "Results live only in this task's log" |
| Job boards (network set to All domains) | 7 of 7 | 7 of 7 |
| Local connector | Worked | Not available |
| Result kept | `scheduled-log.md` and a run file in the folder | Only in the task's own history |

Both were started with **Run now** on 2026-09-24, just after 12:31 Pacific, using platform-check 0.0.2. Both finished; whether either paused to ask for approval, and which approval options the form offered, weren't recorded.

### What the docs say, and why it needed testing

- The help article says scheduled tasks "run remotely… even when your computer is asleep or the Claude Desktop app is closed", and "can't be tied to a folder on your computer". But its own setup form has an optional folder, with the note "If a scheduled task requires local files or apps, it will only run locally" ([Schedule recurring tasks](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork), read 2026-09-24).
- An open bug report says every scheduled task is created local-only: it runs only while the app is open, and a run that falls due while the app is closed happens at next launch ([#80913](https://github.com/anthropics/claude-code/issues/80913), open, last updated 2026-09-17).

The results above fit both documents: the task with no folder ran remotely, and the task with a folder ran on the computer. What they don't show yet is **when** a folder task runs if nobody is there.

## Options considered

1. **Folder-attached task that runs the check (chosen).** It does the real work and keeps everything in the folder. It probably depends on the computer being on.
2. **Remote task that only reminds the user**, which was the design doc's fallback. It runs even when the laptop is off, but it can't save anything, so a check only happens once the user opens Claude.
3. **Both:** a folder task that runs the check, plus a remote reminder when the folder task hasn't run for a while. Worth adding only if folder tasks turn out to run too rarely in real use.

## Not tested, by choice

Whether a folder task runs, catches up or is skipped while the laptop sleeps or the app is closed. It was left out because the design doesn't depend on it: each session catches up first, and the kit only promises that checks run while the computer is on. If it later turns out tasks do run unattended, that's a bonus, and the wording can relax.

## What this changes in the design doc

These are proposed edits; the doc itself hasn't been changed.

- **"How the schedule reaches a local folder":** replace "the scheduled task's job is to prompt the user" with a folder-attached task that runs the check, because phase 0 showed such a task reaches the folder directly. Add the "runs while your computer is on" caveat.
- **Setup, periodic checks step:** create each scheduled task **with the folder attached**, and choose the approval option that doesn't stop to ask. Record which option that is on the form before phase 3.
- **Working loop:** add the catch-up rule at the start of each session.
- **Platform table:** "Scheduled tasks can't see the local folder" becomes "Scheduled tasks with a folder attached run on the user's computer and can see it; ones without a folder run remotely and can't save anything."

## Sources (read 2026-09-24)

- [Schedule recurring tasks in Claude Cowork](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork)
- [Use Claude Cowork on web, desktop, and mobile](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile): "Scheduled tasks run in the cloud, so they no longer need your computer to be awake"
- [anthropics/claude-code#80913](https://github.com/anthropics/claude-code/issues/80913): scheduled tasks always created local-only
