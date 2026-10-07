---
name: setup
description: Set up a new job search in the user's connected folder, through one guided conversation - background from their resume and LinkedIn, their field, what they want, their screening rules, the job boards to read, a first scan and calibration, and a daily check. Use when the user says "set me up", "get started", "set up my job search", or connects an empty Job Search folder. Resumes where it left off.
---

# Setup: from "set me up" to a first screened list

One conversation takes someone who has never used a terminal to a working job search. They answer questions, upload two files and say yes or no to job titles. They never open a file, edit anything, or see a technical word.

## How to talk

- **One question at a time.** Offer choices where you can (use multiple-choice questions if your tools allow), and always accept "not sure". Never stack several questions in one message.
- **Plain words only.** Say "your job boards", not "companies.toml"; say "the titles we look for", not "regex". Never show a file path, code, or an error message.
- **Their words, saved as they said them.** When an answer goes into a file, quote it.
- **Never ask about age, family, health, or anything about them that isn't about the job.**
- **Show before you save** anything that changes how jobs are screened, and say what it will do.
- Keep each message short. The whole setup should fit in one sitting, about 30 to 40 minutes.

## Progress, so setup can stop and resume

After each step, write `profile/setup-progress.md`: the steps done, and anything decided that isn't in another file yet. When setup starts, read it. If steps are already done, say so in one line ("We'd got as far as your preferences; let's pick up there") and continue from the next one. If the folder already has a finished profile and no progress file, it's set up already: say so and offer a scan instead.

