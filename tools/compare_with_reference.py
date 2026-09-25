#!/usr/bin/env python3
"""
Prove the engine gives the same results as the reference scanner it was ported from.

    python tools/compare_with_reference.py record  --reference-jobs <reference jobs/ folder> --work <folder>
    python tools/compare_with_reference.py compare --reference-jobs <reference jobs/ folder> --work <folder>

<work> must already hold kit/ (made by tools/import_reference.py) and the reference's tracker is
read from <reference jobs>/../pipeline.md. Everything is written under <work>, never next to the
reference: its scanner, config and watchlist are copied into <work>/reference/ and the copy is
what runs, so the reference folder isn't touched (not even a __pycache__).

record   runs the reference once, live, over its whole watchlist, and saves every board answer
         into <work>/cassette/ (one gzip file per request).
compare  replays the cassette through the reference (this Python, which must be 3.11+) and
         through the engine (--engine-python, Python 3.10 by default, like Cowork's workspace on
         the user's computer), both from an empty start and at the same pinned time. Then it
         compares every posting, saved description, board count and run count, and writes the
         differences to <work>/results/. Exit code 0 means no differences.
"""

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(REPO, "plugins", "job-search", "engine")
sys.path.insert(0, ENGINE)
sys.dont_write_bytecode = True

from jobkit import net  # noqa: E402

AS_OF = "2026-09-24T19:00:00+00:00"  # noon Pacific: far from midnight in either time zone
STATUS = {"new": "new", "reject": "not_a_fit", "apply": "worth_applying", "maybe": "your_call",
          "skipped": "skipped", "applied": "applied"}
FIELDS = ("title", "company", "location", "url", "posted", "source", "salary", "flag", "first_seen", "last_seen")
BOARD_FIELDS = ("jobs", "matched", "dropped_title", "dropped_location")
RUN_FIELDS = ("boards", "failed", "read", "dropped_title", "dropped_location", "matched", "new", "total_seen")


def fresh_reference(ref_jobs, work):
    """A clean copy of the reference scanner, with an empty memory, under <work>/reference/."""
    home = os.path.join(work, "reference")
    if os.path.exists(home):
        shutil.rmtree(home)
    jobs = os.path.join(home, "jobs")
    os.makedirs(os.path.join(jobs, "postings"))
    for name in ("scan.py", "config.toml", "watchlist.toml"):
        shutil.copy2(os.path.join(ref_jobs, name), jobs)
    pipeline = os.path.join(os.path.dirname(ref_jobs), "pipeline.md")
    if os.path.exists(pipeline):
        shutil.copy2(pipeline, home)
    with open(os.path.join(jobs, "seen.json"), "w", encoding="utf-8") as f:
        json.dump({"postings": {}, "sources": {}}, f)
    return jobs


