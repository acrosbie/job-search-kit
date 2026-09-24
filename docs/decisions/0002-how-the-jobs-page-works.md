# 2. How the jobs page works

- **Status:** proposed, awaiting review, with one question for the reviewer (below)
- **Date:** 2026-09-24
- **Tested on:** Windows 11 Home, Claude Desktop, Pro plan. Not tested: Apple computers, phones, the web version of Claude.

## Decision

The main jobs page is a **Claude artifact whose buttons save each choice in the artifact's own storage**. At the start of every triage, track or scan, Claude reads the saved choices and records them in the user's folder (`decisions.log`), which stays the record. A plain page in the folder, `My jobs.html`, is the backup: the user clicks, copies their choices and pastes them into chat. Answering in chat by number always works as well.

## What we found

| | File in the folder (`My jobs (test).html`) | Claude artifact with storage ("Jobs page test") |
|---|---|---|
| Opens | Double-click in File Explorer opens it in the browser. It also showed inside the Claude app with its buttons | Inside the Claude app, and from the Artifacts list in the sidebar |
| Remembers clicks | **No.** Closing or reloading clears them | **Yes.** Each click is saved immediately, per user (`data/users/<viewer>/choices`), and the clicks were still marked on reopening |
| How Claude gets the choices | The user presses "Copy my choices" and pastes the line into chat. Claude saved all 15 to `decisions-test.json` | Claude reads them itself. In a **new** task, it found the artifact (Artifact tool, `list`) and read the 4 saved clicks (ArtifactData tool, `list`), with no copying by hand |
| Needs | Nothing | Pro plan or above; a signed-in viewer; the ArtifactData tool, which Claude has to load through tool search |
| Where the choices live | Only in the folder, once Claude saves them | On claude.ai, in the user's account, until Claude copies them to the folder |

Tests ran on 2026-09-24 at 12:22 (file) and 12:26 (artifact, read back in a new task).

## Options considered

1. **Artifact with storage (chosen as main).** Buttons that really save, with no server to run and nothing to install. It also opens from any computer signed in to the user's Claude account.
2. **File in the folder plus paste (chosen as backup).** Nothing leaves the folder, and it works with no Claude features. But it's one extra step (copy, paste), and a click is lost if the user closes the page before copying.
3. **Chat by number.** Always works, and needs no page. It's clumsy for 20 postings at once.
4. **Local web server, as in the reference system** (`scan.py serve` at 127.0.0.1:8765). Rejected: it needs Python and a terminal on the user's computer, and neither Cowork workspace can serve a page to the user's browser.

## Question for the reviewer

**Is it acceptable for page clicks to live on claude.ai until Claude copies them into the folder?** The stored data is the job title, company and keep/skip/not-sure for each posting clicked, kept in the user's own account and private to them. Cowork already processes the folder's files on Anthropic's servers ([architecture overview](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview)), so this adds storage, not a new party. But the design doc's privacy section says the user's data lives in their folder. If the answer is no, option 2 becomes the main page and option 1 is dropped.

## What this changes in the design doc

These are proposed edits; the doc itself hasn't been changed.

- **The working loop, "The jobs page":** replace "Clickable buttons that save decisions need a live page, which is an open question for phase 0" with the artifact-plus-storage design above, keeping `My jobs.html` as the backup.
- **Data model:** add the artifact's storage as a temporary inbox for page choices. `decisions.log` stays the only record; a page click is logged as the user's decision (the "by whom" field), so the rule that the user's click beats Claude's verdict carries over.
- **Privacy:** say plainly, once during setup, that page clicks are stored in the user's Claude account until the next session copies them to the folder.
- **Build plan, phase 4:** "My jobs.html" becomes "the jobs page artifact, plus My jobs.html as backup".

## Not yet tested (needed in phase 4)

- **Claude writing the job list into the artifact's storage**, so the page shows new postings after each scan without being rebuilt. The test page had its 15 jobs built in.
- **One page per user versus one shared page.** Storage is private per viewer, so a single published kit page might serve everyone, each with their own clicks. Untested.
- **Phones.** The help article lists new artifacts on desktop and web, not the mobile apps ([Use Cowork on web, desktop, and mobile](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile)).
- **Whether "Copy my choices" works inside the Claude app's preview** of the file page. The buttons showed there; copying wasn't recorded.

## Sources (read 2026-09-24)

- [What are artifacts and how do I use them](https://support.claude.com/en/articles/9487310): "Store data in an artifact", personal versus shared storage, 20 MB limit, Pro and above
- [Use artifacts in Claude Cowork](https://support.claude.com/en/articles/14729249-use-artifacts-in-claude-cowork): artifacts made since 2026-08-19 are ordinary artifacts; live artifacts can't be created any more
- [Use Claude Cowork on web, desktop, and mobile](https://support.claude.com/en/articles/15520349-use-claude-cowork-on-web-desktop-and-mobile): where artifacts are available
