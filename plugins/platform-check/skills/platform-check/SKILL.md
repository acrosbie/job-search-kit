---
name: platform-check
description: Phase 0 test for job-search-kit. Use when the user says "run the platform check", "run the platform check in scheduled mode", pastes a line starting "Platform check choices:", asks to "make the jobs page artifact", or asks to "read my choices from Jobs page test".
---

# Platform check (test)

This plugin is a throwaway test. Its only job is to find out how this Claude session runs code, reaches the network, reads and writes the user's folder, shows a page, and runs on a schedule. The results decide how the real job-search kit is built, so **record what actually happened, not what should have happened.**

Rules for every step:

- Try each step once. If it fails, record the failure in plain words and move on. One retry is fine for an obvious typo in a path, nothing more.
- Do not work around a failure with a different tool. If the script cannot reach a job board, do not fetch the board another way to make the result look better. The failure is the result.
- Do not change any settings, install packages, or fetch anything the steps below don't name.
- Never show the user a raw error dump. Say what failed in one sentence, and put the exact error text in the report file.
- Plugin root as written in this skill: `${CLAUDE_PLUGIN_ROOT}`. Record in the report whether that line shows a real folder path or the placeholder text with the dollar sign.

## Finding things (every mode)

1. **The connected folder.** The user connects a folder, normally named `Job Search (test)`. Find out two things and record both:
   - whether your shell (the environment where you run commands) can see it, and at what path, for example by listing likely mount points or searching for a folder with that name;
   - whether your file tools (read and write file) can reach it.
   If no folder is connected, say so. In scheduled mode with no folder, follow "Scheduled mode, no folder" below.
2. **The script.** Try, in order, and record which one worked:
   - `${CLAUDE_PLUGIN_ROOT}/skills/platform-check/probe.py`
   - a search of the shell's filesystem for `probe.py` in a folder named `platform-check`
   - reading `probe.py` from this skill with your file tools and writing it into a temp folder in the shell
3. **Python.** Use `python3`; if it doesn't exist, `python`. Record the one you used.

## "run the platform check"

1. **If the shell can see the folder**, run:
   `python3 "<script>" check --folder "<folder path as the shell sees it>"`
   **If it can't**, use the copy route: create `<temp>/platform-check-output` in the shell, copy `platform-check/state.json` from the connected folder into it with your file tools if that file exists, then run:
   `python3 "<script>" check --out "<temp>/platform-check-output"`
   and afterwards copy every file the script wrote (`run-*.json`, `run-*.md`, `My jobs (test).html`, `state.json`) into the connected folder's `platform-check` subfolder, replacing `state.json`.
2. **Web fetch.** With your own web fetch tool (not the shell), fetch `https://boards-api.greenhouse.io/v1/boards/greenhouse/jobs`. Record whether it worked and how many jobs came back, or quote the refusal message.
3. **Local connector.** If a tool named `fetch_board` is available (from the `platform-check-local` connector), call it with `token` set to `greenhouse` and record its full result. If it isn't available, record that, and list any tools or connectors you can see with "platform-check" in the name.
4. **Report.** Write `platform-check/report-<YYYYMMDD-HHMMSS>.md` in the connected folder with:
   - date and time;
   - whether the plugin-root line above showed a real path or the placeholder;
   - how the shell saw the folder (path, or "not visible"), and whether your file tools could reach it;
   - which script route and which Python worked;
   - the script's printed summary, pasted as is, and its output route;
   - the web fetch result and the connector result;
   - anything else that surprised you, in plain words.
5. **Tell the user**, in no more than eight short lines: which steps worked, which didn't, and that the full report is in `platform-check`. No jargon: say "the script could reach 7 of 7 job boards", not "egress succeeded".

## "run the platform check in scheduled mode"

This is what a scheduled task runs. Nobody is watching, so be brief and write everything down.

1. Find the folder, script and Python as above.
2. **With a folder the shell can see:** `python3 "<script>" scheduled --folder "<folder path>"`.
   **With a folder only your file tools can reach:** copy `platform-check/state.json` and `platform-check/scheduled-log.md` from the folder into `<temp>/platform-check-output` if they exist, run `python3 "<script>" scheduled --out "<temp>/platform-check-output"`, then copy `state.json`, `scheduled-log.md` and the new `run-*` files back into the folder's `platform-check` subfolder.
3. If `fetch_board` is available, call it with `token` `greenhouse`.
4. Append one line to `platform-check/scheduled-notes.md` in the folder:
   `- <date and time>: folder reached by <shell | file tools only | not at all>; fetch_board <worked, N jobs, node at PATH | not available | failed: reason>`
5. End the task with the script's summary.

### Scheduled mode, no folder

If no folder is connected, don't write anywhere. Run `python3 "<script>" scheduled --out "<temp>/platform-check-output"`, try `fetch_board` as above, and end the task with the script's summary plus one line: "No folder connected; results are only in this task."

## A pasted line starting "Platform check choices:"

The user copied this from `My jobs (test).html`. Read the latest `platform-check/run-*.json` in the folder, whose `board fetch` → `list` holds the jobs in page order (the page shows the first 15). Write `platform-check/decisions-test.json`:

```json
{"saved": "<date and time>", "source": "pasted from My jobs (test).html",
 "choices": [{"number": 1, "title": "<title>", "choice": "keep"}]}
```

Then confirm in one line how many choices you saved.

## "make the jobs page artifact"

Create an artifact titled **Jobs page test** from the first 15 jobs in the latest `platform-check/run-*.json`: each job's title (linked), location, and Keep / Skip / Not sure buttons. Each click must be **saved in the artifact's own storage** (personal, not shared), so it is still there when the artifact is opened again in a later session.

Write `platform-check/artifact-notes.md` recording what you could and couldn't do, for example whether storage was available and how you set it up. If storage isn't available, say so in the notes and to the user. Don't quietly build a page whose clicks aren't saved.

## "read my choices from Jobs page test"

This runs in a **new** task. Find the artifact titled **Jobs page test** and read the clicks saved in its storage. Write `platform-check/artifact-readback.md` with what you found, or why you couldn't, and which tool or route you tried. Don't ask the user to copy the choices out by hand: the test is whether you can read them yourself.
