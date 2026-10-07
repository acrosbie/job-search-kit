# Phase 5b: resume help in Cowork

This checks phase 5b's proof. Morgan, the made-up accounting manager, brings an updated resume with 10 inflated or unconfirmed claims planted among accurate lines, plus one new claim that's true. The check must flag all 11 and call no accurate line wrong. Morgan's answers must land in `about-me.md`. Then a clean resume and a copy tailored to one job, in Word and PDF, must carry none of the 10 and nothing the job asks for that Morgan lacks. It takes about 15 minutes.

The test folder is `Job Search (test)\phase5b\Job Search`, a copy of Morgan's folder from phase 5.
- **Morgan's updated resume** sits beside it, outside the folder: `Job Search (test)\phase5b\resume-updated.pdf`.
- **Morgan's answers** are in the answer sheet's "Resume check" section (`tests/personas/accounting-manager-denver/answer-sheet.md`).

## Before you start

The plugin must be **job-search 0.5.0**. Check its version in **Customize**, then **Plugins**.

## The run

Use the **speech bubble** mode. Click **+ New** and connect `Job Search (test)\phase5b\Job Search`.

1. **Attach `resume-updated.pdf` and say "Can you check my resume against what you know about me?"**
   - Claude may first bring your jobs page up to date. That's the catch-up being tested too.
   - It should say how many lines it checked, and list the ones that need a look. Expect:
     - the CPA after the name;
     - "Senior Accounting Manager";
     - a team of 8;
     - $250K;
     - owning ASC 606;
     - leading the audit;
     - consolidations;
     - SOX;
     - Tableau dashboards;
     - June 2016;
     - the Expensify rollout.
   - It may also ask you to confirm a few numbers directly.
   - Answer each question from the answer sheet.
2. **Say "Make me a clean resume."** It should name two files in the resume folder, and say in a few lines what changed.
3. **Say "Now tailor it for #72."**
   - It should name two files in a Grafana Labs folder inside the resume folder.
   - It should name the two changes it made.
   - It should say plainly what the posting asks for that isn't on your resume: Big 4, a CPA certification, and so on.
4. **Open the tailored Word file and its PDF** in whatever you'd use to send a resume: Word, Google Docs, Word on the web, or your PDF viewer. Do they open without complaint, and look like a normal resume?

## Then tell me

Tell me which steps did what they should, and what you saw when you opened the files. I'll check the rest:
- the folder, with `python tools/check_resume.py "<folder>" tests/personas/accounting-manager-denver/resume-seeds.json`;
- the jobs page's storage.

## What this run decides

- **Judgment:** whether Claude catches the three plants only judgment can see: leading the audit, Tableau dashboards and SOX. The engine catches the other seven by rule.
- **The posting's words:** whether a tempting posting's words (Big 4, CPA, SEC reporting) stay off the tailored copy.
- **The Word file:** whether the kit's own Word file opens cleanly in a real app. There's no Word on the build computer.
- **Where it ran:** which workspace ran the engine, and whether the Word file reached the folder.
- **0.4.1's page catch-up:** the first time it has met Cowork. This folder's page was never marked as up to date.
