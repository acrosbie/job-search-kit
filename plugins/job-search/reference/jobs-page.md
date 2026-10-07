# The jobs page

Each user has their own jobs page: a Claude artifact in their own Claude account that lists what's waiting on them, the follow-ups due, and every application, each job with a number that never changes. Its buttons save each click in the page's own storage, private to the user. Claude reads those clicks back and records them in the user's folder as the user's own decisions. The folder stays the only record.

The engine rewrites the page's files after every change, so they are always current:

| File | What it is |
|---|---|
| `data/page.json` | The page's data |
| `data/jobs-page.html` | The page with that data built in, ready to publish |
| `My jobs.html` | The same page as a file the user can double-click. It can't save clicks, so it has a **Copy my choices** button instead |

Its link and how it is kept current are in the user's settings, `[page]`: `url`, `version` (the engine version it was published from) and `route`. Read them with `run.py settings show`.

Never mention artifacts, storage, JSON or routes to the user. It's "your jobs page".

## Making the page

Do this in setup's last step, or the first time any skill finds `[page] url` empty.

1. If `[you] name` is empty, set it to the user's first name (`run.py settings set you.name "<first name>"`), taking it from `START HERE.md` or asking. Then run `run.py page` so the page carries it.
2. Publish `<folder>/data/jobs-page.html` as an artifact, with:
   - capabilities `{"db": {}, "user": {}}`;
   - icon `briefcase`;
   - description "What's waiting on you, what's due, and every application."
   If your publishing tool can't read files in the user's folder, read the file and write its contents to a file in your own workspace, then publish that.
3. Save its link and version: `run.py settings set page.url "<link>"`, then `run.py settings set page.version "<engine version>"` (from `run.py version`). Then run `run.py page --pushed`: the page went out with the folder's current data built in.
4. Tell the user, once: "Your jobs page is ready: <link>. You can mark jobs there as you read them. Your clicks wait in your Claude account until I copy them into your folder, the next time we talk."

If publishing isn't possible here (for example in a scheduled check), skip it. Don't mention it, and try again in the next conversation.

## Keeping it current

Do this at the end of any skill that changed something (scan, triage, add-job, track), and after recording clicks.

1. If `[page] version` differs from the engine's version, publish `data/jobs-page.html` again to the same link (pass the link; leave the capabilities and icon as they are), then set `page.version`. This brings in a new page design.
2. Otherwise, send it the latest data by the route in `[page] route`:
   - **`storage`:** with the ArtifactData tool (load it through tool search if needed), `get` the document `page` in collection `data/users/me` to learn its version, then `set` that document to the contents of `data/page.json`, passing the version as `if_version` (leave `if_version` out when the document doesn't exist yet). Use `file_path` if the tool can read the file, otherwise pass the contents as `data`.
   - **`republish`:** publish `data/jobs-page.html` again to the same link.
   - **Empty (not tried yet):** try `storage` first. If it works, run `run.py settings set page.route storage`. If it doesn't, try `republish`, and set the route to `republish` if that works. If neither works, leave the route empty.
3. **Once it's sent, record that:** `run.py page --pushed`. That's how the next conversation knows the page is up to date. Without it, catching up sees `page_behind` and sends it again.
4. If nothing works, skip it quietly. The page shows when it was last brought up to date, `My jobs.html` in the folder is always current, and the next conversation tries again.

## Reading the user's clicks

Every skill does this first, as part of catching up (`running-the-engine.md`).

1. If `[page] url` is empty, there's nothing to read.
2. With ArtifactData, `list` the collection `data/users/me/page/clicks` on the page's link. Keep the clicks whose `recorded` is empty. If there are none, you're done.
3. Write those clicks, as a JSON list, to `<folder>/data/page-choices.json`, replacing what's there. Then run:
   ```
   python3 "<folder>/.kit/engine/run.py" record-choices "<folder>/data/page-choices.json" --folder "<folder>"
   ```
4. Mark each click as done in the page's storage, in one `batch` of `update` writes, each with the version you listed:
   - for every click in `recorded`, `already` or `superseded`, set `recorded` to today's date;
   - for every click in `unknown`, set `recorded` to today's date and `problem` to its `why`, in plain words.
5. Tell the user in one line what you recorded, by number and name: "From your jobs page: you applied to #12 Acme, Senior Accountant, and skipped #15 and #16." Only their last choice on each job is recorded; if they changed their mind on the page or since in chat, say "your last choice on #81 was want it" rather than listing each click. Say plainly which clicks couldn't be recorded, and why.

Never edit or delete the user's clicks in any other way, and never mark one done without recording it first.

## The backup: My jobs.html

If the user can't use the artifact, or prefers a file, point them to **My jobs.html** at the top of their Job Search folder: double-click it, make their choices, press **Copy my choices**, and paste the result into chat.

When they paste text containing `[choices:`, write the pasted text as it is to `<folder>/data/page-choices.json` and run `record-choices` on it, as above. There's nothing to mark done: the file page keeps no clicks.

## The weekly review notice

When a scheduled check has prepared the weekly review, the page shows "Your weekly review is ready" at the top. There's nothing to do for it: the next conversation offers the review (catching up), and going through it clears the notice.

## Chat by number

"Skip #12" or "I applied to 7" refers to the numbers on the page. Look the number up in `data/page.json` (`num` in `waiting`, `todo`, `applications` and `screened`) to find the posting's `key` or the application's `id`. Repeat the name back as you record it ("Skipped #12, Acme, Senior Accountant"), so a wrong number is caught.
