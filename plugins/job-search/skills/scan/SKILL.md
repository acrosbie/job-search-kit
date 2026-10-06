---
name: scan
description: Check the user's job boards for new postings and say what's new. Use when the user says "any new jobs?", "check for new jobs", "scan", "run a scan", or when a scheduled check runs. Needs the user's Job Search folder connected.
---

# Scan: any new jobs?

Fetch, then report. Judging fit is the triage skill's job, not this one's.

## Steps

1. **Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`** to find the user's folder, pick where to run, and install or refresh the engine. Then catch up (section 5a), step 1 only: the scan runs the day-21 close itself.
2. **Run the scan:** `python3 "<folder>/.kit/engine/run.py" scan --folder "<folder>"`. It reads every board in `profile/companies.toml`; hundreds of boards take a few minutes. It prints a JSON summary.
3. **Report**, in plain words, no more than about fifteen lines:
   - **What's new:** the count from `new`, then each new posting from `new_postings` as `Company: Title (place)`. If there are more than about fifteen, group them by company.
   - **What was screened out automatically:** the count from `rejected_postings`, with the reasons grouped ("3 are outside where you'd commute, 1 pays below your line"). Don't list them unless asked.
   - **Boards that failed:** each by company name, in plain words, as in the reference's section 8. Say their saved jobs are still there.
   - **Check by hand:** if `check_by_hand` isn't empty, mention once that some companies can't be read automatically, and offer the list.
   - **Applications:** if `closed_day_21` lists any, one line: "No reply from Acme in three weeks, so I've marked it closed." If `follow_ups_due` has any `send` or `find_person`, one line: "Two follow-ups are due; ask me what's due."
4. **Keep the jobs page current** (`${CLAUDE_PLUGIN_ROOT}/reference/jobs-page.md`, "Keeping it current"). In a scheduled check, skip anything it can't do, without comment.
5. **End by offering the next step:** "Want me to go through the new ones?" If nothing is new, say so and stop.

## Don't

- Don't comment on whether a job fits. The title filter only narrows the list; the verdict comes from reading the whole posting in triage.
- Don't open the saved postings here.
- Don't edit anything in the user's folder by hand. The engine is the only thing that writes the records.
- Don't use technical words with the user: no "engine", "JSON", "exit code" or "egress". Say "your job boards", "your saved jobs", "network access".
