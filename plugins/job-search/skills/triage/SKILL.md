---
name: triage
description: Go through new job postings and sort each into Worth applying, Your call, or Not a fit, quoting the posting and using the user's own rules and background. Use when the user says "go through the new ones", "go through them", "triage", "is this one worth applying to", or gives their own verdicts ("skip the third one, it's too far"). Needs the user's Job Search folder connected.
---

# Triage: go through the new ones

Read each waiting posting the way a careful friend would: in full, against the user's own rules and background, and quoting the posting's words. Then record a verdict the user can read and overturn. The scan only narrowed the list by title and place; this is where the judgment happens. Nothing here is invented.

## Before starting

1. **Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`**, sections 1 to 4.
2. **Read the user's profile** (the format is in `${CLAUDE_PLUGIN_ROOT}/reference/profile-format.md`):
   - `profile/rules.md`: the rules and flags you will apply;
   - `profile/about-me.md`: what they have and haven't done, and how to present them;
   - `profile/what-i-want.md`: their preferences, in their words.
3. **Get the queue:** `python3 "<folder>/.kit/engine/run.py" queue --folder "<folder>"`. If it's empty, say there's nothing waiting and offer to check for new jobs.

## For each posting in the queue

Read its description file (`description_file`) **in full**. Then:

1. **Rules, in the order rules.md gives them.** For each one, find the line in the posting that decides it and quote it, or note "not stated". The first rule that fires makes the posting Not a fit; keep checking the rest only far enough to be sure.
2. **What the user has done comes only from about-me.md.** If a posting requires something about-me.md records them as *not* having, that can fire a rule. If about-me.md doesn't mention it either way, **don't assume they lack it**: it's a question for them, which makes the posting Your call.
3. **Cooldown.** The queue gives each posting `applied_recently_at_company` and `same_company_in_queue`. Apply the user's cooldown rule to those facts. When several postings at one company pass, only the best fit is Worth applying. The others are Your call ("second Acme job this month; the better fit is ..."), naming the best fit.
4. **Flags**, as rules.md says. The scan may already have set some on the posting (`flag`), such as a place it couldn't read or four or five days in the office. Flags never reject on their own; rules.md says what to do with each.
5. **Verdict:**
   - **Worth applying:** no rule fires, or only unknowns that wouldn't change the answer. Add the two things to change on their resume for this job, and the posting's own words to mirror. Take both **only** from Confirmed and Owned hands-on in about-me.md, following its "How to present me" section. Nothing unconfirmed, ever.
   - **Your call:** a rule can't be decided from the posting, or a flag asks a question. Give the **single question** that decides it, and who can answer it. If nobody at the company can be asked (no contact recorded), it's the user's call: "apply and ask on the first call, or skip". Quote the line that carries the risk. **Never turn a Your call into Worth applying** to be helpful: it is the user's decision.
   - **Not a fit:** name the rule and quote the line that fired it.
6. **Record it:**
   ```
   python3 "<folder>/.kit/engine/run.py" mark KEY <worth_applying|your_call|not_a_fit> --by claude --note "<note>" --folder "<folder>"
   ```
   The note is one line. For Not a fit: `Rule N (<plain name>): "<quoted line>"`. For Your call: `Question: <the question>`. For Worth applying: `Tailor: <the two changes, briefly>`.

   **Exit code 3 means the user already decided this posting. Their decision stands:** leave it and don't mention it again. Never mark anything `applied`; only the user does that.

If a posting says it's no longer on the board (`gone`), still judge it, and say so when you report it.

## Report to the user

In plain words, short enough to read in a minute:

1. **The count:** "12 new: 2 worth applying, 3 your call, 7 not a fit."
2. **Worth applying**, each with its link: the two resume changes, and the words to mirror.
3. **Your call**, each with its question and who can answer it.
4. **Not a fit**, grouped by reason, titles only ("Too far to commute: Acme Support Lead, Globex Care Manager"). Offer to show the quote for any of them. The user can overturn any verdict.

## When the user answers

"Apply to the first two, skip the third, it's too far", or any verdict of their own:

- Record each one with `--by user` and their words as the note. Their verdict overrides Claude's, and the engine notes a reversal.
- **Only the user marks a posting `applied`**, and only once they say they have applied. Never assume it.
- When they give a reason that sounds like a rule ("too far", "no more contract work"), write it in the note as `candidate rule: <their words>`. Don't change any rule now; rule changes are proposed, tested on saved postings and agreed with the user first.

## Don't

- Don't predict odds, applicant numbers, or how competitive a job is. Those numbers would be invented.
- Don't soften a Not a fit because the company is attractive.
- Don't invent a requirement, a contact, or a referral. Every verdict rests on a quoted line.
- Don't re-judge a posting the user has already decided.
- Don't use technical words with the user: no "engine", "JSON", "status code" or "key". Say "the posting", "your saved jobs", "your rules".
