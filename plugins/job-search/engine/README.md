# The engine

Fetches public job boards, screens postings against the user's settings, and keeps the records in the user's folder. Python standard library only; runs on **Python 3.10** and later (Cowork's workspace on the user's computer has 3.10). Claude runs it; the user never sees it.

It is a port of a working personal scanner, and matched it with 0 differences over 590 boards (`docs/phase-1/equivalence.md`).

## Running it

```
python3 run.py <command> --folder "<the user's Job Search folder>" [options]
```

`run.py` works from any folder, so setup can copy this whole `engine/` folder into the user's folder. It writes no `__pycache__`.

| Command | What it does | Prints |
|---|---|---|
| `scan [--only SLUG]` | Reads every board in `companies.toml`, saves new matches, applies the automatic rejects, logs the run | JSON summary (below) |
| `queue` | The postings waiting for triage, each with applications to the same company within `[triage] cooldown_days` and the other queued postings from that company | JSON: `count`, `cooldown_days`, `postings` |
| `show KEY` | A saved posting, as text | the posting |
| `mark KEY STATUS --by claude\|user [--note TEXT] [--force]` | Records a verdict in `postings.json` and `decisions.log` | the logged row |
| `add FILE [--text-from link\|pasted] [--anyway]` | Saves a posting the user found (LinkedIn, a company site) from a file anywhere with the scan's header: `# Title`, `- Company:`, `- Location:`, `- URL:`, `- Posted:`, `---`, then the description. Names it `manual-<company>-<LinkedIn job id, or title>` and screens it as a scan would; a title outside the search is flagged, never dropped. Refuses a duplicate (same link, or same company and title), naming the one saved. If the user already said they applied to it (an application recorded by company and role), joins the two and marks it applied | the new record, with `application` when joined |
| `add-link URL [--company NAME]` | A link to a board the engine reads (Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Rippling): reads that board and saves the posting exactly as a scan would, with the scan's key | the record, or `saved: false` with `why`: `not_a_board_link`, `board_failed` or `not_on_board` |
| `apply KEY` or `apply --company C --role R [--url U]` | The user applied: `--date`, `--estimated`, `--channel company_site\|linkedin\|referral\|other`, `--top-pick yes\|no`, `--contact`, `--note`. Records the application and marks the posting applied by the user. Saying it twice updates the one record. `mark KEY applied --by user` does the same | the application |
| `track ID [STATUS]` | What happened next: `replied`, `screen`, `interview`, `offer`, `rejected`, `withdrawn`, `closed`, or `followed_up` (an event, not a status); also `--contact`, `--top-pick`, `--channel`, `--note`, `--date` | the application |
| `applications` | Every application with `days`, `closes_on`, `due` and `route` | JSON |
| `due` | Closes every application still at plain `applied` after `[tracking] presume_after_days`, then lists the follow-ups due by route: `send` (a contact is recorded), `find_person` (a top pick, nobody known), `closing` (nothing to send) | JSON: `closed_now`, `send`, `find_person`, `closing`, `open`, `last_scan_at` |
| `page` | Writes the jobs page (below). Every command that changes the records does this by itself | a summary |
| `record-choices FILE` | Records clicks from the jobs page, given as a JSON list or the pasted "Copy my choices" text, as the user's own decisions as of when they clicked: oldest first, once each, and only the last click on each job or application, skipping any the user overruled later in chat | JSON: `recorded`, `already`, `superseded`, `unknown` |
| `discover SLUG [--page URL]` | Which public job board a company uses; with `--page`, also reads its careers page for an embedded board | JSON: `boards`, `embedded`, `unsupported` |
| `init [--field support-cx\|custom] [--places us] [--timezone Area/City]` | Starts a new user's folder from `starter/`: the 589 starter boards, the defaults, a places pack and a field pack (`custom` leaves the title patterns empty for setup to build). Refuses a folder that already has a profile | JSON summary |
| `settings show` / `settings set KEY VALUE` | Reads, or changes one setting by dotted key (`titles.function`, `places.hybrid_ok`, `pay.reject_if_top_below`, `labels.reason_pay`). Checked before saving: patterns compile, numbers are numbers, keys exist, labels use only their own placeholders | JSON |
| `settings phrase-reject NAME --phrases P [--min-distinct N] [--reason T] [--same-as JSON]` | Adds or replaces one phrase rule | JSON |
| `companies list` / `companies add --name --slug --ats [--token\|--host --tenant --site\|--query ...\|--careers-url]` / `companies drop SLUG` | Edits the watched companies one entry at a time; an entry must carry what its reader needs | JSON |
| `titles [--sample N]` | From the last scan's `titles-latest.tsv`: what the title filter keeps, and near misses (a `field_words` word, or the function words without the level, or an exclusion), in places the user would take | JSON: counts and samples |
| `try-titles [--function P] [--level P] [--exclude P] [--field-words P]` | What a change to the title patterns would gain and lose on the same titles, without fetching | JSON: counts and samples |
| `version` | Engine and Python version | text |

