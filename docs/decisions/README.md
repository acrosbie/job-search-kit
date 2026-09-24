# Decisions

Each file records one decision: what was decided, the evidence, what it changes in the design doc, and what's still open. A decision is marked **proposed** until it has been reviewed.

| # | Decision | Status |
|---|---|---|
| [1](0001-where-fetching-runs.md) | The engine fetches job boards inside Cowork, in the workspace that can see the user's folder; setup turns network access on | proposed |
| [2](0002-how-the-jobs-page-works.md) | The jobs page is a Claude artifact whose buttons save; a plain page in the folder is the backup | proposed, one question for review |
| [3](0003-how-checks-are-scheduled.md) | Periodic checks are scheduled tasks with the folder attached, and run the check themselves | provisional, overnight test running |

All three come from the phase 0 platform check (`plugins/platform-check`, run with `docs/platform-check/how-to-run.md`) on 2026-09-24, on Windows only.

## Found along the way

- **Code mode isn't Cowork.** The desktop app's `</>` icon runs Claude Code directly on the computer, with no sandbox and the user's own settings. A scan run there passes every test and proves nothing about Cowork. Skills should notice when they're on a Windows or macOS host and tell the user to switch.
- **Plugin updates arrive with a delay.** A fix pushed at 12:11 wasn't picked up by the manual Update button ("latest"). With auto-sync on, it arrived a few minutes later.
- **Installing from the repo works.** Customize, Plugins, Add marketplace, `acrosbie/job-search-kit`, Install. The ZIP backup wasn't needed.
