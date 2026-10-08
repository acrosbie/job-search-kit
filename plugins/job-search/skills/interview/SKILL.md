---
name: interview
description: Help the user prepare for and learn from job interviews, from their own confirmed background - record an interview (with a calendar file), write a prep sheet for it, run a mock interview, go through how it went afterwards, and keep a story bank and a one-page quick reference. Use when the user says "I have an interview with ...", "I have a screen with ... tomorrow", "prep me for my ... interview", "help me prepare", "mock interview", "practice", "what should I ask them", "how did my interview go", "debrief", "story bank" or "cheat sheet". Needs the user's Job Search folder connected.
---

# Interview: prepare from what's true, and learn from each one

An interview is where an overstated claim costs the most: it gets probed, out loud, by someone who knows the field. So everything the user plans to say comes from what they've confirmed in `profile/about-me.md`, and the engine checks it.

The method comes from the reference search:
- **Name a gap early, then move on.** Every gap gets a plain sentence, then a bridge to something true.
- **Raise the awkward caveat yourself,** before they find it.
- **Lead with the answer, give one example, then stop talking.**
- **Ask the user directly about anything the posting cares about that the profile doesn't cover,** and save the answers. Interviews are when people remember what they did.

## Before starting

1. Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`, sections 1 to 5a.
2. Read `profile/about-me.md` in full, `profile/what-i-want.md`, `profile/rules.md`, and `${CLAUDE_PLUGIN_ROOT}/reference/interview-format.md`.
3. Look in the folder's `notes/` for anything the user wrote before about this company, or about interviews in general (an old prep sheet, a story, a quick reference). Use it as a starting point. What it says about them still has to be in `about-me.md` before it goes into an answer.
4. Work out which they want: to record an interview, a prep sheet, a mock interview, a debrief, the story bank, or the quick reference. If it isn't clear, ask with one multiple-choice question.

## 1. Record the interview

1. **Find the application** with `run.py applications`, by company and role; ask if several match. If they never recorded applying, record it first, as the track skill's "I applied to …" says.
2. **Ask what you need, in one short message:**
   - when, as a day and a time;
   - phone, video or on site;
   - who it's with, in their words;
   - how long, if they know.

   Never guess a time.
3. **Record it:**
   ```
   python3 "<folder>/.kit/engine/run.py" track <id> <screen|interview> --on <YYYY-MM-DDTHH:MM> [--kind phone|video|onsite] [--with "<who>"] [--minutes N] --folder "<folder>"
   ```
   A recruiter or phone screen is `screen`; anything after that is `interview`. The output names the calendar file. Tell them: "Double-click `<calendar file>` in your Job Search folder to add it to your calendar."
4. **Offer the prep sheet:** "Want me to put a prep sheet together? It takes about ten minutes, with a few questions for you."

## 2. The prep sheet

1. **Gather what's known about this job:**
   - the posting, in full: `data/postings/<key>.md`, or `run.py show <key>`, for the application's key;
   - triage's note on it, and the application's history (how they applied, who they've talked to);
   - their notes about this company.

   If there's no saved posting, ask them to paste it (the add-job skill saves it).
2. **Check the posting's must-haves against `about-me.md`.**
   - List what the posting requires or calls essential.
   - For each one, find the line in `about-me.md` that covers it.
   - Ask about each one it doesn't cover, one question at a time. Skip those already under Not confirmed yet.
   - **Save each answer in `about-me.md` the moment they give it,** as the resume skill's check does:
     - Confirmed: "<first name> said so, <date>: '<their words>'";
     - Corrected;
     - or Not confirmed yet.
   - **If the interview is today or tomorrow, ask only the three to five that matter most,** and say so.
3. **Pay facts:**
   ```
   run.py pay --ask <their ask from what-i-want.md, as a yearly number> --folder "<folder>"
   ```
   Quote facts only: "Of your 120 saved postings with a posted range, the middle one tops out at $175K; 38 top out below your ask." Never say what they'll be offered.
4. **Write the prep sheet** at `<folder>/interviews/<Company> - <Role>/prep.md`; `run.py interview list` gives the folder. Use the format in `interview-format.md`:
   - **At a glance:** when, who, how long, and what this round is for. A recruiter screen is about fit, pay and logistics; a hiring manager goes deeper into the work.
   - **The company:** three lines, from the posting. If you look anything else up, cite the page. Never invent a fact about the company.
   - **The role:** what it really is, in plain words, quoting the posting.
   - **Opener:** a 60-second answer to "tell me about yourself", tilted to this role, every line with its `from:` lines.
   - **Answers:** the 5 to 8 questions most likely in this round, each as `### <question>` with its answer, every line traced. For a recruiter screen, include:
     - why this role;
     - why they're looking;
     - what they want next;
     - pay;
     - when they can start;
     - one or two questions about the work itself.
   - **Gaps:** each gap the posting will find, named plainly, then bridged to something true. Traced.
   - **Caveats:** anything they should raise themselves, such as a number with a catch (`about-me.md` says when). Traced.
   - **Comp:** their ask (`what-i-want.md`), the posting's range if it states one, the pay facts above, and the one sentence to say.
   - **Logistics:** start date, where they'd work, and anything `what-i-want.md` says to raise only at the offer stage (time off, say).
   - **Questions to ask:** four to six, specific to this posting.
   - **Do not say:** the old versions of every correction, anything worked alongside said as owned, and anything their notes mark never to say.
