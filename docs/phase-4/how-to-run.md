# Phase 4: a scripted week in Cowork

This checks the loop end to end: a pasted LinkedIn link, three applications, one reply, one day-21 close, and the jobs page with clicks read back. It takes about 15 minutes. The engine side is already proven by `tests/test_week.py`; this run proves the skills and the page in Cowork.

The test folder is `Job Search (test)\phase4\Job Search`, a copy of the made-up accounting manager's folder from phase 3. What the run should leave is in `phase4\week-expected.json`, **next to** the folder, not inside it.

## Before you start

The plugin must be **job-search 0.3.0**. In **Customize**, then **Plugins**, check its version. Auto-sync brings it a few minutes after the push.

## The run

Use the **speech bubble** mode, not `</>`. Click **+ New** and connect `Job Search (test)\phase4\Job Search` (the inner folder). Allow what Claude asks.

1. **Paste the LinkedIn link.** On its own line:
   `https://www.linkedin.com/jobs/view/accounting-manager-at-mv-transportation-4471959130`
   Claude should update its engine (the folder still has the oldest one), save the job, and give a verdict with the job's number. It may also make your jobs page and give you its link.

2. **Say what you applied to.** Paste this:
   > I applied to that one 8 days ago through LinkedIn. I also applied to Fivetran's Senior Manager Accounting job 24 days ago, and they replied last week: they want a phone screen. And I applied to Step's Accounting Manager job 22 days ago, no word since.

   When it asks, answer:
   - Fivetran and Step were on the company's site.
   - Only MV Transportation is a top pick.

   Claude should record three applications. It should say:
   - Step closed after three weeks with no reply;
   - Fivetran is at a phone screen (not closed, though it's past day 21);
   - MV Transportation is due a "find a person".

3. **Say "show me my jobs page"** and open the link. Then:
   - Check that MV Transportation is under **To do** as "Find a person", and that the Fivetran and Step applications read **Screen** and **No reply**.
   - Under **Waiting on you**, click **Skip** on one job and **Save**. Then click **Want it** on another and **Save**.

4. **Start a new task**, connect the same folder, and say **what's due?**
   Claude should first say it recorded your two choices from the jobs page, by number and name, and then list what's due.

5. **Optional, about 5 minutes: can a scheduled check update the page?**
   1. In that task, say **set up a daily check at 7am**.
   2. Then, in **Scheduled** in the sidebar, use **Run now** on it, and wait for it to finish.
   3. Reopen the jobs page and look at the **As of** time at the top.
   If it changed, the page can promise fresh jobs each morning. If it didn't, it says when it was last brought up to date, and catches up the next time you talk to Claude.

## Then tell me

Say which steps did what they should, and anything that surprised you. I check the rest myself, without you doing anything more:
- the folder, with `python tools/check_week.py "<folder>" "<phase4>\week-expected.json"`;
- the page, by reading the artifact;
- your two clicks, by reading the page's storage.

## What this run decides

- **Step 1:** whether Claude can read a LinkedIn link word for word, or needs the text pasted. Either works; this tells us which one users will usually see.
- **Step 3:** how the page is kept current, by writing to its storage or by publishing it again. The answer is saved in the folder as `[page] route`.
- **Step 5:** what we tell users about when the page updates.
