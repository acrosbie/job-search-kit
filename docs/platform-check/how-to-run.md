# How to run the platform check (Windows)

> **Phase 0 is finished.** The test plugin was removed from the repo after its decisions were accepted (`docs/decisions/`). To run it again, for example on a Mac, restore it with `git checkout platform-check-0.0.2 -- plugins/platform-check .claude-plugin/marketplace.json` and push, then follow the steps below.

This is a test, not the kit. It answers three questions before anything real gets built:

1. **Can Claude fetch job boards from inside Cowork**, or does fetching have to happen on your computer?
2. **What's the best jobs page:** a file you open, or a Claude page whose buttons save?
3. **Do scheduled checks run** when the Claude app is closed or the laptop is asleep, and can they reach your folder?

It takes about an hour of your time, plus an afternoon of mostly waiting for Part D. The test only ever fetches Greenhouse's own public job board. Nothing personal is used.

**Screens may not match these steps exactly.** Anthropic is merging "Chat" and "Cowork" into one Claude, so menus are moving. If something isn't where a step says, write down what you saw instead. That's useful evidence too.

**Screenshots:** press **Windows key + Shift + S** and drag over the area. Windows saves each one in `Pictures\Screenshots` (or `OneDrive\Pictures\Screenshots` if you use OneDrive). When you're done, move the ones for this test into the `platform-check` folder inside `Job Search (test)`.

---

## Part A: set up (about 15 minutes)

**A1. Install the Claude app.** Go to **claude.com/download**, download the Windows version, run it, and sign in with your paid Claude account. Allow the install if Windows asks.

**A2. Check which screen you have.** Look at the message box at the bottom. If you see **Chat** and **Cowork** options, you have the older screen: whenever a step says "start a new task", pick **Cowork** first. If you don't see them, you have the new screen: just type in a new conversation. Write down which one you have.

**Not the Code mode.** At the top left, next to the back and forward arrows, there are two small icons: a **speech bubble** and **`</>`**. Every test here happens with the **speech bubble** selected. The `</>` icon switches to Code mode, which runs things directly on your computer and would make every test look like it passed. If a report says it ran on "Windows" rather than "Linux", that run happened in Code mode.

**A3. The test folder** is already made: `Job Search (test)` in your user folder (`C:\Users\<your name>\Job Search (test)`). It's empty. The test writes only into a `platform-check` folder inside it.

**A4. Install the test plugin.**
1. In the left sidebar, open **Customize**, then **Plugins**. (Older screen: open the **Cowork** tab first.)
2. Next to **Personal plugins**, click **+**, then **Add marketplace**, then **Add from a repository**.
3. Type `acrosbie/job-search-kit` and add it.
4. Find **platform-check** in the list and click **Install**. It may warn that the plugin includes something that runs on your computer. That's expected: it's the backup fetcher this test checks. Allow it.

**If step 2 or 3 fails** (no such option, or an error): take a screenshot, then use the backup instead. Click **+** again, choose the option to **upload a plugin file**, and pick `Downloads\platform-check-plugin.zip`.

**A5. Check it arrived.** Open the installed plugin. You should see a skill called **platform-check** and a connector called **platform-check-local**. Write down whether you see both.

---

## Part B: can Claude fetch job boards? (about 20 minutes)

**B1. Screenshot your network setting before touching it.** Open **Settings**, then **Capabilities**. Screenshot the section about **code execution** and **network egress** exactly as it is now. Don't change anything yet.

**B2 (test T1): run it with the setting untouched.**
1. Start a new task.
2. Connect the folder: look for a way to add or work in a folder. It may be a **Work in a folder** checkbox, a folder icon, or an item in the **+** menu. Pick `Job Search (test)`. Allow it when asked whether Claude can read and change files there.
3. Type **run the platform check** and send it.
4. Allow anything Claude asks permission for during this test.
5. After a minute or two, Claude replies with a short summary. Write down **how many job boards it could reach** (for example "0 of 7") and anything it says failed.

**B3 (test T2): turn the network on.**
1. **Settings**, then **Capabilities**. Make sure **Code execution and file creation** is on, then turn on **Allow network egress**.
2. If you're offered a choice of what to allow, pick the one that lets you **add specific domains**, and add these seven:
   ```
   boards-api.greenhouse.io
   api.ashbyhq.com
   api.lever.co
   api.smartrecruiters.com
   *.myworkdayjobs.com
   himalayas.app
   api.rippling.com
   ```
   If there's only an on/off switch, turn it on and write that down.
3. Screenshot the section after saving.
4. Start a **new** task, connect `Job Search (test)` again, and type **run the platform check**. Write down how many job boards it reached.

**B4 (test T2b): only if B3 still reached fewer than 7.** If there's an **All domains** option, switch to it, start a new task, run the check again, and write down the result. Then **switch back** to what you set in B3. This tells a setting problem apart from a known bug where Cowork ignores the setting.

**B5 (test T3): does the folder remember?** Start one more **new** task with the folder connected and type **run the platform check**. Claude's summary says which run number this is. Write it down. It should be one more than the last run, which shows information survives between tasks.

