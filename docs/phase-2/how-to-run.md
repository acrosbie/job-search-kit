# Phase 2: trying the scan and triage in Cowork

This checks that the kit's two skills work in Cowork, and that its triage agrees with the decisions already made in a real search. It takes about 15 minutes of your time, plus waiting.

The test folder was built for you from that search, with 20 postings put back to "waiting". The right answers are kept in a file **next to** the folder, not inside it, so Claude can't see them.

## Before you start (5 minutes)

**Skim the three profile files.** They describe you, and the triage follows them word for word. They're in `Job Search (test)\phase2\Job Search\profile\`:
- `about-me.md`: your background: confirmed, corrected, unconfirmed, owned versus worked alongside.
- `what-i-want.md`: your preferences, in your words.
- `rules.md`: your screening rules and flags.

Tell me anything that's wrong before the run, not after.

## The run

1. **Install the plugin.** In the Claude app, open **Customize**, then **Plugins**. The **job-search-kit** marketplace should now offer **job-search**; if it doesn't, click **Update** on the marketplace and wait a few minutes. Install **job-search**. If the old **platform-check** is still there, uninstall it.
2. **Note your usage.** Open **Settings**, then **Usage**, and write down the figure. The design doc asks how much a day's scan and triage costs.
3. **Start a conversation in the right mode.** Make sure the **speech bubble** icon at the top left is selected, not `</>`. Click **+ New**.
4. **Connect the folder.** Connect `Job Search (test)\phase2\Job Search`: the inner **Job Search** folder, **not** `phase2`. Connecting `phase2` would let Claude see the answers.
5. **Scan.** Type **any new jobs?** and allow what it asks. The first time, it copies its engine into the folder and then reads 590 job boards. That takes a few minutes.
6. **Triage.** When it's done, type **go through them**. It works through the 20 test postings plus anything genuinely new. This takes a while; let it finish.
7. **Don't answer its verdicts yet.** Your own verdicts would be recorded too, and they'd muddle the comparison.
8. **Note your usage again**, and tell me both figures.

I'll then score the kit's verdicts against the answers and send you each disagreement, to fix or accept.
