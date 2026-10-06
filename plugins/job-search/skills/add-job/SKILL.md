---
name: add-job
description: Save and screen a job the user found themselves - a link they paste from LinkedIn, Indeed, a company's careers site or anywhere else, or the text of a job posting. Use when the user pastes a job link or a job description, or says "what about this one", "add this job", "screen this one", or "is this worth applying to" with a link. Needs the user's Job Search folder connected.
---

# Add a job: a link or a posting the user found

The user found a job outside their scans. Save it the way a scan would, then judge it like any other posting. The words you save must be the posting's own, because triage quotes them.

## Before starting

Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`, sections 1 to 5a: find the folder, run where it can see it, refresh the engine, and catch up.

## 1. Save it

**A LinkedIn link: ask for the text straight away.** Claude can't read LinkedIn job pages from Cowork (tested 2026-10-06), so don't try. Say:

> LinkedIn doesn't let me read job postings, so could you paste this one here? Open the job on LinkedIn, select everything from the job title down to the end of the description, copy it, and paste it into this chat.
>
> Or, if the job has an **Apply on company website** button, paste the link that opens instead. I can often read those exactly.

Then save what they paste, as in "Otherwise" step 3 below, with `--text-from pasted` and the LinkedIn link as the URL. If they paste a company link instead, start again from the top with that link. If they'd rather not paste anything, say you can't judge the job without its text, and that they can paste it any time.

**Any other link: try the engine first.**
```
python3 "<folder>/.kit/engine/run.py" add-link "<the link>" --folder "<folder>"
```
For a link to a job board the engine reads (Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Rippling), it reads that board itself and saves the posting exactly as a scan would. If the result says `"saved": true`, go to step 2. If the company isn't one of theirs, you can add `--company "<name>"` so it's named properly.

**Otherwise** (`"saved": false`, which is most company-site and job-site links):

1. **Read the link** with your web fetch tool. Ask it for the job title, company, location, posting date, and the **full description, word for word, not summarised**. Read only the link the user pasted, once. Never follow links from the page.
2. **If you can't read it**, ask for the text. That means the page is blocked, it asks the user to sign in, or what comes back is clearly a summary (short, reworded, sections missing). Say: "I can't read that page from here. Could you copy the job posting, from the title down, and paste it here?"
3. **Write it to a file in your own workspace**, not in the user's folder:
   ```
   # <Title>

   - Company: <Company>
   - Location: <Location, or (not stated)>
   - URL: <the link, or leave it empty for pasted text with no link>
   - Posted: <YYYY-MM-DD, or (unknown)>

   ---

   <the description, word for word>
   ```
   Never fill a gap with a guess: write `(not stated)` or `(unknown)`.
4. **Save it:**
   ```
   python3 "<folder>/.kit/engine/run.py" add "<that file>" --text-from <link|pasted> --folder "<folder>"
   ```
   Use `link` when you read it from the link, `pasted` when the user pasted it.

**If the output names an `application`,** the user had already told you they applied to this job. It's now joined to that application, so say so in one line ("I've added the posting to your Acme application"). Still judge it (step 2), and record your verdict without changing anything, so the monthly review can compare it with what happened: `mark <key> <verdict> --by claude --record-only --note "<note>"`.

**Exit code 3, "already saved as …":** the job is already on their list. Say where it stands in one line, by its number ("That's #12, Acme, Senior Accountant. I marked it worth applying on 2 Oct."), and don't save it again. If they say it's a different job with the same title, run `add` again with `--anyway`.

## 2. Judge it

The output gives the posting's `key`, its `status`, and any flags.

- **`not_a_fit` already:** one of their automatic rules rejected it. Tell them the reason (`note`), and that they can overturn it.
- **`new`:** judge it with the triage skill's "For each posting in the queue" steps, for this one posting (its description is `data/postings/<key>.md`). A flag saying it's not one of the titles their search looks for is worth a sentence, but it's never a reason on its own: they chose this job.

Report the verdict the triage way, with the job's number from `data/page.json`: "#31 Initech, Support Operations Manager: worth applying. Two changes to make to your resume: …"

If the user already said they applied to it, record that next with the track skill.

## 3. Then

Keep the jobs page current (`${CLAUDE_PLUGIN_ROOT}/reference/jobs-page.md`, "Keeping it current").

## Don't

- Don't try to read LinkedIn; ask for the text. Read any other site only through the one link the user gave you, once.
- Don't reword, shorten or tidy the description. Save it word for word.
- Don't invent a detail the posting doesn't give.
- Don't use technical words with the user: no "key", "engine", "JSON" or "board system". Say "your saved jobs", "your list".
