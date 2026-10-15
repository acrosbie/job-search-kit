---
name: scan
description: Check the user's job boards and say what's new, or do the whole morning. Use for "any new jobs?", "check for new jobs", "scan", "do my morning job search", a scheduled check, or to set up or stop the daily check ("check my job boards every morning", "stop the daily check"). Needs their Job Search folder.
---

# Scan: any new jobs?

Fetch, then report. Judging fit is the triage skill's job; the morning run (below) follows it.

## Steps

1. **Start as `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md` says: find the folder, refresh the engine if needed, run `start`, and work down its `next`.** Leave `offer_scan`, `say_last_scan_failed` and `run_due_after_news` to the scan: it runs the day-21 close itself, and its summary's `due` says what closed.
2. **Run the scan:** `python3 "<folder>/.kit/engine/run.py" scan --folder "<folder>"`. It reads every board in `profile/companies.toml`; hundreds of boards take a few minutes. It prints a JSON summary.
3. **Report** in about 5 lines (`running-the-engine.md`, "Replies"); the scan gives each job its `num` and `url`:
   - **If `status` is `blocked` or `failed`, that is the whole headline:** nothing was checked. "I couldn't reach any of your 592 job boards from here, so nothing was checked; your saved jobs are as they were." Then the cause and the one fix, as `engine-troubleshooting.md` says. Never call it a scan, and don't report counts.
   - **If `status` is `partial`,** say how many of `watched` were read ("I read 589 of your 592 boards").
   - **What's new:** the count from `new`, then each new posting from `new_postings` as its link, `[#177 Company: Title](url) (place)`. More than five: by company in one line, and the rest are on their jobs page.
   - **What was screened out automatically:** the count from `rejected_postings`, with the reasons grouped ("3 are outside where you'd commute, 1 pays below your line"). Don't list them unless asked.
   - **Boards that failed:** each by company name, in plain words, as `engine-troubleshooting.md` says. Say their saved jobs are still there.
   - **Board health** (`health`):
     - `failing`: a board that failed 3 scans in a row. Offer to look for the company's board again with `discover`.
     - `silent`: no jobs listed for 30 days. Mention it once; the company may have moved its jobs elsewhere.
     - `at_cap`: some of the board's jobs weren't read, because it's so large. Mention it once.
   - **Check by hand:** if `check_by_hand` isn't empty, mention once that some companies can't be read automatically, and offer the list.
   - **Applications:** if `closed_day_21` lists any, one line: "No reply from Acme in three weeks, so I've moved it to no reply." If `follow_ups_due` has any `send` or `find_person`, one line: "Two follow-ups are due; ask me what's due."
   - **The rest of `next`** from `start` (a weekly review ready, an interview soon or waiting for a debrief, a resume that no longer matches): one line each, offered, never started.
4. **Keep the jobs page current** (`${CLAUDE_PLUGIN_ROOT}/reference/jobs-page.md`, "Keeping it current"). In a scheduled check, skip anything it can't do, without comment.
5. **End by offering the next step:** "Want me to go through the new ones?" If nothing is new, say so and stop.

## The morning run: "do my morning job search"

Usually a scheduled task sends this at the time they chose, with nobody there. Do the whole morning, so they open their jobs page to new jobs already read and written up:

1. **Start** as in step 1. Do the quiet items in `next` (refresh the engine, read their clicks, the page). Leave anything that needs their answer, such as how they applied or an interview's time, for the next conversation.
2. **The jobs.** If `start`'s `scan.fresh` is true, a scan ran in the last few hours, usually the Windows task on their computer (`schedules.md`): don't scan again. What it found is in `data/scan-latest.json`. Otherwise scan (step 2). If nothing could be reached, note it and go on: jobs from earlier may still be waiting.
3. **Go through the new ones** as the triage skill says, its first batch of 15, with nobody to ask. Every verdict is yours, with its summary, and they can overturn any. Never mark anything applied, change a rule, or judge again a job they decided.
4. **Keep the jobs page current** (`jobs-page.md`): it's what they look at first.
5. **Leave a short note**, at most five lines: how many new jobs, how many worth applying, with the best one as its link and its headline, any Your call questions, and anything that went wrong (no boards reached, the page not updated).

If they typed it themselves, do the same, then report as the triage skill does.

## Setting up or stopping the daily check

Follow `${CLAUDE_PLUGIN_ROOT}/reference/schedules.md`.

## Don't

- Outside the morning run, don't comment on whether a job fits. The title filter only narrows the list; the verdict comes from reading the whole posting in triage.
- Don't open the saved postings here.
- Don't edit anything in the user's folder by hand. The engine is the only thing that writes the records.