`scan` also takes `--record DIR` (save every board answer to a cassette folder), `--replay DIR` (read answers from one, with no network) and `--as-of TIME` (pin the clock, for replays).

**Exit codes:** 0 done; 1 something is wrong with the folder or its files, or a posting or application isn't there (the message names it); 2 a mistake in the command; 3 refused on purpose. `mark` refuses when Claude tries to overwrite a verdict the **user** made (their decision stands; `--force` only when they ask), and when anyone but the user marks a posting `applied`. `add` and `add-link` refuse a duplicate. `track` refuses `presumed_rejected`, which only the day-21 close sets.

**The scan summary** has `boards`, `failed`, `read`, `dropped_title`, `dropped_location`, `matched`, `new`, `rejected_by_rule`, `total_seen`, and four lists:
- `new_postings`: key, company, title, location, flag, salary. This is the queue for triage.
- `rejected_postings`: the same, plus `rule` and `reason`, in the user's words.
- `failures`: board, slug, error. A failed board keeps its old postings.
- `check_by_hand`: companies with `ats = "manual"` and their careers URL.

Every scan also runs `due`, so the summary carries `closed_day_21` (applications just closed at day 21) and `follow_ups_due` (counts by route).

## Starter data

`starter/` travels with the engine into the user's folder:
- `boards.toml`: 589 public company job boards, identifiers only.
- `defaults.toml`: patterns for contract work and days in the office, the cooldown, and Workday settings.
- `places/us.toml`: US geography. The user's own commute is added at setup as `places.hybrid_ok` and `places.remote_only`.
- `fields/support-cx.toml`: the finished support and CX field pack: titles, field words, a phrase rule and aggregator search phrases.

Other fields get their title patterns from setup's field generator.

`page/jobs-page.html` travels with the engine too: the jobs page's template (see `jobkit/page.py`).

## The user's folder

| File | Holds | Written by |
|---|---|---|
| `profile/settings.toml` | What screens postings (below) | setup, tune |
| `profile/companies.toml` | `[[company]]` entries: `name`, `slug`, `ats`, and `token`, or `host`, `tenant`, `site` for Workday, `host` for careers sites, `queries` for Himalayas, `careers_url` for manual ones | setup, tune, discover |
| `data/postings.json` | `{"postings": {key: record}, "boards": {slug: health}}` | engine |
| `data/postings.backup.json` | The previous `postings.json` | engine |
| `data/postings/<key>.md` | One saved description per posting | engine, `add` |
| `data/applications.json` | `{"applications": [...]}`, one record per application (below). The scan also reads it, to flag postings already applied to (same link, or same company and a matching title) | `apply`, `track`, `due` |
| `data/applications.backup.json` | The previous `applications.json` | engine |
| `data/decisions.log` | One JSON object a line: `at`, `date`, `key`, `company`, `title`, `verdict`, `reason`, `by` (`rule`, `claude` or `user`), plus `rule` for automatic rejects, `reverses` when a user verdict contradicts the last one, and `choice` when it came from a click on the jobs page | engine, `mark` |
| `data/page.json` | What the jobs page shows: `waiting`, `todo`, `applications`, `screened`, `counts`, `as_of` | engine |
| `data/jobs-page.html` | The jobs page with its data built in, as Claude publishes it (no document skeleton) | engine |
| `My jobs.html` | The same page as a complete web page, at the top of the folder | engine |
| `data/runs.log` | One JSON object per scan: the summary counts | engine |
| `data/titles-latest.tsv` | Every title read on the last scan, for testing a title change on real data | engine |

