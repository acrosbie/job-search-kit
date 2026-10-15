# Scheduled checks

Two checks can run on a schedule (decision 3):
- **The morning run: the job boards checked, the new jobs gone through and written up, the jobs page brought up to date.** Its prompt is "do my morning job search" (the scan skill's morning run).
- **A weekly review, prepared for the user to go through later.** Its prompt is "prepare my weekly review".

Each is a Cowork scheduled task with the user's Job Search folder attached, so it runs on their computer and can read and write the folder. It runs only while the computer is on and Claude is open. A missed one is caught up in the next conversation (`start` lists `offer_scan`), which is why every schedule is also recorded in the user's settings.

Setup offers both (its step 7). Use this page whenever the user asks for one later: "check my job boards every morning", "set up a weekly review", "stop the daily check".

## Setting one up

1. **Ask when.** For the morning run, what time, and whether weekdays only. For the review, which day and what time.
2. **Check that the job boards can be reached from Claude's workspace** (for the morning run): `probe`. If `network` is `blocked`, set up the Windows task first (below); the Cowork task still goes through what it finds.
3. **Create a scheduled task** with:
   - **the Job Search folder attached**;
   - the prompt: **do my morning job search**, or **prepare my weekly review**;
   - the frequency: daily (or weekdays), or weekly;
   - the approval option that doesn't stop to ask, if there is one.

   Use your scheduling tool if you have one. Otherwise, walk them through **Scheduled** in the sidebar → **New task** → **Set up manually**, giving them each field to fill in.
4. **Record it**, with its time, so a missed check is noticed and today's isn't counted missed before it has run:
   ```
   run.py settings set schedule.scan daily --folder "<folder>"      (or weekdays, or weekly)
   run.py settings set schedule.scan_at 06:50 --folder "<folder>"   (the morning run's time)
   run.py settings set schedule.review weekly --folder "<folder>"
   ```
5. **A catch-up for the morning run:** a second task with the same prompt, **do my morning job search**, about three hours later. If the first one ran, the catch-up finds nothing to do and leaves no note; if the computer was asleep or Claude couldn't reach it, the catch-up does the morning. Found in real use (2026-10-13 and 14): the 06:50 run missed two days running, and a run at 10:37 worked.
6. **Tell them in two sentences:** it runs while their computer is on and Claude is open, and a missed one is caught up the next time they talk to Claude. For the morning run, add that every verdict is yours and theirs to overturn, and nothing is applied for or sent. For the review, that it's only prepared: nothing changes until they go through it.

## When Claude's workspace can't reach job boards

Some computers' Claude workspaces are refused by a proxy on every board, even with network access on, while Windows itself reaches them (found in real use, 2026-10-08). Then Windows does the fetching: a Windows scheduled task runs the scan from the folder's own copy of the engine each morning, and the Cowork task, 15 minutes later, sees that scan (`start`'s `scan.fresh`) and goes through what it found.

1. **It's made on Windows itself:** in Remote Control or Code mode on their computer, not in Claude's workspace. On a Mac, say this isn't available yet; the morning run then works only if the workspace can reach the boards.
2. **Make it** 15 minutes before the Cowork task:
   ```
   python "<folder>\.kit\engine\run.py" windows-task create --at 06:45 --folder "<folder>"      (add --weekdays for Monday to Friday)
   ```
   It runs only while they're signed in, with no window, and catches up when the computer wakes after the time it was due. Each scan's result goes to `data/scan-latest.json`.
3. **Check it:** `windows-task show` gives when it runs next and how the last run went (`last_result` 0 is fine). A run that reaches no board (the network not up yet as the computer wakes) tries again every 20 minutes, three times. `outdated` means it was made before it could try again: make it again, with the same time, after the folder's engine is current.
4. **Tell them in one sentence:** "Your computer will check your job boards at 6:45 each morning, and Claude goes through what it finds at 7:00."

## Stopping one

Walk them through **Scheduled** → the task → pause or delete it, or use your scheduling tool. Then clear the setting, so a missed check isn't caught up any more: `run.py settings set schedule.scan "" --folder "<folder>"` (or `schedule.review`). If there's a Windows task, remove it too, from Remote Control or Code mode: `windows-task remove`.
