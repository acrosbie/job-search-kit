---
name: track
description: Record what happens with the user's job applications - "I applied to X", replies, phone screens, interviews, offers, rejections, withdrawals, follow-ups and contacts - and say which follow-ups are due. Also opens their jobs page. Use when the user says "I applied to ...", "X replied", "I have an interview with ...", "X turned me down", "I withdrew from ...", "the recruiter at X is ...", "I followed up with ...", "what's due?", "any follow-ups?", "where do things stand?", "show me my jobs page" or "open my jobs page". Needs the user's Job Search folder connected.
---

# Track: applications, and what happens next

Record what the user tells you about their applications, in their words, and keep the follow-ups honest. A follow-up needs someone to receive it. So with a contact on record, there's something to send. A top pick with nobody known is a search for a person. Anything else is left to close by itself at day 21.

## Before starting

Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`, sections 1 to 5a: find the folder, run where it can see it, refresh the engine, and catch up.

**Record everything the user told you first, then run `due` once.** For example, an application from three weeks ago that has a reply is recorded with its reply before anything closes.

**An interview or screen booked** ("I have a screen with Acme tomorrow at 10") is recorded by the interview skill's step 1, which keeps the day and time and writes a calendar file. Then it offers a prep sheet.

## "I applied to …"

Only ever when the user says they applied. Never because Claude marked a job worth applying, and never "probably".

1. **Find the job.**
   - A number ("I applied to #12") is a `num` in `data/page.json`.
   - A company or title: look in `data/page.json` first, then in `data/postings.json`.
   - If several jobs match, ask which one, with one multiple-choice question.
   - If it isn't saved and they have the link, save it first with the add-job skill. For a LinkedIn link, that means asking them to paste the posting.
   - If they'd rather not paste it, or there's no link, record it by company and role. Say they can paste the posting any time, and it will be joined to this application.
2. **Ask how, and whether it's a top pick, in one go.** Use multiple-choice questions if your tools allow; otherwise ask in one short message.
   - For each application, ask "How did you apply to <Company>?", with the choices: on the company's site, through LinkedIn, through someone I know, some other way. Name the company in every question.
   - Then ask one question: "Which of these are top picks for you?", listing each company as a choice (for one application: "Is this one of your top picks?").
   - Ask about at most three applications at a time. Skip anything they've already told you ("I applied through a friend" answers how).
   - Match each answer to its company by name before recording it. Never carry one application's answers over to another.
3. **The date** is today, unless they say otherwise.
   - "Last Tuesday" means that date.
   - "About two weeks ago" means the latest date it could be, with `--estimated`.
   - Never a date after today.
4. **Record it:**
   ```
   python3 "<folder>/.kit/engine/run.py" apply <key> --channel <company_site|linkedin|referral|other> --top-pick <yes|no> [--date YYYY-MM-DD] [--estimated] [--contact "<name>"] [--note "<their words>"] --folder "<folder>"
   ```
   With no saved posting: `apply --company "<company>" --role "<role>" [--url "<link>"] …`.
5. **Confirm each application on its own line,** with the date, how they applied and whether it's a top pick, so a wrong answer is caught:
   > Recorded:
   > - #12 Acme, Senior Accountant: today, on their site, a top pick
   > - #15 Globex, Controller: 2 Oct, through LinkedIn, not a top pick

   If they correct one, record the correction with `track <id> --channel … --top-pick …`.

## What happened next

Find the application in `run.py applications` (by number, company or role; ask if several match). Then record it with:
```
python3 "<folder>/.kit/engine/run.py" track <id> <status> [--date YYYY-MM-DD] [--note "<their words>"] [--contact "<name>"] --folder "<folder>"
```

| The user says | Status |
|---|---|
| "They emailed me back", "a recruiter got in touch about it" | `replied` |
| "I have a phone screen", "a recruiter call is booked" | `screen` |
| "I have an interview", "second round" | `interview` |
| "They made me an offer" | `offer` |
| "They turned me down", a rejection email | `rejected` |
| "I pulled out", "I withdrew" | `withdrawn` |
| "They cancelled the job", "it's been filled" | `closed` |
| "I followed up", "I sent a note" | `followed_up` |

- **A person they name**, such as "the recruiter is Dana Smith": add `--contact "Dana Smith"`. On its own: `track <id> --contact "<name>"`. Only a name the user gave you. Never guess one, and never look one up.
- **A reply after the day-21 close** is good news, and fine to record. It replaces "no reply".
- Put the user's own words in `--note` when they add anything ("they want to talk about the hybrid days").

## "What's due?"

Run `due`, then say, briefly:

- **`closed_now`:** one line. "No reply from Acme in three weeks, so I've marked it closed. Tell me if you hear back."
- **`send`:** "Follow up with Dana Smith at Acme (day 8). Want me to draft a short note?" A draft is three or four plain sentences. It uses only what's confirmed in `profile/about-me.md`, and it's theirs to send. When they say they've sent it, record `followed_up`.
- **`find_person`:** "Acme, Senior Accountant is a top pick, and nobody's on record to follow up with. Look on LinkedIn or Acme's site for the person who would lead the team this job is in. Tell me their name, and I'll add them."
- **`closing`:** one line for all of them. "Three more have nobody to send to; they close on their own at day 21 (the next is Globex, on 22 Oct)."
- Nothing due: say so in one line.

## "Show me my jobs page"

Follow `${CLAUDE_PLUGIN_ROOT}/reference/jobs-page.md`. Make the page if there isn't one; otherwise bring it up to date. Then give them the link. If they'd rather have a file, point them to **My jobs.html** in their Job Search folder.

## Then

Keep the jobs page current (`jobs-page.md`, "Keeping it current").

## Don't

- Don't record an application the user hasn't told you about.
- Don't send, email or message anyone. You draft; they send.
- Don't guess, search for or invent a contact's name.
- Don't predict replies, odds, or how long anything will take.
- Don't use technical words with the user: no "status", "ID", "track" or "route". Say "your applications", "what's due", "closed after three weeks with no reply".
