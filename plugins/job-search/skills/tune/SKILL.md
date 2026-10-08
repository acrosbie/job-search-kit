---
name: tune
description: Change one of the user's screening rules the careful way - state the change and its evidence, replay it over their saved jobs, name anything it would flip, and save it with its history only after their yes. Use when the user says "stop showing me ...", "change my rules", "that rule is wrong", "I'd take jobs in ...", "add ... to my rules", or when the weekly review or triage proposes a change. Needs the user's Job Search folder connected.
---

# Tune: change one rule, carefully

A rule decides which jobs the user never sees, so changing one deserves care. The reference search learned this the hard way: a rewrite once overturned two of the user's own decisions within the hour and had to be undone. So every change goes the same way:
1. Say it plainly, with the evidence.
2. Replay it over the saved jobs.
3. Name anything it would flip.
4. Wait for a yes.
5. Save it with its history.

The engine refuses a change that skipped the replay, or that would turn away a job the user applied to or wanted without their say.

## Before starting

Follow `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md`, sections 1 to 5a. Read `profile/rules.md`, and `profile/what-i-want.md` for the user's own words.

## 1. Say the change, with its evidence

One or two sentences, in the user's terms, with the facts behind it. For example: "You've overturned Rule 4 twice: Workiva and Grafana Labs, both because owning part of the close is fine for you. Change it to turn a job away only when the role has no part in the close?"

Decide which kind of rule it is:

- **A scan rule** lives in `settings.toml`: where they'd work (`places.*`), remote wording, the pay line, a phrase rule, or the titles they look for. The engine replays these exactly.
- **A triage rule** is a numbered rule in `rules.md`, which you apply when reading postings. You replay these yourself, by reading.

## 2. Replay it

**A scan rule:**
```
python3 "<folder>/.kit/engine/run.py" replay --set <key> "<new value>" --folder "<folder>"
```
For a phrase rule, use `--phrase-reject <name> --phrases "<pattern>"` instead of `--set`. For titles, use `try-titles` (setup's step 6 shows how); it's the replay for a title change.

**A triage rule:**
1. Run `rule-evidence <N> --words "<the rule's key words, as a pattern>"`. You get:
   - the jobs the rule turned away, with your earlier quote;
   - the user's overturns, in their words;
   - passing jobs whose text has those words, with the lines quoted.
2. Judge each job twice, under the current wording and under the new one, from the quoted lines. Open the description file when the lines don't settle it.
   - **If the change only loosens the rule** (it turns away less), the passing jobs can't be turned away by it, so judge only the jobs it turned away.
   - **If it tightens the rule, or adds one,** the passing jobs are the ones that matter.
3. Write the result to a file in your own workspace (not the user's folder):
   ```
   {"checked": ["<every key you judged>"],
    "flips": [{"key": "<key>", "after": "not_a_fit | your_call | passes", "quote": "<the line that decides it>"}]}
   ```
   List only jobs whose verdict would change.

## 3. Show what it would flip

Put the replay in plain words, by number and name:

> I tried it on your 22 saved jobs. It would let through 2 that the "owns nothing" rule turned away: #58 Workiva, Senior Accounting Manager, and #61 Grafana Labs, Accounting Manager (both ones you overturned). It wouldn't turn away anything you applied to or wanted.

- **If it would turn away a job they applied to or wanted** (the replay's `wanted`), say so first, by name, and ask whether that's all right. That needs its own explicit yes.
- If the replay changes nothing at all, say so. A rule that would change nothing may not be worth changing.

## 4. Ask, and wait for a yes

Ask one question: "Save this change?" Offer **Yes, save it**, **Not now**, and **Change it first** (they reword it). Use a multiple-choice question if your tools allow.

- **Only an explicit yes saves it.** "Maybe", "I guess", or no answer is not a yes.
- **Not now:** record it, so the weekly review doesn't raise it again for four weeks:
  ```
  run.py decline --what "rule <N>" --why "<their words>" --proposal "<the change, in plain words>" --folder "<folder>"
  ```
  For a setting, `--what` is `"setting <key>"`; for a phrase rule, `"phrase rule <name>"`.
- **Change it first:** go back to step 1 with their wording, and replay again.

## 5. Save it, with its history

Pass their own words as `--why`: the reason they gave, or their answer.

**A scan rule:**
```
run.py settings set <key> "<new value>" --why "<their words>" [--accept-flips <key> ...] --folder "<folder>"
```
(For a phrase rule, use `settings phrase-reject` with the same `--why`.)

**A triage rule:**
1. Write the rule's new lines to a file: `- Not a fit when: …`, `- Doesn't count: …`, `- Why: …`, keeping the user's earlier answer in **Why**.
2. Run:
   ```
   run.py change-rule <N> --text "<that file>" --why "<their words>" --replay "<the replay file>" [--accept-flips <key> ...] --folder "<folder>"
   ```

The engine keeps the rule's number and history, and adds a dated **Changes** line with the replay. Other forms:
- To retire a rule: `change-rule <N> --retire --why … --replay …`. Add `--flag-text <file>` (a `### <name>` flag with `- When:` and `- What to do:`) to turn it into a flag.
- To add a rule: `change-rule --new "<plain name>" --text … --why … --replay …`.

`--accept-flips` names only the jobs the user explicitly agreed may be turned away. If the engine refuses (exit code 3), it says why, for example that the replay is missing, stale, or for a different change. Fix that and ask again if needed; never work around it.

**For a scan rule, also update `rules.md`'s "Rules the scan applies before triage" section,** so it describes the rule as it now stands. Its history is in `data/changes.log`.

## 6. If it now lets jobs through

If the replay's `would_pass` (or your flips to `passes` or `your_call`) names jobs a rule turned away that the user never decided, offer once: "#58 and #61 would pass now. Put them back on your list?" If they say yes:
```
run.py requeue <key> <key> --why "<the change, in plain words>" --folder "<folder>"
```
Then keep the jobs page current (`${CLAUDE_PLUGIN_ROOT}/reference/jobs-page.md`, "Keeping it current"), including `page --pushed` once it's sent.

## Don't

- Don't save any change without the user's explicit yes, and don't change two rules in one go.
- Don't make a rule from something they didn't say, or about age, family, health or anything not about the job.
- Don't stretch a rule past its "Doesn't count" notes to make the replay look better.
- Don't use technical words with the user: no "regex", "settings.toml", "replay file" or "key". Say "your rules", "the jobs it would change", "your saved jobs".