A **posting key** is `<system>-<company slug>-<job id>` (for example `greenhouse-acme-4012`), or `manual-<company>-<short>` for one the user found; it ties postings, verdicts and applications together and never changes. **Statuses:** `new`, `worth_applying`, `your_call`, `not_a_fit`, `skipped`, `applied`. A posting record carries `status`, `company`, `title`, `location`, `url`, `posted`, `source`, `salary`, `pay_low`, `pay_high`, `flag` (text), `flags` (`code` and `text` each), `first_seen`, `last_seen`, `gone`, `file`, `num` (its number on the jobs page, given once and kept), for a verdict `note`, `rule` and `triaged`, and for one the user found `text_from` (`board`, `link` or `pasted`).

An **application** carries `id` (the posting's key, or `app-<company>-<role>` with no saved posting), `key`, `company`, `role`, `urls`, `applied_date`, `applied_date_estimated`, `channel`, `top_pick`, `level` (the level word in its title), `posted_pay`, `contact` (only a person the user named), `followed_up` (a date), `status`, `history` (each change: `date`, `at`, `status` or `event`, `by` `user` or `engine`, `note`, `choice`) and `note`. **Application statuses:** `applied`, `replied`, `screen`, `interview`, `offer`, `rejected`, `presumed_rejected`, `withdrawn`, `closed`. Only `due` sets `presumed_rejected`, and only on a plain `applied`; a status the user gives later replaces it. A follow-up is an event with a date, so it never stops the day-21 count. Older rows (the reference tracker's free-text statuses) are read in this shape, with their own words kept as `status_was`.

**The engine never deletes a file**, because Cowork's workspace on the user's computer isn't allowed to. It writes in place, and a posting that disappears from its board gets a `gone` date.

## settings.toml

Every pattern is a case-insensitive regular expression; a missing or empty one matches nothing. `tests/fixtures/sample-folder/profile/settings.toml` is a complete example.

| Section | Keys | Used for |
|---|---|---|
| `[you]` | `timezone` (for example `America/New_York`), `name` (first name, for the page's title) | Dates the user reads |
| `[titles]` | `function`, `level`, `exclude`, `field_words` | A title needs a function word **and** a level word, and no exclusion. `field_words` only marks near misses |
| `[places]` | `remote`, `hybrid_ok`, `remote_only`, `in_country`, `country_wide`, `abroad` | The listed location: `hybrid_ok` passes; `remote_only` and `in_country` pass only if the description says remote; `abroad` is dropped unless a home place is also listed |
| `[description]` | `remote_language`, `contract`, `onsite_days`, `onsite_place` | Remote wording; flags for contract work and 4–5 days in the office (never rejects) |
| `[[phrase_rejects]]` | `name`, `phrases`, `min_distinct`, `same_as`, `reason` | Reject when enough distinct phrases appear, for example quota language |
| `[pay]` | `reject_if_top_below` (0 = off) | Reject when the posted range tops out below this |
| `[workday]` | `country_facet`, `max_total` | Workday boards are narrowed to one country and capped |
| `[triage]` | `cooldown_days` (default 30) | One application per company in this many days; `queue` reports what applies |
| `[tracking]` | `follow_up_after_days` (5), `presume_after_days` (21) | When a follow-up is due, and when an application with no reply closes as presumed rejected |
| `[page]` | `url`, `version`, `route` | The user's jobs page artifact: its link, the engine version it was published from, and how Claude keeps it current (`republish` or `storage`) |
| `[labels]` | `flag_*`, `reason_*` | Wording for every flag and reason. Plain-language defaults are in `jobkit/settings.py` |

Rejects apply in this order, and the first one wins: location, phrase rules, pay.

## The jobs page

After every command that changes the records, the engine writes the page three ways from `page/jobs-page.html`: `data/page.json` (its data), `data/jobs-page.html` (with the data built in, for Claude to publish as the user's own artifact) and `My jobs.html` (a complete page the user can double-click). As an artifact, each click is saved in the user's private storage at `data/users/<id>/page/clicks/<click id>`, and the page shows the newer of its built-in data and the `data/users/<id>/page` document, which Claude can write `page.json` into. Opened from the folder, the page can't save, so it offers "Copy my choices" for pasting into chat. Either way, `record-choices` records the clicks.

## Tests

From the repo root, on Python 3.10 and on a current Python:

```
python -m unittest discover -s tests -t .
```

`tests/recorded/sample` replays 29 public boards for a made-up job seeker. `tools/compare_with_reference.py` re-runs the full comparison with the reference scanner, for anyone who has it.
