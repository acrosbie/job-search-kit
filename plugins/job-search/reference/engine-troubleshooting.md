# When the engine can't run, or something fails

Read this only when `running-the-engine.md` sends you here.

## The workspace isn't ready

If the shell on the user's computer says it is still setting up or downloading, wait about a minute and try once more. The first use can take five minutes. If it still isn't ready, use the copy route below.

## Python

`python3 --version` must print 3.10 or later. On Windows, `python3` can be a shortcut that only prints "Python was not found"; use `python` there instead.

## Code mode or Remote Control

The shell is the user's own Windows or macOS system rather than Linux. The engine runs directly there: run `${CLAUDE_PLUGIN_ROOT}/engine/run.py` with the folder's normal path; there's no need to copy the engine. If Python isn't installed, tell them: "The job search kit works in the Claude app's normal conversation view. Switch away from the Code view (the `</>` icon at the top left) and ask me again."

## The copy route: no shell can see the folder

Run the engine straight from `${CLAUDE_PLUGIN_ROOT}/engine` in a shell on Anthropic's servers, against a copy:

1. Copy into a temporary folder, keeping their paths: `profile/` and `data/` (every file, except `data/snapshots/` and the descriptions in `data/postings/`: copy only the ones the command reads, such as the posting for `show`, or the queue's for triage). For `resume` and `interview` commands, also copy `resume/` or `interviews/`.
2. Note the time: `python3 -c "import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat())"`.
3. Run the command with `--folder` pointing at the temporary folder.
4. List what it wrote: `python3 "${CLAUDE_PLUGIN_ROOT}/engine/run.py" changed --since "<that time>" --folder "<temporary folder>"`. Copy back into the user's folder exactly the files it lists, keeping their paths. The Word file and PDF of a resume copy like any file; if the Word file can't be written into their folder this way, give it to them in the chat instead, and say so.

## Say it in plain words

Never show a raw error. Say what happened and what it means for them, in one or two sentences.

- **One board failed** (the scan summary's `failures`): "Acme's job board didn't answer today; your saved jobs from it are still here." If the scan's `health` lists it under `failing`, look for the company's board again as the scan skill's board health says.
- **A scan with `status` `blocked` or `failed`:** nothing was checked, and nothing in the folder changed. Lead with that, then the cause from `failures_by_kind`, then one fix:
  - `proxy`: Claude's network access is off, or doesn't allow job boards. "I can't reach your job boards from here, so nothing was checked. In Claude, open Settings, then Capabilities, and turn on network access (Allow network egress). Then ask me again." If another place in the table in `running-the-engine.md` is open to you, try it first.
  - `offline`: "This computer doesn't seem to be online right now, so nothing was checked."
  - anything else: "None of your job boards answered just now, so nothing was checked. I'll try again next time."
- **A missing file** (exit code 1): name it in their terms ("your settings file"), not as a path.
- **A file broken, or a change that went wrong** (a bad hand edit, a mistaken bulk change): the engine keeps the records as they were before each command. `snapshots` lists them, newest first, with the command each came before. Say what you'd put back and from when ("your applications as they were this morning, before the scan"), and only after their yes run `restore SLOT --file <path>`. It keeps what's there now as a snapshot too. The logs aren't rewound, so say so if it matters.
- **Something else seems wrong:** `doctor` runs every check in full (`--probe` also tries three job boards). Its `problems` say what and the fix.
- **Never delete anything** in the user's folder, even to tidy up.
