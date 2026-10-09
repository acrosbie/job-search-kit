# A job's summary

What the user reads first about a job, on their jobs page and in chat: how a friend who knows them and has read the posting would put it. The verdict's note, rule and quote stay as the record behind it; the page folds them away as "Behind the call".

Write it for every Worth applying and Your call, as a small JSON file, and pass it with the verdict (`mark ... --summary FILE`), or on its own for a job already decided (`summarize KEY --summary FILE`). The engine checks it and refuses one that slips, naming the part; fix that part and send it again.

```json
{
 "headline": "Your strongest match this week.",
 "fits": ["It's the Zoom job at a new company: making support work at scale for \"tens of millions\" of users, through \"chatbot and agent support experiences\"."],
 "enjoy": "It's measured on real outcomes like contact rate, the kind of metrics you like digging into.",
 "watch": ["Three days a week in San Mateo: inside your hybrid zone, but a real commute from San Jose.",
           "It's a role with no team, and the range sits right around your $180K ask."],
 "ask": "How much does the role shape the tools, and how much write the processes? Ask on the first call.",
 "tailor": ["Lead with your two migrations, framed as programs."],
 "mirror": ["end to end service delivery", "agent tooling"]
}
```

| Part | What it says | Needed |
|---|---|---|
| `headline` | One plain sentence with the honest take: "Your best match this week", "Great work, low pay", "A long shot worth one try" | Always |
| `fits` | Why it fits: 1 to 3 points tying the job's real work to what they've done. One short quote from the posting, in quotation marks | 1 to 3 |
| `enjoy` | What they'd probably enjoy, from what they said they enjoy in `what-i-want.md`, matched to the job's day-to-day | If there's something |
| `watch` | Watch-outs in everyday terms: pay against their ask in dollars, days in the office and the commute from where they live, the team's size, the gaps a hiring manager will probe | 0 to 4 |
| `ask` | The one question that would change their mind, and when to ask it | Your call |
| `tailor` | The resume changes for this job | Worth applying, 1 to 3 |
| `mirror` | The posting's own words worth using, short phrases | Up to 8 |

**Writing rules:**
- Always "you". Never "he", "she", "his", "her", "the user" or "the candidate".
- No rule numbers, abbreviations or shorthand ("in lane", "tilt", "IC PM"). Say it in everyday words.
- Each part starts with a capital letter and stays short: the headline under 100 characters, each point under about 240.
- Amounts in dollars, against their ask: "the top of the range is $18K under your $180K ask".
- Office time in days and places: "three days a week in San Mateo", not policy words.
- Every claim about the user comes from Confirmed or Owned hands-on in `about-me.md`, as everywhere else. Every quote is the posting's own words; the engine checks.
- Don't predict odds or how competitive it is.

**In chat,** give the same shape, briefly: the headline, one line of why, and the question or the resume change.
