---
name: resume
description: Help with the user's resume, only when they ask - check it against what they've confirmed about themselves (claims that are inflated, unconfirmed or don't match), make a clean main resume, or make a copy tailored to one job, as a Word file and a PDF. Use when the user says "check my resume", "is my resume accurate", "clean up my resume", "make me a resume", "update my resume", "tailor my resume for job 12" or "a resume for the Acme job". A job marked worth applying is not a request. Needs the user's Job Search folder connected.
---

# Resume: check it, clean it, tailor it

Only when the user asks. Every line comes from what they've confirmed in `profile/about-me.md`, and nothing is ever improved. A stretched claim fails at the reference check, with their name on it.

The reference search learned this the hard way:
- The resume's numbers had been rounded up, and its scope rounded wider. None of it was invented, and all of it was uncomfortable.
- Corrections crept back into other documents weeks later.
- The PDF that was actually sent went out stale.
- Claude once introduced an overclaim itself.

So the engine checks every line against `about-me.md` before it makes a file.

## Before starting

1. Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`, sections 1 to 5a.
2. Read `profile/about-me.md` in full, and `${CLAUDE_PLUGIN_ROOT}/reference/resume-format.md`.
3. Work out which they want: a check of their resume, a clean main resume, or a copy for one job. If it isn't clear, ask with one multiple-choice question.

## 1. Check their resume

1. **Get it.** Use the file they attached, PDF or Word. If there isn't one, look in their folder for a PDF or Word file with "resume" or "CV" in its name. Otherwise ask: "Attach your resume here, as a PDF or a Word file."
2. **Transcribe it, word for word,** into `<folder>/resume/your-resume-<YYYY-MM-DD>.md`, in the format `resume-format.md` gives. Keep their sections, their order and their words, every line as written. Fix nothing while transcribing.
3. **Under each line, write the `from:` lines it rests on:** the exact words from `about-me.md`, where it supports the line. Leave a line with nothing behind it without a `from:`; the engine marks it.
4. **Read every line against its sources,** and add a `flag:` line where the wording goes further than them (`resume-format.md` gives the kinds). Look for:
   - a number rounded up, or a team or scope wider than confirmed;
   - "led", "owned" or "built" where they worked alongside or contributed, or "designed" where they co-designed;
   - a percentage or a sum of money nothing backs;
   - a credential or licence they don't hold, even after their name;
   - a title they were corrected on, or one from a different job;
   - dates that start earlier or end later than confirmed;
   - a tool listed as a skill where they only use what others build;
   - anything `about-me.md` says the opposite of, such as "Facts postings check: none".
5. **Run the check:**
   ```
   python3 "<folder>/.kit/engine/run.py" resume check "<folder>/resume/your-resume-<date>.md" --own --folder "<folder>"
   ```
6. **Also find the numbers that rest on agreement alone:** a number in a line that's fine, but whose claim in `about-me.md` was established only by "resume and LinkedIn agree". The reference search's inflated numbers were in both, so agreeing proves nothing. Plan one direct question for each one. It's a question, not a fault, so don't call the line wrong.
7. **Tell them what you found, in plain words.** For example: "I checked the 18 lines of your resume against what you've confirmed with me. 8 match. 10 need a look." Then list them, each line quoted, with the reason in a short phrase:
   - **First, the ones that don't match** what they told you: corrected, contradicted, a different number, owned where they worked alongside, wider than confirmed.
   - **Then the ones to confirm:** not in their profile yet, or not confirmed yet.

   Never accuse. "This says a team of 8. You told me 4 direct reports. Which is right?"
8. **Ask about each one, one question at a time,** the way setup asks about their background. Then ask the direct questions about numbers.
   - **A sum of money, a percentage or another measured result needs more than a yes.** Ask how it was measured ("Where does the $250K come from?"), and record their answer with it. If they can't say, it goes under Not confirmed yet. That's how the reference search's unsourceable numbers were caught.
9. **Record each answer in `about-me.md` as soon as they give it,** before you ask the next question. Don't save them up for the end: in the first test run, every answer was given and none was saved. Use its sections, as setup does:
   - **Confirmed:** the claim in their words, with "<first name> said so, <date>: '<their words>'".
   - **Corrected:** Was (the resume's words, quoted, with "(resume)"), Now (what's true), Why (their words and the date). Skip it if `about-me.md` already has that correction.
   - **Not confirmed yet:** anything they aren't sure of, with their words and the date.
   - **Owned hands-on or Worked alongside:** the right column, when the question was about that.

   Never improve a claim or round a number. If they're vague, record it as vague.
10. **Close in a line or two:** what's now confirmed, corrected and still unconfirmed. Then offer: "Want a clean version of your resume, with these fixed?"

## 2. A clean main resume

1. **It starts from a check.** If `resume/` has no `your-resume-*.md`, do step 1 first, saying so in a line: "First I'll check your resume against what you've confirmed, so the clean one starts right."
2. **Write `<folder>/resume/main.md`:**
   - Their name and contact lines, from their resume.
   - Their sections, in their order, and their own wording wherever a line traces.
   - A line the check found wrong: rewrite it to what `about-me.md` now says. If it isn't confirmed, leave it out.
   - A fact they confirmed during the check that their resume didn't have can go where it belongs.
   - The summary, from "How to present me" for the kind of role they want most (`what-i-want.md`), using only confirmed claims.
   - Every line with its `from:` lines, and no `flag:` lines.
   - Nothing else: no new skills, keywords or numbers.
3. **Check it:** `run.py resume check "<folder>/resume/main.md" --folder "<folder>"`. It must come back with `flagged` 0. If not, fix or drop each line it names, and check again.
4. **Make it:** `run.py resume render "<folder>/resume/main.md" --folder "<folder>"`.
   - **Refused because the check's answers aren't recorded** (`about-me.md` hasn't changed since the check)? Record the answers they gave in this conversation, as in step 1, then make it again. Don't ask them again.
   - **They chose not to answer some?** Record each of those lines under Not confirmed yet ("'<the line>': not answered, <date>"), then make it. There's no other way past this refusal, and none is needed: what they didn't confirm stays off the resume either way.
5. **Tell them:**
   - **Where the files are:** "Jordan Lee resume.docx and Jordan Lee resume.pdf, in the resume folder of your Job Search folder."
   - **How many pages it is.**
   - **In three to five lines, what changed from their own resume:** "Fixed: … Left out until you confirm it: … Added, as you confirmed today: …".
   - **If `warnings` says there's no PDF,** say why, and that Word or Google Docs can save the Word file as a PDF.

## 3. A copy for one job

Only when they ask ("tailor my resume for #72"). Find the job by its number in `data/page.json` or `data/postings.json`, or by company and title; ask if several match.

1. **It starts from the main resume.** If `resume/main.md` is missing, or no longer checks clean, offer to make or update it first (step 2), and wait for a yes.
2. **Read the posting in full,** in `data/postings/<key>.md`. Read triage's note on it too (`note` in `data/postings.json`): a "Tailor:" note names the two changes triage suggested.
3. **Write the copy** at `<folder>/resume/<Company> - <Role>/resume.md`, starting from `main.md`. Make two changes, as the reference search did:
   - **The summary leads with what fits this job,** from "How to present me" and triage's note.
   - **The most relevant bullets come first** in each job. A confirmed fact the main resume left out can come in if it fits this job.

   Use the posting's own words only where they name what the user really did ("full-cycle close" for the month-end close they run). Never a requirement they don't meet, a tool they haven't used, or a keyword for its own sake. Nothing else changes.
4. **Check it, then make it:**
   ```
   run.py resume check "<file>" --folder "<folder>"
   run.py resume render "<file>" --for <key> --folder "<folder>"
   ```
5. **Tell them:**
   - where the files are;
   - the two changes, a line each;
   - plainly, what the posting asks for that isn't on the resume, and why. For example: "It asks for a licensed CPA. You've passed 3 of 4 sections, and that's what your resume says." That's worth knowing for a cover note or an interview. It's never a reason to stretch a line.

When they say they've applied, the track skill records it.

## If the Word file can't reach their folder

On the copy route (`running-the-engine.md` section 6), the Word file may not copy into their folder. Then give it to them in the chat, and tell them the PDF is in the folder.

## Don't

- **Don't make, update or offer a resume unless they asked.** A job marked Worth applying isn't a request. The one exception is the one-line offer when catching up finds a resume that no longer matches.
- **Don't improve a claim:**
  - no number rounded up, and no scope widened;
  - no credential, tool or keyword they haven't confirmed;
  - not even a posting's own words, if they would claim more.
- **Don't change `about-me.md` except with the user's answer,** in their words, with the date.
- **Don't work around the engine's refusal:** fix the line or leave it out.
- **Don't predict anything:** how a resume will do, the odds, or what a hiring system will score it.
- **Don't send it anywhere or apply for them.** You make the files; they send them.
- **Don't use technical words with the user:** no "source", "trace", "flag", "engine" or "JSON". Say "your resume", "what you've confirmed with me", "the Word file and the PDF".
