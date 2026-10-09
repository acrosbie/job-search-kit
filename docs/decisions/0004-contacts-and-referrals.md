# 4. Contacts, referrals and outreach

- **Status:** proposed 2026-10-09. Needs answers to the questions at the end before it's built.
- **Date:** 2026-10-09
- **Evidence:** the search the kit was built from (phase 6), as of 2026-10-09, and its own outreach playbook.

## The problem

The kit finds jobs and tracks applications well, but a search is won through people, and the kit has almost nowhere to keep them.

- Of 60 applications, 1 has a contact and none has a follow-up. 34 closed as "no reply" at day 21.
- On the day of the quality pass, 8 top picks had nobody to follow up with. The page's "find a person" card can open a search, but the name found goes into one free-text field on one application, with no role, no history and no next step.
- Sourcing is near its ceiling: about 10 to 13 new postings a week fit, after reading close to 600 boards. The rest of the volume, by that search's own analysis, comes through referrals.
- The search's own playbook already says what works: an announcement post first; former colleagues, two a day; vendor account teams; hiring managers, meaning the support or CX leader, not the recruiter; follow-ups to **people** five to seven days after sending. Its rule: "the person column is the load-bearing one". The kit runs none of this.

## Decision (proposed)

1. **Contacts are records.** `data/contacts.json` holds one record per person:
   - `id`, `name`, `company`, `title` (in the user's words), `kind` (recruiter, hiring manager, referrer, colleague, other), `how_known` (the user's words);
   - `source`: you (said in chat), interview (met in one), or connections (the LinkedIn export);
   - `profile` (a link the user gave, if any), `applications` (ids);
   - `touches`: date, channel (email, LinkedIn, phone, in person, other), in or out, the user's note;
   - `next_touch`: date and why; `status`: active, waiting or done.

   An application's `contact` becomes a link to a contact; the name it holds today is moved into a record, the same way ids were put right.
2. **Names come only from the user.** Said in chat, pasted, met in an interview, or in the connections export they download from LinkedIn themselves (`Connections.csv`: first and last name, profile link, company, position, connected on). Claude never looks a person up, never opens a profile, never guesses an email. The page's LinkedIn search stays a link the user opens.
3. **Who you know there.** For each job worth applying to and each open application, the engine lists contacts at the same company (names compared the way applications are matched to postings). Triage and Today offer that route before the cold apply: "You know 2 people at Acme: ask Dana about a referral first?"
4. **The referral window.** When the cooldown rule turns a job away because of a recent application at the same company (applied 21 September, window reopens 21 October), the engine records a next touch for that date: "ask about a referral at Acme". `start` lists it when it's due.
5. **Outreach as a habit, counted.** `[outreach]` settings hold a daily and a weekly target (the playbook's 2 messages a day, follow-ups 5 to 7 days after sending). Today shows "1 of 2 messages today" and what's due; the weekly review counts touches and replies. Claude drafts each message from confirmed facts only, in the user's own templates where they have them; the user sends it. Nothing is ever sent.
6. **Follow-ups go to people.** An application whose company has a contact is routed to "send", as today; a touch recorded on that contact counts as its follow-up. The rest go to "find a person", which now saves a contact record.
7. **A `network` skill** owns the phrases about people: "who do I know at Acme", "I messaged Dana", "Dana replied", "import my LinkedIn connections", "who should I reach out to today", "draft a referral ask". Track keeps applications; network keeps people.
8. **The page** gets a People section (next touch due first) and, on each job, "You know: Dana, former colleague". Contacts live in the page's storage in the user's Claude account like the rest of the page (decision 2).

## Options considered

1. **Contacts as records in the folder (proposed).** One person can be on several applications, or on none yet. Their history survives a closed application.
2. **More fields on each application.** Can't hold a referrer for two jobs, or someone the user knows at a company they haven't applied to, which is exactly the referral route.
3. **A CRM or a spreadsheet the kit writes to.** Data leaves the folder, and setup gets longer.
4. **Claude finds the people.** Against the kit's rule, for good reasons: names found that way are often wrong, and they are other people's details, collected without asking.

## Privacy

Contacts are other people's names and jobs. The kit keeps only what the user gives it. From the connections export it keeps name, company, position, profile link and connected-on, and **not** email addresses, unless the user adds one for a person. Snapshots include `contacts.json`, so the future "delete my data" command clears snapshots too.

## What this changes

- **New:** `data/contacts.json`; `jobkit/contacts.py`; commands `contact add | touch | list | match` and `import-connections FILE`; `start` steps `contact_due` and `referral_window`; the page's People section; the `network` skill; `[outreach]` settings.
- **Changed:** an application's contact becomes a link; `due`'s routes look at contacts; triage offers the referral route first; the weekly review counts outreach.

## Questions for the reviewer

1. **Email addresses from the export:** proposed not to keep them unless the user adds one. Agreed?
2. **Targets:** count against the playbook's 2 messages a day by default, or only once the user sets a target?
3. **Who to search for:** the "find a person" search derives the field from the role's title, so "Customer Support Systems Administrator" searches for systems administrators. The playbook says to search for the support or CX leader by real titles ("Director of Customer Support", "Senior Manager, Customer Support"), never "Support Technology". Proposed: the field pack names the leaders' titles, and the search uses those. Agreed?
4. **A recruiter who writes first, with no posting:** a contact and a lead, with the playbook's scam check (the sending domain) as a flag. In this decision, or a separate one?

## Build order

1. Contact records, the move of existing contact names, and the connections import.
2. Who you know there, and the referral window.
3. The `network` skill.
4. The page's People section.
5. Outreach targets and counts.