5. **Check it:**
   ```
   run.py interview check "<folder>/interviews/<Company> - <Role>/prep.md" --folder "<folder>"
   ```
   It must come back with `flagged` 0. Fix each line it names, or drop it, and check again. Never get round a flag by adding to `about-me.md` without the user's answer.
6. **Tell them, in a few lines:**
   - where the sheet is;
   - the three things that matter most in this call;
   - the one caveat to raise themselves;
   - then offer a mock run: "Want to practise? I'll be the recruiter."

## 3. A mock interview

1. **Play the interviewer** for this round, from the posting and the prep sheet, one question at a time.
   - **A recruiter:** friendly; fit, pay, logistics, and one or two questions about the work.
   - **A hiring manager:** the work in depth, and the gaps.
   - **Never pretend to know something about the company** that the posting doesn't say.
2. **After each answer, give short feedback:**
   - **Claims:** quote anything they said that isn't in `about-me.md`. If it's true, ask, and save it the way step 2 does. If it isn't, give the honest version.
   - **Length:** about 60 to 90 seconds spoken, or 150 to 220 words.
   - **Shape:** the answer first, one example, then stop.
3. **When they stop:** sum up in three points. Offer to put their best phrasings into the prep sheet, traced, and check it again.

## 4. Afterwards: how did it go

Offer this when catching up lists the interview under `debrief_due`, or when they bring it up.

1. **Ask, briefly:**
   - what they asked;
   - what went well, and what was hard;
   - what happens next;
   - the names of anyone they met.
2. **Record it:**
   - **The stage:** `run.py track <id> <status> --note "<their words>"` when it moved on, or ended. A next screen or interview takes its day (`--on`, step 1), or `--time-unknown` until they know it.
   - **Anyone they named:** `--contact "<name>"`. Only a name they gave you.
   - **A next round already booked:** step 1's `track … --on`.
3. **New facts:** something they said about themselves that isn't in `about-me.md` gets confirmed with them first, then saved.
4. **Write it down:**
   - add `## Debrief, <date>` to the prep sheet, in their words (make `prep.md` with just this if there was no prep sheet);
   - then run `run.py interview debriefed <id> --folder "<folder>"`. It's refused until the debrief is written there.
5. **Offer a short thank-you note:** three or four sentences, one specific thing from the conversation, nothing unconfirmed. It's theirs to send.

## 5. The story bank and the quick reference

Only when they ask, or once with the first prep sheet.

- **`interviews/stories.md`:** six to ten stories under `## Stories`, each `### <name>`:
  - what was going on;
  - what they did;
  - what happened, and how they know.

  Every line traced. Seed it from their notes, and ask about any story `about-me.md` doesn't hold yet.
- **`interviews/quick-reference.md`:** one page to have open during a call, with these sections:
  - `## Comp`;
  - `## Logistics`;
  - `## Answers`: one-line prompts, traced;
  - `## Do not say`;
  - `## Ask them`.

Check both with `run.py interview check`.

## Don't

- **Don't predict:** not how the interview will go, the odds, the offer, or how long the process takes.
- **Don't invent:** no fact about the company, no person, no number.
- **Don't put in an answer** anything that isn't confirmed in `about-me.md`, and never say something worked alongside was owned.
- **Don't send anything,** or contact anyone. The user does.
- **Don't use technical words with the user:** no "trace", "from:", "engine" or "JSON". Say "what you've confirmed", "your prep sheet".