def load_reference(jobs):
    os.environ["SCAN_HOME"] = jobs
    spec = importlib.util.spec_from_file_location("reference_scan", os.path.join(jobs, "scan.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pin_reference_clock(ref):
    fixed = dt.datetime.fromisoformat(AS_OF).astimezone()
    ref.today = lambda: fixed.date().isoformat()
    ref.now = lambda: fixed.strftime("%Y-%m-%d %H:%M")


def record(a):
    jobs = fresh_reference(a.reference_jobs, a.work)
    ref = load_reference(jobs)
    cassette = net.Cassette(os.path.join(a.work, "cassette"))
    live = ref.fetch

    def recording_fetch(url, data=None, headers=None, timeout=ref.TIMEOUT):
        try:
            text = live(url, data=data, headers=headers, timeout=timeout)
        except Exception as e:
            cassette.write(url, data, error=net.error_record(e))
            raise
        cassette.write(url, data, text=text)
        return text

    ref.fetch = recording_fetch
    pin_reference_clock(ref)
    ref.run()
    n = len(os.listdir(cassette.folder))
    size = sum(os.path.getsize(os.path.join(cassette.folder, f)) for f in os.listdir(cassette.folder))
    print(f"\nrecorded {n} board answers, {size / 1e6:.1f} MB, in {cassette.folder}")
    return 0


def replay_reference(a):
    jobs = fresh_reference(a.reference_jobs, a.work)
    ref = load_reference(jobs)
    replay = net.Replay(os.path.join(a.work, "cassette"))
    ref.fetch = lambda url, data=None, headers=None, timeout=None: replay.request(url, data, headers)
    ref.time.sleep = lambda s: None
    pin_reference_clock(ref)
    ref.run()
    return jobs, replay.misses


def replay_engine(a):
    run = os.path.join(a.work, "engine-run")
    if os.path.exists(run):
        shutil.rmtree(run)
    shutil.copytree(os.path.join(a.work, "kit", "profile"), os.path.join(run, "profile"))
    os.makedirs(os.path.join(run, "data"))
    apps = os.path.join(a.work, "kit", "data", "applications.json")
    if os.path.exists(apps):
        shutil.copy2(apps, os.path.join(run, "data"))
    cmd = a.engine_python.split() + ["-B", os.path.join(ENGINE, "run.py"), "scan", "--folder", run,
                                     "--replay", os.path.join(a.work, "cassette"), "--as-of", AS_OF]
    done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit(f"engine failed ({done.returncode}):\n{done.stderr[-3000:]}")
    return run, json.loads(done.stdout)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def compare(a):
    ref_jobs, ref_misses = replay_reference(a)
    run, summary = replay_engine(a)

    ref = json.loads(read(os.path.join(ref_jobs, "seen.json")))
    kit = json.loads(read(os.path.join(run, "data", "postings.json")))
    rp, kp = ref["postings"], kit["postings"]
    diffs = []

    for k in sorted(set(rp) - set(kp)):
        diffs.append(f"only the reference matched {k}: {rp[k]['company']}, {rp[k]['title']}")
    for k in sorted(set(kp) - set(rp)):
        diffs.append(f"only the engine matched {k}: {kp[k]['company']}, {kp[k]['title']}")
    for k in sorted(set(rp) & set(kp)):
        r, e = rp[k], kp[k]
        if STATUS.get(r["status"], r["status"]) != e["status"]:
            diffs.append(f"{k} status: reference {r['status']}, engine {e['status']}")
        if r.get("note", "") != e.get("note", ""):
            diffs.append(f"{k} reason:\n    reference: {r.get('note', '')}\n    engine:    {e.get('note', '')}")
        if r.get("triaged") != e.get("triaged"):
            diffs.append(f"{k} triaged: reference {r.get('triaged')}, engine {e.get('triaged')}")
        for f in FIELDS:
            if r.get(f) != e.get(f):
                diffs.append(f"{k} {f}:\n    reference: {r.get(f)!r}\n    engine:    {e.get(f)!r}")
        ref_desc = os.path.join(ref_jobs, "postings", r.get("file", ""))
        kit_desc = os.path.join(run, "data", "postings", e.get("file", ""))
        if read(ref_desc) != read(kit_desc):
            diffs.append(f"{k} saved description differs")

    rb, kb = ref["sources"], kit["boards"]
    for b in sorted(set(rb) | set(kb)):
        if b not in rb or b not in kb:
            diffs.append(f"board {b} only in the {'engine' if b in kb else 'reference'}")
            continue
        for f in BOARD_FIELDS:
            if rb[b].get(f) != kb[b].get(f):
                diffs.append(f"board {b} {f}: reference {rb[b].get(f)!r}, engine {kb[b].get(f)!r}")
        if bool(rb[b].get("error")) != bool(kb[b].get("error")):
            diffs.append(f"board {b} failed in only one: reference {rb[b].get('error')!r}, engine {kb[b].get('error')!r}")

    ref_runs = [json.loads(x) for x in read(os.path.join(ref_jobs, "runs.jsonl")).splitlines() if x.strip()]
    kit_runs = [json.loads(x) for x in read(os.path.join(run, "data", "runs.log")).splitlines() if x.strip()]
    for f in RUN_FIELDS:
        if ref_runs[-1].get(f) != kit_runs[-1].get(f):
            diffs.append(f"run count {f}: reference {ref_runs[-1].get(f)}, engine {kit_runs[-1].get(f)}")
    if read(os.path.join(ref_jobs, "titles-latest.tsv")) != read(os.path.join(run, "data", "titles-latest.tsv")):
        diffs.append("titles-latest.tsv differs")
    if ref_misses:
        diffs.append(f"the reference asked for {len(ref_misses)} answers the recording doesn't have, e.g. {ref_misses[0]}")

    rejects = {}
    for v in kp.values():
        if v.get("rule"):
            kind = "phrases" if v["rule"].startswith("phrases:") else v["rule"]
            rejects[kind] = rejects.get(kind, 0) + 1
    counts = {"boards answered": kit_runs[-1]["boards"], "boards failed": kit_runs[-1]["failed"],
              "postings read": kit_runs[-1]["read"], "matched": len(kp), "new": kit_runs[-1]["new"],
              "automatic rejects by kind": rejects,
              "saved descriptions compared": len(set(rp) & set(kp)), "differences": len(diffs)}

    os.makedirs(os.path.join(a.work, "results"), exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = os.path.join(a.work, "results", f"compare-{stamp}.md")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Engine vs reference, {stamp}\n\n```json\n{json.dumps(counts, indent=1)}\n```\n\n")
        f.write("## Differences\n\n" + ("\n".join(f"- {d}" for d in diffs) if diffs else "None.") + "\n")
    print(json.dumps(counts, indent=1))
    for d in diffs[:40]:
        print(" -", d)
    print(f"\nfull result: {out}")
    return 0 if not diffs else 1


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("step", choices=("record", "compare"))
    p.add_argument("--reference-jobs", required=True, help="the reference scanner's jobs/ folder (only read)")
    p.add_argument("--work", required=True, help="where everything is written; must hold kit/")
    p.add_argument("--engine-python", default="py -3.10" if os.name == "nt" else "python3.10")
    a = p.parse_args(argv)
    a.work = os.path.abspath(a.work)
    if os.path.commonpath([a.work, REPO]) == REPO:
        print("refusing to work inside the repository: the results are personal data", file=sys.stderr)
        return 3
    if os.path.commonpath([a.work, os.path.abspath(a.reference_jobs)]) == os.path.abspath(a.reference_jobs):
        print("refusing to work inside the reference folder: it must stay untouched", file=sys.stderr)
        return 3
    if sys.version_info < (3, 11):
        print("the reference scanner needs Python 3.11 or later; run this tool with one", file=sys.stderr)
        return 2
    return record(a) if a.step == "record" else compare(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
