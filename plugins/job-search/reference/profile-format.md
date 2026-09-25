# The user's profile

Three files in `<folder>/profile/` describe the user in their own terms. Setup writes them from the user's answers. Triage reads them for every posting. Nothing in them is ever invented: a claim the user hasn't confirmed is marked unconfirmed, and never used.

## about-me.md: their background

```
# About me

## Confirmed
| Claim | How it was established |

## Corrected (never use the old version)
| Was | Now | Why |

## Not confirmed yet (never use in an application)
- ...

## Owned hands-on, and worked alongside
| Owned hands-on | Worked alongside (never claim as owned) |

## Facts postings check
Degrees, certifications, clearances, languages, industries, years managing people, years managing managers.

## How to present me, by kind of role
- For <kind of role>: lead with ...
```

When triage gives tailoring advice, every claim in it comes from **Confirmed** or **Owned hands-on**. Something that isn't there is not experience the user lacks. It's a question to ask them.

## what-i-want.md: what they're looking for

```
# What I want

| Question | My answer, in my words | Date |
```

Answers are kept in the user's own words. When an answer changes, the old one stays below it, marked "was", with its date.

## rules.md: the screening rules

```
# My screening rules

## Rules: any one makes a posting Not a fit
Checked in order. Numbers never change; a retired rule keeps its number, marked retired.

### Rule N: <plain name>
- Not a fit when: <what the posting says>
- Doesn't count: <look-alikes that don't fire it>
- Why: <the user's answer that created it, quoted>, <date>
- Changes: <date: what changed and what it flipped on saved postings>

## Flags: noted, never reject on their own
### <plain name>
- When: <what the posting says>
- What to do: <a question to ask, or just note it>

## Rules the scan applies before triage
<Rules the engine applies from settings.toml, listed so triage knows they've already run.>
```

## settings.toml

This holds the engine's mechanical settings: titles, places, pay line, phrase rules, cooldown and wording. See `${CLAUDE_PLUGIN_ROOT}/engine/README.md`. The user never edits it; Claude changes it, explaining and testing each change first.