## Step 0: the folder and the engine

Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md` sections 1 to 4. Ignore its "no `profile/settings.toml`" case, because that's the folder setup is about to fill. Install the engine into the folder first.

Then start the folder, using the user's time zone (ask which city they're in if you need it). Use the support field pack only if their work is customer support, support operations or CX; otherwise `custom`:
```
python3 "<folder>/.kit/engine/run.py" init --folder "<folder>" --field <support-cx|custom> --timezone <Area/City>
```
You can do the init after step 3 if you don't know their field yet. It refuses a folder that already has a profile, and that's correct: change an existing profile with `settings` and `companies` instead.

Open with one short paragraph: what setup will do (about 30 minutes, one question at a time, nothing to install, everything stays in this folder). Then say once: "What you share with me is processed by Anthropic under your Claude plan's terms; your files stay in this folder."

Once you know their first name, save it for their jobs page: `run.py settings set --folder "<folder>" you.name "<first name>"`.

## Step 1: let Claude reach the job boards

Say in one sentence why: "To read job boards for you, Claude needs permission to reach those websites."

Walk them through it:
1. Open **Settings**, then **Capabilities**.
2. Turn on **Code execution and file creation**, if it's off, and **Allow network egress**.
3. If there's a choice of what to allow: **if they can list specific sites**, have them add the ones in `${CLAUDE_PLUGIN_ROOT}/reference/job-board-domains.md` (give them the list to paste). If the only choices are package managers or all sites, choose **All domains**, and say plainly that it lets Claude reach any website when it runs code.

Prove it worked by reading one board:
```
run.py scan --folder "<folder>" --only <the slug of any greenhouse company in profile/companies.toml>
```
If it says the board couldn't be reached, follow `running-the-engine.md` section 8, and give them a minute to change the setting. If they can't or won't, say the kit can still screen job links they paste in, and carry on.

## Step 2: their background, from their resume and LinkedIn

Ask for their **resume** (PDF or Word, attached here) and their **LinkedIn profile**: on their profile page, More → Save to PDF, or paste the text. Read both in full.

Draft `profile/about-me.md` in the shape `${CLAUDE_PLUGIN_ROOT}/reference/profile-format.md` gives. Then confirm it with them, one question at a time. Ask only what changes a verdict later, about **8 to 12 questions**:

- **Numbers and scope.** For anything numeric or scope-heavy, ask how it really was: "You wrote 'led a team of 30'. How many people reported to you directly?"
- **Mismatches.** Where the resume and LinkedIn disagree (title, dates, team size, scope), ask which is right. Never pick one quietly.
- **Owned or alongside.** For each tool, system or area: "Did you own this hands-on, or work alongside the people who did?" Triage leans on this line.
- **The facts postings check.** Degrees, certifications, licences, clearances, languages, industries, years managing people, years managing managers. Ask only for what their field's postings commonly require.
- **What they back themselves on, and what they don't.** One question each.

Every claim goes under **Confirmed** (with how: "their resume and LinkedIn agree", or "they said so", with the date) or **Not confirmed yet**. A correction goes under **Corrected**, with the old wording kept. Then fill **How to present me, by kind of role** from what they confirmed, so triage's tailoring has something true to lead with.

Never improve a claim. If they're vague, record it as vague.

## Step 3: their field and the titles to look for

**Ask what work they want.** Offer: "the same kind of work you do now", "something adjacent (tell me what)", "a change". Then ask what they'd type into a job site's search box.

**If it's customer support, support operations or CX**, the support field pack already holds titles tuned on tens of thousands of real postings; use it.

**Otherwise, build the title patterns** (the field generator). A title is kept when it has a **function** word **and** a **level** word, and no **exclude** word. All patterns are case-insensitive regular expressions.
- **function:** the phrases that name their work, as postings write them. For an accountant, for example: `accounting|accountant|controller|accounts payable|accounts receivable|\bpayroll\b|general ledger|financial reporting`. Use real title phrases, not job-description words. Prefer two-word phrases over one broad word.
- **level:** the seniority words that fit, for example `\bmanager\b|\bdirector\b|\bhead\b|\blead\b|\bcontroller\b`. Put `\b` around short words so "lead" doesn't match "leader".
- **exclude:** look-alikes they don't want: neighbouring functions sharing a word (`account (manager|executive)` against accounting), interns, the seniority they've ruled out (`\bvp\b|vice president` if that's too senior), sales.
- **field_words:** broader words of the field (`accounting|finance|payroll|audit|controller`). These don't keep anything; they're how calibration and the weekly review spot titles the filter nearly kept.

Write each one with `run.py settings set --folder "<folder>" titles.function "<pattern>" --setup` (likewise `titles.level`, `titles.exclude`, `titles.field_words`). `--setup` marks setup's own settings: the engine accepts them until the user's first decision on a job. After that, every rule change goes through the tune skill. The engine checks a pattern before saving it; if it refuses, fix it and try again. Don't trouble the user with the refusal.

Record in `what-i-want.md` the field, the adjacent fields they'd take, and the fields they've ruled out, with their reasons. Tell them the titles aren't final: step 6 checks them against real postings.

## Step 4: what they're looking for

Short, plain questions, one at a time, each with choices and "not sure". Save every answer verbatim, with the date, in `profile/what-i-want.md`. Use the table in `profile-format.md`.

1. **Role shape:** individual contributor, manager, or either? What do they need to own?
2. **Pay:** the lowest pay they'd consider. If the pay is below that, reject it automatically, or just flag it?
3. **Place:**
   - which city they live in;
   - remote, hybrid or on-site;
   - the longest commute they'd do for a hybrid job;
   - whether they'd relocate.
4. **Hours:** anything ruled out (on-call, shifts, weekends)?
5. **Company:** size or stage they prefer; industries they'd avoid.
6. **Contract or temporary work:** in, lower priority, or out?
7. **Deal-breakers and nice-to-haves,** in their words.
8. **Constraints:**
   - Do they need visa sponsorship?
   - When can they start?
   - How urgent is the search?

## Step 5: their rules and job boards

**Rules.** Build `profile/rules.md` from `${CLAUDE_PLUGIN_ROOT}/reference/rule-catalog.md`, keeping **only** the rules their answers call for. Each rule gets its plain name, when it fires, its "Doesn't count" notes, and the answer that created it, quoted and dated. Add the flags that apply. Under "Rules the scan applies before triage", list location, pay (if they chose reject) and any phrase rule.

**Settings, through the engine** (`run.py settings set ... --setup`):
- **`places.hybrid_ok`** and **`places.remote_only`** come from their commute. Draft the actual town names within their commute, and a ring further out that would work only if remote. Show both lists, ask them to correct them, then save each as a pattern, such as `denver|aurora|lakewood|englewood`. The rest of the country and abroad are already set.
- **`pay.reject_if_top_below`:** their lowest pay as a yearly number, only if they chose "reject". If they chose "flag", leave it at 0 and make pay a flag in rules.md.
- **Phrase rules**, with `run.py settings phrase-reject ... --setup`, only for a kind of job that hides behind their titles and that they always turn down.

**Show them the result as one plain list:** "Here's what I'll screen out, and what I'll only point out to you." Ask what's wrong, and fix it before going on.

**Job boards.** They start with 589 public company job boards, mostly technology companies. Say so plainly: "They suit office jobs at tech companies best. If there are companies you'd especially like, tell me and I'll add them." For each company they name:
1. Run `run.py discover <name>`. Add `--page <their careers page>` if the plain check finds nothing.
2. Check four of the board's titles really belong to that company. The same name can belong to a different company.
3. Add it with `run.py companies add --folder "<folder>" --name ... --slug ... --ats ... --token ...`.

If nothing is found, say the company can't be read automatically, and that they can paste its job links any time.

## Step 6: first scan, then calibrate the titles

**Run the scan** (follow the scan skill's steps), and tell them it takes a few minutes. Then show them how the titles are working, without listing everything:
```
run.py titles --folder "<folder>" --sample 10
```

**Show about 10 kept titles and 10 near misses** as two short numbered lists: "Here are 10 titles I'd show you", then "Here are 10 I left out". Ask for a yes or no on each: would they want to see jobs titled like that?

**Turn their answers into title changes:**
- A kept title they don't want means an `exclude` word, or a narrower `function` phrase.
- A near miss they do want means adding its phrase to `function`, or its seniority word to `level`.

Test each change before saving it:
```
run.py try-titles --folder "<folder>" --level "<new pattern>"
```
Tell them in one line what it changes ("That adds 43 Senior Accountant jobs and loses none"). Save it with `settings set ... --setup` when they agree. Do at most three rounds. Then say what's left: what the filter keeps and what it skips.

**Then go through the first batch together**, using the triage skill. Pick 5 to 10 of the newest postings if there are many. When they disagree with a verdict, ask why. If their reason is a rule ("too far", "no agency jobs"), make the change with the tune skill, which shows what it would change on their saved jobs and saves it only when they say yes.

## Step 7: scheduled checks

Offer two, one at a time, and set up each one they want as `${CLAUDE_PLUGIN_ROOT}/reference/schedules.md` says:
- **A daily check:** "Want me to check your job boards every morning?"
- **A weekly review:** "Once a week I can also get a short review ready: where you've overturned my verdicts, a spot-check of what the scan turned away, and your follow-ups. You go through it when it suits you. Want that?"

## Step 8: wrap up

**Make their jobs page,** as `${CLAUDE_PLUGIN_ROOT}/reference/jobs-page.md` says under "Making the page" (it asks first whether they'd rather have it as a file only). Its last step tells them, once, that clicks on the page wait in their Claude account until Claude copies them into this folder. If it can't be made here, tell them about **My jobs.html** in their folder instead.

**Write `START HERE.md`** at the top of the folder. Claude reads it first in every future conversation:

```
# Job search: start here

