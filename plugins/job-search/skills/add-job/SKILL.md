---
name: add-job
description: Save and screen a job the user found themselves - a link they paste from LinkedIn, Indeed, a company's careers site or anywhere else, or the text of a job posting. Use when the user pastes a job link or a job description, or says "what about this one", "add this job", "screen this one", or "is this worth applying to" with a link. Needs the user's Job Search folder connected.
---

# Add a job: a link or a posting the user found

The user found a job outside their scans. Save it the way a scan would, then judge it like any other posting. The words you save must be the posting's own, because triage quotes them.

## Before starting

Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`, sections 1 to 5a: find the folder, run where it can see it, refresh the engine, and catch up.

## 1. Save it

**Any link: try the engine first.**
```
python3 "<folder>/.kit/engine/run.py" add-link "<the link>" --folder "<folder>"
```
For a link to a job board the engine reads (Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Rippling), it reads that board itself and saves the posting exactly as a scan would. If the result says `"saved": true`, go to step 2. If the company isn't one of theirs, you can add `--company "<name>"` so it's named properly.

**Otherwise** (`"saved": false`, which is every LinkedIn, Indeed or company-site link):

1. **Read the link** with your web fetch tool. Ask it for the job title, company, location, posting date, and the **full description, word for word, not summarised**. Read only the link the user pasted. Never search LinkedIn, follow links from the page, or open other LinkedIn pages.
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

- Don't read LinkedIn or any other site on your own. Read the one link the user gave you, once.
- Don't reword, shorten or tidy the description. Save it word for word.
- Don't invent a detail the posting doesn't give.
- Don't use technical words with the user: no "key", "engine", "JSON" or "board system". Say "your saved jobs", "your list".
