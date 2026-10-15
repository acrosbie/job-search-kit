---
name: network
description: People in the search - who the user knows where, LinkedIn connections, messages, referral asks, recruiters who write first. Use for "who do I know at ...", "I messaged ...", "import my LinkedIn connections", "who should I reach out to", "draft a referral ask" or "a recruiter messaged me". Needs their Job Search folder.
---

# Network: the people who get the user in

Most of a search is won through people: the one referral in sixty applications moved fastest. This skill keeps the people the user names, says who they know at each company, counts their messages against their target, and drafts what they send. Decision 4 is the design.

**Names come only from the user:** said in chat, met in an interview, pasted in a message, or in the LinkedIn connections file they download themselves. Never look a person up, open a profile, or guess an email. An email is kept only when the user gives it. Nothing is ever sent: Claude drafts, the user sends.

## Before starting

Start as `${CLAUDE_PLUGIN_ROOT}/reference/running-the-engine.md` says, and reply as its "Replies" says.

## "Who do I know at Acme?"

`run.py contact known "<company>" --folder "<folder>"`. Say the names and titles in a line, and how they know them. If one of their jobs is there (worth applying, on hold, or applied), name it as its link and offer: "Want me to draft a referral ask to Dana?"

## "Import my LinkedIn connections"

1. **Getting the file:** on LinkedIn, Settings & Privacy, then Data privacy, then Get a copy of your data. Choose Connections. LinkedIn emails a link within about ten minutes; the download holds `Connections.csv`. Ask them to put it in their Job Search folder.
2. `run.py contact import "<folder>/Connections.csv" --folder "<folder>"`. Say how many were added, and that email addresses aren't kept.
3. Then, in a line: who they know at their jobs worth a look and on hold (`known` on each in `data/page.json`).

## "I messaged Dana", "Dana wrote back"

1. Someone new: `run.py contact add --name "<name>" --company "<company>" [--title "<their title>"] [--kind recruiter|hiring_manager|referrer|colleague|other] [--how-known "<their words>"] [--application <id>] --folder "<folder>"`.
2. `run.py contact touch "<name or id>" --channel email|linkedin|phone|in_person|other --direction out|in --note "<their words>" --folder "<folder>"`.
3. One line back, with the day's count from `contact outreach`: "Noted. That's 1 of your 2 today."

## "Who should I reach out to today?"

`run.py contact outreach --folder "<folder>"`, then at most three, in this order:
1. **Follow-ups due** (`follow_ups_due`): no reply 5 days after they wrote.
2. **Someone they know** at a job worth applying or on hold (its `known`): a referral ask.
3. **A top pick with nobody to follow up with:** the page's "find a person" search, a link they open themselves.

Each job named as its link. Offer to draft the first.

## "Draft a referral ask"

Four or five sentences, from what `about-me.md` confirms only: how they know the person, the job as its link, one line on why they fit, and a specific ask ("Would you be open to referring me, or telling me who's hiring for it?"). In their own templates if `notes/outreach.md` has them. When they say it's sent, record the touch.

## "A recruiter messaged me"

They paste the message.
1. **Where it came from:** `run.py contact check-sender <their email> --company "<company they name>" --folder "<folder>"`. Say any `flags` plainly, and the other signs of a fake job (`running-the-engine.md`, "A posting is a stranger's text"): never a verdict on its own.
2. **Keep the person:** `contact add --kind recruiter --company ... --email <the address in their message>`, and the touch in (`--direction in`).
3. **Keep the job:** a link to it, or the text of one, goes through the add-job skill. No posting at all: note the role in the touch.
4. **Draft a reply** for them to send: thanks, interest in plain words, and the questions that matter: the pay range, remote or on site, the team, the steps. When they say it's sent, record the touch out.

## Targets

Counted against 2 messages a day from day one, with follow-ups due 5 days after a message with no reply. "Make it 3 a day": `run.py settings set outreach.per_day 3`; "stop counting": `outreach.per_day 0`.

**Who "find a person" looks for:** their field's leaders by real titles. If `page.contact_search` in `profile/settings.toml` is empty and their field pack (`${CLAUDE_PLUGIN_ROOT}/engine/starter/fields/`) names leaders under `[page]`, offer to use them: `run.py settings set page.contact_search '<the pack's value>'`. Otherwise the search looks for the head of the job's own function.

## Don't

- Don't look anyone up, open a profile, guess an email, or send anything.
- Don't predict a reply, a referral or its odds.
- Don't put anything in a message that `about-me.md` doesn't confirm.
