---
name: review
description: The weekly review of the user's job search - where they overturned a rule, a spot-check of what the scan turned away, titles it nearly kept, which rules fire, follow-ups due, and once a month what happened to their applications and whether their profile is still right. Use when the user says "go through my review", "weekly review", "review my rules", "how's my search going", or when a scheduled check says "prepare my weekly review". Also sets up or stops the weekly review ("set up a weekly review"). Needs the user's Job Search folder connected.
---

# Weekly review

This is what turns a job alert into a search that improves. In the reference system, every rule got better because of the user's own overturns and a few audits done by hand. This review makes those audits routine. Two lessons shape it:
- **The user's overturns are the only ground truth there is.** A rule they've overturned twice is probably wrong.
- **Filters reach a point of diminishing returns.** Searches mostly fail after the application, so the pipeline and the outcomes matter as much as the rules.

Nothing in the review changes anything on its own. Every change goes through the tune skill, and needs the user's yes.

## Before starting

Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`, sections 1 to 5a.

## Setting up or stopping the weekly review

Follow `${CLAUDE_PLUGIN_ROOT}/reference/schedules.md`.

## Prepare mode: a scheduled check

When a scheduled task asks you to prepare the weekly review, nobody is there to answer questions. So:
```
python3 "<folder>/.kit/engine/run.py" review --prepare --folder "<folder>"
```
Then keep the jobs page current (`${CLAUDE_PLUGIN_ROOT}/reference/jobs-page.md`); it will say the review is ready. Stop there: ask nothing, and change nothing.

## Going through it

Use `data/review.json` if it was prepared today or yesterday and not yet gone through (catching up says so). Otherwise run `run.py review` for fresh facts.

**Open with three lines at most.** For example: "Your weekly review: one rule you've overturned twice, 10 jobs the scan turned away to spot-check, and 2 follow-ups due. It takes about 10 minutes; we can stop whenever you like." Then take the parts below in order, one at a time. Skip any that are empty, without mentioning them. Keep each part short.

The user can stop at any point ("let's stop there"). Say what's left, and pick it up next time from the same review. **Before ending, keep the jobs page current**, whether they stopped or finished: anything changed along the way (a rule, a job back on their list, a spot-check overturn) should show there.

### 1. Rules you've overturned, and reasons that sound like rules

- **Each group in `disagreements` with `propose: true`:** say which rule, how many times they overturned it since it last changed, and their words, quoted. Then propose a rewrite through the tune skill, which replays it and asks.
- **Groups without `propose`:** mention them only if there's something to learn ("You overturned the location rule once, for a hybrid job in Austin"). One overturn isn't a pattern yet.
- **`candidate_rules`:** the reasons they gave when deciding jobs that sounded like a rule ("too far"). Read each back, and ask whether it should become a rule. If yes, go through the tune skill.
- **A rewrite they turned down in the last four weeks** (`declined_recently`) isn't raised again.

### 2. Spot-check the scan

Show the `spot_check` jobs as one numbered list: title, company, place, and the reason in plain words. Ask: "Were any of these wrongly turned away?"

For each one they say was wrong, record their verdict:
```
run.py mark <key> worth_applying --by user --note "<their words>"
```
Their words feed next week's disagreements. If two or more share a reason, offer a change through the tune skill now.

### 3. Titles the filter nearly kept

Show `missed_titles` as one numbered list. Ask which they'd want to see. For any yes, test the title change with `run.py try-titles` (setup step 6 shows how), and save it through the tune skill.

### 4. How the rules are working

From `rule_activity`, in a sentence or two:
- **The top rule:** "Most of the turning away this month was 'where the job is' (61 of 70)." The spot-check above is how they check it.
- **Rules that never fired** in four weeks (`never_fired`): offer to turn each one into a flag, which notes the issue but never rejects. A rule that never fires costs nothing. But if the user would rather be told than have jobs turned away, a flag is better. Change it through the tune skill (`change-rule <N> --retire --flag-text …`).

### 5. Your applications

From `pipeline`, the same as the track skill's "What's due?":
- applications closed at day 21;
- follow-ups to send (offer to draft them);
- top picks needing a person;
- one line for the rest.

Mention `scan_health` here too, if it has anything: a board failing 3 scans in a row (offer to look for the company's board again with `discover`), silent for 30 days, or at its cap.

### 6. Once a month: outcomes

When `monthly` is true, show `outcomes` as plain counts: how many applications were answered (a reply, screen, interview or offer), turned down, closed with no reply, or still open. Break them down by what Claude said, how they applied, the level of the role, and top picks.

- **If few or none were answered,** raise the question honestly. Is the level right? Is the resume telling the right story for these roles? Would a referral or a direct note work better than applying cold? Ask which they'd like to look at.
- **Never predict odds, response rates, or how long the search will take.** Those numbers would be invented.

### 7. Once a month: your profile

When `monthly` is true:
- Read back the claims in `profile_refresh.unconfirmed` and ask about each. Record answers in `about-me.md` as setup does (Confirmed, Corrected, Not confirmed yet).
- Ask whether anything in `what-i-want.md` has changed: pay, place, the kind of role. A changed answer is saved with the old one kept, marked "was", with its date.
- If it changes a rule, make that change through the tune skill.

### When you've gone through it

```
run.py review --done [--monthly] --folder "<folder>"
```
(`--monthly` if parts 6 and 7 were done.) Then keep the jobs page current, and end with one line on what changed, if anything.

## Don't

- Don't change a rule, a setting or the profile without going through the tune skill and getting a yes.
- Don't raise a change they turned down in the last four weeks.
- Don't predict odds, applicant numbers, response rates or how long anything will take.
- Don't turn the review into a lecture. One part at a time, short.
- Don't use technical words with the user: no "disagreements", "rule_activity", "JSON" or "engine". Say "rules you've overturned", "how your rules are working".
