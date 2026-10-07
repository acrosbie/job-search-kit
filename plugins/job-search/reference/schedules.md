# Scheduled checks

Two checks can run on a schedule (decision 3):
- **A daily check of the job boards.** Its prompt is "any new jobs?".
- **A weekly review, prepared for the user to go through later.** Its prompt is "prepare my weekly review".

Each is a Cowork scheduled task with the user's Job Search folder attached, so it runs on their computer and can read and write the folder. It runs only while the computer is on and Claude is open. A missed one is caught up in the next conversation (`running-the-engine.md`, section 5a), which is why every schedule is also recorded in the user's settings.

Setup offers both (its step 7). Use this page whenever the user asks for one later: "check my job boards every morning", "set up a weekly review", "stop the daily check".

## Setting one up

1. **Ask when.** For the daily check, what time each morning, and whether weekdays only. For the review, which day and what time.
2. **Create a scheduled task** with:
   - **the Job Search folder attached**;
   - the prompt: **any new jobs?**, or **prepare my weekly review**;
   - the frequency: daily (or weekdays), or weekly;
   - the approval option that doesn't stop to ask, if there is one.

   Use your scheduling tool if you have one. Otherwise, walk them through **Scheduled** in the sidebar → **New task** → **Set up manually**, giving them each field to fill in.
3. **Record it**, so a missed check is noticed:
   ```
   run.py settings set schedule.scan daily --folder "<folder>"      (or weekdays, or weekly)
   run.py settings set schedule.review weekly --folder "<folder>"
   ```
4. **Tell them in two sentences:** it runs while their computer is on and Claude is open, and a missed one is caught up the next time they talk to Claude. For the review, add that it's only prepared: nothing changes until they go through it.

## Stopping one

Walk them through **Scheduled** → the task → pause or delete it, or use your scheduling tool. Then clear the setting, so a missed check isn't caught up any more: `run.py settings set schedule.scan ""` (or `schedule.review`).
