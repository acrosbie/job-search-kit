# Phase 5: the weekly review in Cowork

This checks phase 5's proof: with two overturns seeded on one rule, the weekly review proposes a rewrite, shows its replay, and saves it with its history only after a yes. It takes about 10 minutes.

The test folder is `Job Search (test)\phase5\Job Search`, a copy of the made-up accounting manager's folder from phase 4. Two of Claude's verdicts there were overturned, in Morgan's words. Both were rejections under **Rule 4, "Owns the month-end close"**:
- **Workiva:** "Owning part of the close is fine. Most accounting manager jobs share the close with someone."
- **Grafana Labs:** "I'd take this one. Owning the review of the hardest parts of the close is real ownership."

Two more jobs, at Fastly and DoorDash, were turned away by the same rule, and nobody has decided them yet.

## Before you start

The plugin must be **job-search 0.4.0**. Check its version in **Customize**, then **Plugins**.

## The run

Use the **speech bubble** mode. Click **+ New** and connect `Job Search (test)\phase5\Job Search`.

1. **Say "go through my weekly review".**
   - Claude should open with a few lines of summary.
   - It should then say you've overturned Rule 4 twice, quoting your words, and propose rewriting it.
   - It should show the replay: which saved jobs would change, by name. Expect Fastly and DoorDash to pass under the new wording, and nothing you applied to or wanted to be turned away.
2. **Say "No, leave it for now."** Nothing should change, and Claude should say it won't raise it again for a few weeks.
3. **Say "Actually, yes, make that change."** It should be saved. Claude should then offer to put Fastly and DoorDash back on your list; say yes.
4. **Say "let's stop there"**, or carry on with the spot-check if you're curious.
5. **Optional, about 5 minutes: does a scheduled review get prepared?**
   1. Say **set up a weekly review**.
   2. In **Scheduled**, use **Run now** on it.
   3. In a new task, say **any news?**
   Claude should say your weekly review is ready, and the jobs page should say so at the top.

## Then tell me

Say which steps did what they should. I'll check the rest:
- the folder, with `python tools/check_review.py "<folder>" "<phase5>\review-expected.json"`;
- the rule's new wording and history in `rules.md`.

## What this run decides

- **Steps 1 to 3:** whether the tune skill's careful path works in Cowork: Claude's replay by reading, the refusal of a save without one, and a "not now" that holds.
- **Step 5:** whether a scheduled check can prepare the review unattended. Phase 4 left the same question open for the jobs page.
