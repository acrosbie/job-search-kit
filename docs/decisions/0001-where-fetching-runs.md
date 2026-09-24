# 1. Where fetching runs

- **Status:** proposed, awaiting review
- **Date:** 2026-09-24
- **Tested on:** Windows 11 Home, Claude Desktop, Pro plan. Not tested: Apple computers, phones, Team and Enterprise plans.

## Decision

The engine (Python, standard library only) fetches job boards itself, inside Cowork. It runs in whichever Cowork workspace can see the user's folder, normally the one on their own computer. When only the workspace on Anthropic's servers is available, the engine runs there and Claude copies files into and out of the folder. Setup must turn on network access. The local connector and Claude's web fetch are not used for scans.

## What we found

A Cowork session on Windows had **two places to run commands**, and they behave differently:

| | Workspace on Anthropic's servers | Workspace on the user's computer |
|---|---|---|
| What it is | Linux, Python 3.11.15, 2 CPUs, 8 GB | Linux virtual machine the app downloads on first use; Python 3.10.12, 2 CPUs, 4 GB |
| Sees the connected folder | No. Claude reads and writes it through the desktop app, one file at a time | **Yes**, directly, at `~/mnt/<folder name>` |
| Has the plugin's files | Yes | No; Claude copied the script in |
| Can delete files in the folder | n/a | **No**: "Operation not permitted" unless the user grants it |
| Job boards reached, network setting untouched | **0 of 7**; pypi.org only | not ready yet ("workspace still downloading") |
| Job boards reached, network set to All domains | **7 of 7**, 0.6 to 1.2 s each | **7 of 7**, about 0.1 s each |
| Available to a scheduled task with no folder | Yes | No |

The run counter in the folder went 2 → 3 through the file-copy route (run 3) and 1 → 2 through the direct route (scheduled run, 12:31). State survives between sessions either way.

Other routes:

| Route | Result | Why it isn't the scan route |
|---|---|---|
| Local connector (a Node program the plugin starts on the user's computer) | Fetched all 22 jobs in every Cowork run, including from the server workspace | It ran on Node that the user had installed (`C:\Program Files\nodejs`, v22.19.0), not the app's built-in Node (v24.21.0). A stranger without Node probably can't run it. Untested. Also unavailable to a scheduled task with no folder |
| Claude's own web fetch | Read the Greenhouse link in every run, without the user pasting it | Answers through a summarising model: it reported 21 jobs where the board lists 22. Fine for reading one pasted job ad, not for counting or parsing lists |
| Desktop app's Code mode (the `</>` icon) | 7 of 7, on the Windows host itself | Not Cowork. It runs on the host with no sandbox and the user's own Claude Code settings. The first two runs landed here by mistake |

### Evidence log

All runs were on 2026-09-24, Pacific time, using platform-check 0.0.1, then 0.0.2 from run 5.

| Time | Where | Network setting | Boards reached | Notes |
|---|---|---|---|---|
| 11:51, 11:56 | Code mode, Windows host | n/a | 7 of 7 | Not a Cowork result. `python3` is the Microsoft Store shortcut that runs nothing; `python` worked |
| 12:03 | Server workspace | untouched (Pro default) | 0 of 7; pypi.org yes; example.com no | Proxy refused with `Tunnel connection failed: 403`. Folder reached through the copy route |
| 12:08 | Laptop workspace | changed to All domains at some point after 12:03 | 7 of 7, and example.com | Folder visible directly; deleting blocked |
| 12:19 | Both workspaces | All domains | 7 of 7 each | Direct write into the folder |
| 12:31 | Scheduled task with folder, run manually | All domains | 7 of 7 | Ran in the laptop workspace |
| after 12:31 | Scheduled task, no folder, run manually | All domains | 7 of 7 | Server workspace only; no connector; nothing saved |

## Options considered

1. **Engine in Cowork, network allowed (chosen).** One code path and no installs, and it can reach the folder directly on the user's computer.
2. **Local connector on the user's computer.** Works, but only with a runtime the user installed. It would also mean rewriting the engine in Node.
3. **Claude's web fetch.** No setting to change, but the results are summarised, not raw data.
4. **Code mode.** Not something a non-technical user should be sent to.

## What this changes in the design doc

These are proposed edits; the doc itself hasn't been changed.

- **Platform table:** "Code runs in a sandbox that forgets" is incomplete. Add the workspace on the user's computer, which sees the folder directly and runs the engine there.
- **Fetch job boards row:** drop "Fallback: move fetching into a local MCP server" as the main fallback. The fallback is the server workspace plus the file-copy route.
- **Engine:** it must run on **Python 3.10**. The reference `scan.py` imports `tomllib`, which needs Python 3.11, and the laptop workspace has 3.10.12. Either vendor a small TOML reader into the engine, or keep settings in JSON. Phase 1 decides.
- **Engine:** it must **never delete** files in the user's folder, because the laptop workspace can't. Mark postings as gone instead of removing them. (The data model already does this.)
- **Engine:** it isn't in the laptop workspace until Claude puts it there. Proposal: setup copies the engine into the user's folder (for example `Job Search/.kit/engine/`), and the scan skill refreshes it when the plugin version changes.
- **Engine:** store times in UTC with an offset. The laptop workspace's clock is UTC; the server workspace used Pacific time.
- **Skills:** check which workspace they are in. If they find themselves on a Windows or macOS host, they are in Code mode and should tell the user to switch.
- **Skills:** pass the plugin's path explicitly. `${CLAUDE_PLUGIN_ROOT}` is filled into skill text but isn't set as a variable in the shell.
- **Setup step 1** (let Claude reach the job boards) stays, with an open question below.

## Still open

- **Can a Pro user allow just the job-board domains?** The test went straight to All domains, and the options on the Pro settings screen weren't recorded. "Allow every site" is a much bigger ask of a stranger than "allow these 7". Five minutes to check; needed before phase 3 (setup).
- **Does the laptop workspace obey the network setting?** It reached example.com, but by then the setting may already have been All domains.
- **First-run delay:** the laptop workspace was "still downloading" on the first Cowork run and ready 5 minutes later. Setup should expect this.
- The open bug reports about the network setting being ignored ([#93656](https://github.com/anthropics/claude-code/issues/93656), [#30112](https://github.com/anthropics/claude-code/issues/30112)) did not show up here, but setup needs a plain-language path for when a board fetch is refused.

## Sources (read 2026-09-24)

- [Claude Cowork architecture overview](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview): cloud by default; local sessions use a VM; folder access through the desktop app
- [Use Claude Cowork on web, desktop, and mobile](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile): folders reachable only while the desktop app is open
- [Create and edit files with Claude](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude): the Allow network egress setting and its options
- [Get started with Claude Cowork](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork): web fetch isn't limited by the network setting
- [Getting started with local MCP servers](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop): Claude Desktop ships a built-in Node for extensions
- [Plugins reference](https://code.claude.com/docs/en/plugins-reference): `${CLAUDE_PLUGIN_ROOT}`
