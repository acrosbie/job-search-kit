# Rule catalog

Setup builds a user's `profile/rules.md` from these templates, keeping only the rules their answers call for. Each one is written in the user's words, with the answer that created it and the date. The format is in `profile-format.md`.

Most of these lessons come from a real search:
- **Every rule needs "Doesn't count" notes.** A rule without them gets stretched to cover look-alikes.
- **A rule that never fires is a flag, not a rule.**
- **When the profile is silent, ask.** Don't assume the user lacks something.

Number the user's rules in the order they're written, and never renumber them.

## Rules: any one makes a posting Not a fit

### Technical gate
- **Ask about it when:** the user doesn't code, or doesn't want a technical role, but works near technical teams.
- **Not a fit when:** the posting requires hands-on technical work they don't do. That can be a named programming language, "X years of software engineering", software development experience, a coding or technical test, or deep hands-on work in a technical tool (write in which tools they named).
- **Doesn't count:** "familiarity with" a tool, or a technical skill listed as nice-to-have. Reports pulled from a tool they use. Write down the user's own line between "familiar" and "expert".

### Level ceiling
- **Ask about it when:** the user has managed people but not managers, or hasn't managed at all.
- **Not a fit when:** a written **requirement** is above their experience. For example "X years leading managers" when they've only led individual contributors, or "has managed a team" when they never have.
- **Doesn't count:** the same thing as a preference or nice-to-have. Title seniority on its own.

### Function, or lane
- **Ask about it when:** always. It's built from the field step: the work they want, the adjacent work they'd take, and the work they've ruled out, with their reasons.
- **Not a fit when:** the job's actual work is in an area they ruled out. Quote the line that shows what the work is, not just the title.
- **Doesn't count:** a ruled-out word that only appears in passing, such as working *with* sales rather than *in* sales.

### Hours
- **Ask about it when:** the user named hours as a constraint (no on-call, no weekends, no shifts).
- **Not a fit when:** the posting names the hours they ruled out: an on-call rotation, 24/7 coverage, named shifts, regular weekends.
- **Doesn't count:** "fast-paced"; occasional evening calls across time zones, unless they ruled those out too.

### Location
- **Ask about it when:** always. The scan applies it from `settings.toml`; triage checks only what the posting's wording actually promises.
- **Not a fit when:** the job is outside where they'd commute and the posting doesn't say remote. Or "remote" turns out to require living somewhere they won't.
- **Doesn't count:** the company's headquarters city when the role itself is remote.

### Pay
- **Ask about it when:** the user gave a lowest pay **and** said below it should be rejected rather than flagged.
- **Not a fit when:** the posted range **tops out** below their line. The scan applies this to ranges written with a dollar sign; triage applies it to the rest, converting hourly or monthly pay to a year.
- **Doesn't count:** a range whose floor is below the line but whose top reaches it.

### Company cooldown
- **Ask about it when:** always (default: one application per company per 30 days).
- **Not a fit when:** they applied to the company within the cooldown, per the queue's facts. Suggest a referral instead, if the company is right.
- **Within one batch:** only the best fit at a company is Worth applying. The others are Your call: "second <Company> job this month".

### Unmet written requirement
- **Ask about it when:** always.
- **Not a fit when:** the posting states a **written, specific** requirement that about-me.md records the user as **not** having. For example a certification they don't hold, a licence, a degree, a clearance, or an industry they've never worked in, written as required.
- **Doesn't count:**
  - a preference or nice-to-have;
  - **a years bar on experience they do have** ("10+ years" when they have nine): note it, don't reject;
  - **anything about-me.md doesn't mention either way**: that's a question (Your call), not a reject.

### Phrase rules
- **Ask about it when:** there's a kind of job that hides behind their titles, which they always turn down (for example sales or quota roles under a customer title). Set it with `settings phrase-reject`, so the scan applies it, and list it under "Rules the scan applies before triage".
- **Not a fit when:** enough distinct phrases from the list appear. Two is usual; one fires too often.

## Flags: noted, never reject on their own

- **Days in the office.** The scan quotes four or five days on-site. It's Your call when the office isn't named, or isn't one they'd commute to. Ask which office, and whether it's negotiable.
- **Contract or temporary.** Note the length. It's in scope unless they ruled contract work out, in which case it's a rule, not a flag.
- **Already applied.** The scan finds an earlier application to the same company and title: usually Skipped, as the same job.
- **Level and pay.** Note the reports, the years bar and the posted band. If they said "scope over pay" or the reverse, junior framing plus low pay is Your call, with the question theirs to answer.
- **Reporting line.** Note it only when the posting states it, and only if they said it matters.
- **Company size or stage.** Note it only where the posting says so; never guess a funding stage.
- **Sponsorship or work authorization.** If they need sponsorship and the posting says it isn't offered, that's a rule (Not a fit), not a flag. If the posting doesn't say, it's a question for the first call.
- **Travel.** Note the share of time travelling if stated. It becomes a rule only if they set a limit.

## Never

Never make a rule about age, family, health, or anything about the user that isn't about the job. Rules filter on what the job requires and offers, never on who the user is.