This folder is <their first name>'s job search, run with the job-search kit. Say what you want in plain words:

- "Any new jobs?" checks the job boards and says what's new.
- "Go through the new ones" sorts new jobs into worth applying, your call, and not a fit.
- "Apply to the first one, skip the second, it's too far" records your decisions.
- Paste a job link from LinkedIn or anywhere to have it screened too.
- "I applied to Acme", "Acme replied" or "I have an interview" keeps track of your applications.
- "What's due?" lists the follow-ups worth sending.
- "Go through my review" goes through the weekly review: rules you've overturned, a spot-check, your follow-ups.
- "Show me my jobs page" opens the page where you can mark jobs yourself. My jobs.html in this folder is the same page as a file.
- "Check my resume", "make me a clean resume" or "tailor my resume for #12" helps with your resume, using only what you've confirmed.
- "I have an interview with Acme on Thursday at 2" records it with a calendar file; "prep me for it" writes a prep sheet; "mock interview" lets you practise; "how did it go" records what happened.

profile/   about you, what you want, and your screening rules
data/      every job found, every decision, every application
.kit/      the engine that reads the job boards (no need to open it)

Set up on <date>. A daily check runs at <time>, and a weekly review is prepared on <day>, while this computer is on.
Your jobs page: <link>
```

**Close with a short summary:**
- how many job boards, and how many jobs the first scan found in their field;
- the rules in one line each;
- what you assumed: anything they said "not sure" to, which you should revisit;
- what to check in the first week (look at a few "not a fit" verdicts, and say if any were wrong);
- their jobs page, with its link, and that they can tell you when they apply, hear back, or get an interview.

Delete nothing. Leave `setup-progress.md` marked finished.

## Don't

- Don't ask several questions at once, or more than the steps need.
- Don't invent anything about them, a company, or the market. Don't predict odds, applicant numbers or how long the search will take.
- Don't make a rule from something they didn't say.
- Don't ask about age, family, health, or anything not about the job.
- Don't show technical words, file paths, code or errors.
