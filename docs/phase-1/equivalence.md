# Phase 1: the engine matches the reference scanner

**Result: 0 differences.** On 2026-09-24 the reference scanner's full watchlist was recorded once, live, and replayed through both the reference scanner (Python 3.12) and the kit's engine (Python 3.10, the version Cowork's workspace on the user's computer has). Both started from an empty record at the same pinned time, and the engine used a settings file converted from the reference configuration by `tools/import_reference.py`.

| Compared | Count | Differences |
|---|---|---|
| Boards read (none failed) | 590 | 0 |
| Postings read | 57,348 | 0 |
| Postings matched, by key | 186 | 0 |
| New postings for triage | 137 | 0 |
| Automatic rejects: status and exact reason text | 49 | 0 |
| of which: outside the user's area, no remote wording | 27 | 0 |
| of which: remote-only area, no remote wording | 1 | 0 |
| of which: phrase rule | 7 | 0 |
| of which: under the pay line | 14 | 0 |
| Postings with flags (exact flag text) | 71 | 0 |
| Saved descriptions, byte for byte | 186 | 0 |
| Per-board counts (jobs, matched, dropped on title, dropped on place) | 590 boards | 0 |
| Run totals, and every title read (`titles-latest.tsv`) | 1 run | 0 |

**The check can fail.** With two deliberate changes to the converted settings (one flag's wording, and the pay line), the same comparison reported 43 differences. The settings were then restored.

**How to repeat it:** `tools/import_reference.py` converts the reference files into a folder outside this repo, then `tools/compare_with_reference.py record` and `compare` run the two steps. The recording, the converted settings and the detailed results stay in that folder, because they are one person's data. This page carries only counts.

**One behaviour deliberately differs, and doesn't show here:** the reference never marks postings from `/api/jobs` careers sites as gone, because it builds their key prefix as `careers_api-` while their keys say `careers-api-`. The engine uses the key's own spelling. The comparison starts from an empty record, so no posting could go missing, and the difference can't appear.
