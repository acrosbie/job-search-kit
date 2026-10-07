# Running the engine

The engine is the Python program in this plugin (`${CLAUDE_PLUGIN_ROOT}/engine`) that fetches job boards and keeps the user's records. The user never sees it and shouldn't have to hear about it. Every skill that touches the user's data follows these steps. Only mention them if something fails.

## 1. Find the user's folder

The user connects a folder, usually called `Job Search`. It is theirs if it contains `profile/settings.toml`. Look for it with your file tools and your shells.

- **No folder connected:** ask them to connect it. "Please connect your Job Search folder. Use the folder option next to the message box, then pick the folder."
- **A folder is connected but has no `profile/settings.toml`:** it hasn't been set up yet. Unless you're running setup, don't run anything; offer to set it up ("Say *set me up* and I'll walk you through it").

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
3. If the copy is missing, or the versions differ, copy **every file** under `${CLAUDE_PLUGIN_ROOT}/engine/` into `<folder>/.kit/engine/`, keeping the same paths: `run.py`, `README.md`, `jobkit/`, `jobkit/boards/`, `jobkit/_vendor/tomli/`, `page/` and `starter/`. Overwrite what's there; never delete anything. The plugin's files live on Anthropic's servers, so use whichever route your tools give you to write files into the user's folder.
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
| `mark KEY STATUS --by claude\|user --note "..."` | Record a verdict: `worth_applying`, `your_call`, `not_a_fit` or `skipped` |
| `add-link URL` | Save a pasted link to a job board the engine reads, exactly as a scan would |
| `add FILE` | Save a posting the user found, from a file with the scan's header |
| `apply KEY` | The user applied (only ever when they say so): records the application and marks the posting applied |
| `track ID STATUS` | What happened to an application: a reply, screen, interview, offer, rejection, withdrawal or follow-up; also a contact |
| `due` | Close applications with no reply at day 21, and list the follow-ups due |
| `applications` | Every application, with its day count and what's due |
| `record-choices FILE` | Record the clicks from the user's jobs page |
| `page` | Write the jobs page files again (every change does this already) |
| `review` | The weekly review's facts (the review skill) |
| `replay`, `rule-evidence`, `change-rule`, `decline`, `requeue` | Changing a rule the careful way (the tune skill) |
| `discover NAME` | Which public job board a company uses |

**Exit codes:**
- **0:** done.
- **1:** a file is missing or wrong; the message names it.
- **2:** a mistake in the command.
- **3:** refused on purpose, for example because the user already decided that posting and their decision stands. Follow the message; never work around it.

Full details are in `${CLAUDE_PLUGIN_ROOT}/engine/README.md`.

## 5a. Catch up

After installing or refreshing the engine, every skill catches up before doing anything else:

1. **The jobs page:** read and record any clicks the user made on it, as `${CLAUDE_PLUGIN_ROOT}/reference/jobs-page.md` says under "Reading the user's clicks".
2. **Day 21:** run `due`. If `closed_now` lists anything, say so in one line: "No reply from Acme in three weeks, so I've marked it closed. Tell me if you hear from them." (The scan skill can skip this step: every scan runs it.)
3. **Missed checks**, from the same `due` output. Scheduled checks run only while the computer is on and Claude is open, so one can be missed.
   - **`scan_overdue`:** in the scan and triage skills, run a scan first (the scan skill's steps), saying so in one line: "Your morning check didn't run, so I'm checking now; it takes a few minutes." In any other skill, offer it in one line ("Your last check was 3 days ago; want me to check now?") and carry on with what they asked.
   - **`review_ready`, or `review_due`:** offer it in one line: "Your weekly review is ready; want to go through it?" Start it only if they say yes (the review skill).
4. **The jobs page:** if `due` says `page_behind`, the page in their Claude account doesn't show what the folder holds. A skipped update, or a scheduled check that couldn't reach it, leaves it like this. Bring it up to date quietly, as `jobs-page.md` says under "Keeping it current".

Keep it short: the user asked for something else, so give the catch-up a line or two and move on.

## 6. Fallback: no shell can see the folder

Run the engine straight from `${CLAUDE_PLUGIN_ROOT}/engine` in a shell on Anthropic's servers, against a copy:

1. Copy these into a temporary folder, keeping their paths: `profile/` (every file), plus whichever exist of `data/postings.json`, `data/applications.json`, `data/decisions.log`, `data/runs.log` and `data/page-choices.json`. For `show`, also copy that posting's file from `data/postings/`.
2. Run the command with `--folder` pointing at the temporary folder.
3. Copy back into the user's folder: `data/postings.json`, `data/postings.backup.json`, `data/applications.json`, `data/applications.backup.json`, `data/decisions.log`, `data/runs.log`, `data/titles-latest.tsv`, `data/page.json`, `data/jobs-page.html`, `My jobs.html`, and every file that is new in `data/postings/`.

## 7. Code mode

In Code mode the engine runs directly on the user's computer. If Python 3.10 or later is installed, run `${CLAUDE_PLUGIN_ROOT}/engine/run.py` with the folder's normal path; there's no need to copy the engine. If Python isn't installed, tell them: "The job search kit works in the Claude app's normal conversation view. Switch away from the Code view (the `</>` icon at the top left) and ask me again."

## 8. When something goes wrong, say it in plain words

Never show a raw error. Say what happened and what it means for them, in one or two sentences.

- **One board failed** (the scan summary's `failures`): "Acme's job board didn't answer today; your saved jobs from it are still here." If the same board has failed three scans in a row (its entry in `data/postings.json` → `boards` keeps the error, and `data/runs.log` has the history), offer to look for the company's board again with `discover`.
- **Every board failed with a proxy or "Tunnel connection failed: 403" error:** Claude's network access is off. "I can't reach job boards yet. In Claude, open Settings, then Capabilities, and turn on network access (Allow network egress). Then ask me again."
- **A missing file** (exit code 1): name it in their terms ("your settings file"), not as a path.
- **Never delete anything** in the user's folder, even to tidy up.
