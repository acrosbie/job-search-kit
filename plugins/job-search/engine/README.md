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
| `add FILE` | Registers a posting saved by hand as `data/postings/manual-<company>-<short>.md`, with the same header a scan writes | the new record |
| `discover SLUG [--page URL]` | Which public job board a company uses; with `--page`, also reads its careers page for an embedded board | JSON: `boards`, `embedded`, `unsupported` |
| `version` | Engine and Python version | text |

`scan` also takes `--record DIR` (save every board answer to a cassette folder), `--replay DIR` (read answers from one, with no network) and `--as-of TIME` (pin the clock, for replays).

**Exit codes:** 0 done; 1 something is wrong with the folder or its files (the message names it); 2 a mistake in the command; 3 refused on purpose. `mark` refuses when Claude tries to overwrite a verdict the **user** made (their decision stands; `--force` only when they ask), and when anyone but the user marks a posting `applied`.

**The scan summary** has `boards`, `failed`, `read`, `dropped_title`, `dropped_location`, `matched`, `new`, `rejected_by_rule`, `total_seen`, and four lists:
- `new_postings`: key, company, title, location, flag, salary. This is the queue for triage.
- `rejected_postings`: the same, plus `rule` and `reason`, in the user's words.
- `failures`: board, slug, error. A failed board keeps its old postings.
- `check_by_hand`: companies with `ats = "manual"` and their careers URL.

## The user's folder

| File | Holds | Written by |
|---|---|---|
| `profile/settings.toml` | What screens postings (below) | setup, tune |
| `profile/companies.toml` | `[[company]]` entries: `name`, `slug`, `ats`, and `token`, or `host`, `tenant`, `site` for Workday, `host` for careers sites, `queries` for Himalayas, `careers_url` for manual ones | setup, tune, discover |
| `data/postings.json` | `{"postings": {key: record}, "boards": {slug: health}}` | engine |
| `data/postings.backup.json` | The previous `postings.json` | engine |
| `data/postings/<key>.md` | One saved description per posting | engine, `add` |
| `data/applications.json` | `{"applications": [...]}`. The engine only reads it, to flag postings already applied to (same link, or same company and a matching title) | track |
| `data/decisions.log` | One JSON object a line: `at`, `date`, `key`, `company`, `title`, `verdict`, `reason`, `by` (`rule`, `claude` or `user`), plus `rule` for automatic rejects and `reverses` when a user verdict contradicts the last one | engine, `mark` |
| `data/runs.log` | One JSON object per scan: the summary counts | engine |
| `data/titles-latest.tsv` | Every title read on the last scan, for testing a title change on real data | engine |

A **posting key** is `<system>-<company slug>-<job id>` (for example `greenhouse-acme-4012`); it ties postings, verdicts and applications together and never changes. **Statuses:** `new`, `worth_applying`, `your_call`, `not_a_fit`, `skipped`, `applied`. A posting record carries `status`, `company`, `title`, `location`, `url`, `posted`, `source`, `salary`, `pay_low`, `pay_high`, `flag` (text), `flags` (`code` and `text` each), `first_seen`, `last_seen`, `gone`, `file`, and for a verdict, `note`, `rule` and `triaged`.

**The engine never deletes a file**, because Cowork's workspace on the user's computer isn't allowed to. It writes in place, and a posting that disappears from its board gets a `gone` date.

## settings.toml

Every pattern is a case-insensitive regular expression; a missing or empty one matches nothing. `tests/fixtures/sample-folder/profile/settings.toml` is a complete example.

| Section | Keys | Used for |
|---|---|---|
| `[you]` | `timezone` (for example `America/New_York`) | Dates the user reads |
| `[titles]` | `function`, `level`, `exclude` | A title needs a function word **and** a level word, and no exclusion |
| `[places]` | `remote`, `hybrid_ok`, `remote_only`, `in_country`, `country_wide`, `abroad` | The listed location: `hybrid_ok` passes; `remote_only` and `in_country` pass only if the description says remote; `abroad` is dropped unless a home place is also listed |
| `[description]` | `remote_language`, `contract`, `onsite_days`, `onsite_place` | Remote wording; flags for contract work and 4–5 days in the office (never rejects) |
| `[[phrase_rejects]]` | `name`, `phrases`, `min_distinct`, `same_as`, `reason` | Reject when enough distinct phrases appear, for example quota language |
| `[pay]` | `reject_if_top_below` (0 = off) | Reject when the posted range tops out below this |
| `[workday]` | `country_facet`, `max_total` | Workday boards are narrowed to one country and capped |
| `[triage]` | `cooldown_days` (default 30) | One application per company in this many days; `queue` reports what applies |
| `[labels]` | `flag_*`, `reason_*` | Wording for every flag and reason. Plain-language defaults are in `jobkit/settings.py` |

Rejects apply in this order, and the first one wins: location, phrase rules, pay.

## Tests

From the repo root, on Python 3.10 and on a current Python:

```
python -m unittest discover -s tests -t .
```

`tests/recorded/sample` replays 29 public boards for a made-up job seeker. `tools/compare_with_reference.py` re-runs the full comparison with the reference scanner, for anyone who has it.
