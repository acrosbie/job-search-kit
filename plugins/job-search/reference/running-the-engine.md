# Running the engine

The engine is the Python program in this plugin (`${CLAUDE_PLUGIN_ROOT}/engine`) that fetches job boards and keeps the user's records. The user never sees it and shouldn't have to hear about it. Every skill that touches the user's data follows these steps. Only mention them if something fails.

## 1. Find the user's folder

The user connects a folder, usually called `Job Search`. It is theirs if it contains `profile/settings.toml`. Look for it with your file tools and your shells.

- **No folder connected:** ask them to connect it. "Please connect your Job Search folder. Use the folder option next to the message box, then pick the folder."
- **A folder is connected but has no `profile/settings.toml`:** it hasn't been set up. Say so plainly and don't run anything.

## 2. Pick where to run

You may have two shells: one on Anthropic's servers, and one on the user's own computer. The one on their computer usually sees connected folders under `~/mnt/<folder name>`. **Run the engine in a shell that can see the user's folder.**

- If that shell says it is still setting up or downloading, wait about a minute and try once more. If it still isn't ready, use the fallback in section 6.
- If your shell is the user's own Windows or macOS system rather than Linux, you are in the desktop app's Code mode. Follow section 7.

## 3. Python

`python3 --version` must print 3.10 or later. On Windows, `python3` can be a shortcut that only prints "Python was not found"; use `python` there instead.

## 4. Install or refresh the engine

The engine runs from a copy inside the user's folder, `<folder>/.kit/engine/`, so the shell on their computer can reach it.

1. Run `python3 "<folder>/.kit/engine/run.py" version`. It prints `job-search-kit engine X.Y.Z, Python ...`.
2. Compare that with `__version__` in `${CLAUDE_PLUGIN_ROOT}/engine/jobkit/__init__.py`.
3. If the copy is missing, or the versions differ, copy **every file** under `${CLAUDE_PLUGIN_ROOT}/engine/` into `<folder>/.kit/engine/`, keeping the same paths: `run.py`, `README.md`, `jobkit/`, `jobkit/boards/`, `jobkit/_vendor/tomli/`. Overwrite what's there; never delete anything. The plugin's files live on Anthropic's servers, so use whichever route your tools give you to write files into the user's folder.
4. Run the version check again. It must now match. If copying isn't possible at all, use the fallback in section 6.

## 5. Commands

```
python3 "<folder>/.kit/engine/run.py" <command> --folder "<folder>"
```

Quote every path: folder names often contain spaces.

| Command | Use |
|---|---|
| `scan` | Read every board in `profile/companies.toml` and save what's new. Prints a JSON summary |
| `queue` | The postings waiting for triage, each with its cooldown facts |
| `show KEY` | One saved posting, as text |
| `mark KEY STATUS --by claude\|user --note "..."` | Record a verdict: `worth_applying`, `your_call`, `not_a_fit`, `skipped`, or `applied` (user only) |
| `add FILE` | Register a posting saved by hand |
| `discover NAME` | Which public job board a company uses |

**Exit codes:**
- **0:** done.
- **1:** a file is missing or wrong; the message names it.
- **2:** a mistake in the command.
- **3:** refused on purpose, for example because the user already decided that posting and their decision stands. Follow the message; never work around it.

Full details are in `${CLAUDE_PLUGIN_ROOT}/engine/README.md`.

## 6. Fallback: no shell can see the folder

Run the engine straight from `${CLAUDE_PLUGIN_ROOT}/engine` in a shell on Anthropic's servers, against a copy:

1. Copy these into a temporary folder, keeping their paths: `profile/` (every file), plus whichever exist of `data/postings.json`, `data/applications.json`, `data/decisions.log` and `data/runs.log`.
2. Run the command with `--folder` pointing at the temporary folder.
3. Copy back into the user's folder: `data/postings.json`, `data/postings.backup.json`, `data/decisions.log`, `data/runs.log`, `data/titles-latest.tsv`, and every file that is new in `data/postings/`.

## 7. Code mode

In Code mode the engine runs directly on the user's computer. If Python 3.10 or later is installed, run `${CLAUDE_PLUGIN_ROOT}/engine/run.py` with the folder's normal path; there's no need to copy the engine. If Python isn't installed, tell them: "The job search kit works in the Claude app's normal conversation view. Switch away from the Code view (the `</>` icon at the top left) and ask me again."

## 8. When something goes wrong, say it in plain words

Never show a raw error. Say what happened and what it means for them, in one or two sentences.

- **One board failed** (the scan summary's `failures`): "Acme's job board didn't answer today; your saved jobs from it are still here." If the same board has failed three scans in a row (its entry in `data/postings.json` → `boards` keeps the error, and `data/runs.log` has the history), offer to look for the company's board again with `discover`.
- **Every board failed with a proxy or "Tunnel connection failed: 403" error:** Claude's network access is off. "I can't reach job boards yet. In Claude, open Settings, then Capabilities, and turn on network access (Allow network egress). Then ask me again."
- **A missing file** (exit code 1): name it in their terms ("your settings file"), not as a path.
- **Never delete anything** in the user's folder, even to tidy up.