**B6 (test T4): Claude's own web tool.** In the same task, paste this link and send it with the question below:
```
https://boards-api.greenhouse.io/v1/boards/greenhouse/jobs
Can you read this link with your web fetch tool and tell me how many jobs it lists?
```
Write down whether it worked.

---

## Part C: the jobs page (about 20 minutes)

**C1 (test T5): the file version.**
1. In File Explorer, open `Job Search (test)`, then `platform-check`, and double-click **My jobs (test).html**. It opens in your web browser.
2. Pick **Keep**, **Skip** or **Not sure** on three jobs.
3. Click **Copy my choices**. It either says "Copied" or shows a text box to copy from yourself (Ctrl+C).
4. Go back to your Claude task, paste (Ctrl+V) and send. Claude should say it saved them.
5. Then ask Claude: **show me My jobs (test).html**. See whether it appears inside the Claude app and whether the buttons work there.
6. Write down: did the page open, did the buttons work, did copy work, did Claude save your choices, and did the page work inside Claude?

**C2 (test T6): the Claude page that saves clicks.**
1. In the same task, type **make the jobs page artifact**.
2. When the page appears, click Keep or Skip on three jobs. Close it.
3. Start a **new** task with the folder connected and type **read my choices from Jobs page test**.
4. Separately, open **Artifacts** from the sidebar, open **Jobs page test**, and check whether your three clicks are still marked.
5. Write down: did Claude build the page, did it find your clicks in the new task, and were they still marked when you reopened it?

---

## Part D: scheduled checks (spread over an afternoon, about 15 minutes of your time)

Set up both tasks below at the same time. Both run every hour.

**D1 (tests T7 and T8): create two scheduled tasks.**
1. Click **Scheduled** in the left sidebar, then **New task**, then **Set up manually**.
2. First task:
   - Name: `Platform check with folder`
   - Prompt: `run the platform check in scheduled mode`
   - How often: **Hourly**
   - Folder: `Job Search (test)`
   - Approval: pick the option where Claude **doesn't stop to ask** (it may be called Auto). Nobody will be there to click Allow. Write down which options were offered.
   - Screenshot the form, then save.
3. Second task: exactly the same, except name it `Platform check no folder` and **leave the folder empty**.
4. On the Scheduled page, use **Run now** (or similar) on each task once, and check the run finished. For the first task, a line should appear in `Job Search (test)\platform-check\scheduled-log.md`.

**D2. With the app open.** Leave Claude open and the laptop awake past the next hour. Afterwards, check `scheduled-log.md` has a new line at about that time.

**D3. With the app fully closed.**
1. Quit Claude completely: find its icon at the bottom right of the taskbar, near the clock (click the **^** arrow if you don't see it), right-click it, and choose **Quit**. Just closing the window isn't enough.
2. Write down the time. Keep it closed until at least 10 minutes past the next hour.
3. Reopen Claude and write down the time.
4. Check `scheduled-log.md`, and each task's past runs on the Scheduled page. Did a run happen **while Claude was closed**, **right after you reopened it**, or **not at all**? Check both tasks.

**D4. With the laptop asleep.** Leave Claude open, put the laptop to sleep (**Start**, **Power**, **Sleep**) until past the next hour, then wake it. Check the same way.

---

## Cleanup (5 minutes)

1. On the Scheduled page, delete both test tasks.
2. In **Customize**, **Plugins**, open **platform-check** and **Uninstall** it. (Plugins also show up in Claude Code when you sign in there, so this removes it from both.)
3. If you used **All domains** in B4, make sure it's switched back. The seven job-board domains from B3 can stay; the real kit will need them.
4. **Leave** `Job Search (test)\platform-check` in place. I'll read it, then tell you when it can be deleted.

---

## Results sheet

Copy this, fill it in, and paste it back into our conversation. Short answers are fine.

```
A2 Screen: old (Chat/Cowork switch) / new (one Claude)
A4 Install from acrosbie/job-search-kit: worked / failed (what it said) / used the ZIP
A5 Saw skill: yes/no   Saw connector platform-check-local: yes/no
B1 Network section before (screenshot saved): yes/no
B2 T1 boards reached with setting untouched: _ of 7   anything it said failed:
B3 T2 what the network setting offered:
   boards reached after turning it on: _ of 7
B4 T2b (only if needed) boards reached with All domains: _ of 7   switched back: yes/no
B5 T3 run number: _   (one more than the last run: yes/no)
B6 T4 web fetch of the pasted link: worked / refused (what it said)
C1 T5 page opened: yes/no   buttons: yes/no   copy: copied / text box / failed
      Claude saved choices: yes/no   page worked inside Claude: yes/no/didn't show
C2 T6 Claude built the page: yes/no   found clicks in new task: yes/no
      clicks still marked on reopen: yes/no
D1 Approval options offered:
   Run now, with folder: worked/failed   Run now, no folder: worked/failed
D2 App open, ran on the hour: yes/no
D3 Closed at __:__, reopened at __:__
   with folder: ran while closed / ran on reopen / didn't run
   no folder:   ran while closed / ran on reopen / didn't run
D4 Asleep from __:__ to __:__
   with folder: ran while asleep / ran on wake / didn't run
   no folder:   ran while asleep / ran on wake / didn't run
Anything else odd:
```
