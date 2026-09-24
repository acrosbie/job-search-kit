#!/usr/bin/env python3
"""
Platform check for job-search-kit, phase 0. Throwaway.

Answers, with evidence: where this script runs, which job-board hosts it can reach,
whether it can fetch one real board, and whether it can read and write the user's
connected folder. Standard library only. Writes nothing outside its output folder.

    python3 probe.py [check|scheduled] [--folder PATH] [--out DIR] [--board TOKEN]

--folder  the user's connected folder. Output goes to <folder>/platform-check/ when the
          script can write there; otherwise to --out, and Claude copies it across.
--out     fallback output folder (default: <temp>/platform-check-output)
--board   the public Greenhouse board to fetch (default: greenhouse, Greenhouse's own)
"""

import concurrent.futures as cf
import datetime as dt
import getpass
import html
import json
import os
import platform
import re
import socket
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; job-search-kit-platform-check/0.1)"
TIMEOUT = 20

# One small request per job-board system the reference scanner reads, plus two controls.
# Any HTTP answer, even 404, means the host was reached.
HOSTS = [
    ("Greenhouse", "https://boards-api.greenhouse.io/v1/boards/greenhouse/jobs"),
    ("Ashby", "https://api.ashbyhq.com/posting-api/job-board/ashby"),
    ("Lever", "https://api.lever.co/v0/postings/lever?mode=json&limit=1"),
    ("SmartRecruiters", "https://api.smartrecruiters.com/v1/companies/smartrecruiters/postings?limit=1"),
    ("Workday", "https://workday.wd5.myworkdayjobs.com/"),
    ("Himalayas", "https://himalayas.app/robots.txt"),
    ("Rippling", "https://api.rippling.com/"),
    ("control: pypi.org (package manager)", "https://pypi.org/robots.txt"),
    ("control: example.com (any other site)", "https://example.com/"),
]


# ---------------------------------------------------------------- redaction

HOME = os.path.expanduser("~")
try:
    USER = getpass.getuser()
except Exception:
    USER = ""
ON_HOST = platform.system() in ("Windows", "Darwin")


def redact(s):
    """Keep the user's home folder and username out of anything written or printed."""
    if not isinstance(s, str):
        return s
    for h in {HOME, HOME.replace("\\", "/")}:
        if len(h) > 3:
            s = s.replace(h, "~")
    if len(USER) >= 3 and USER.lower() not in ("root", "user", "claude", "runner", "sandbox"):
        s = re.sub(r"(?i)(?<![a-z0-9])" + re.escape(USER) + r"(?![a-z0-9])", "<user>", s)
    return s


def redact_all(obj):
    if isinstance(obj, dict):
        return {k: redact_all(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_all(v) for v in obj]
    return redact(obj)


# ---------------------------------------------------------------- where am I

def environment(folder, script_dir):
    mem = ""
    try:
        with open("/proc/meminfo") as f:
            kb = int(f.readline().split()[1])
            mem = f"{kb // 1024} MB"
    except Exception:
        pass
    return {
        "python": sys.version.split()[0],
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "computer name": "(host computer, not recorded)" if ON_HOST else socket.gethostname(),
        "cpus": os.cpu_count(),
        "memory": mem,
        "working folder": os.getcwd(),
        "script folder": script_dir,
        "CLAUDE_PLUGIN_ROOT": os.environ.get("CLAUDE_PLUGIN_ROOT", "(not set)"),
        "connected folder given": folder or "(none)",
        "connected folder visible to script": bool(folder) and os.path.isdir(folder),
        "top-level folders": sorted(os.listdir("/"))[:40] if not ON_HOST else [],
        "environment variable names": sorted(os.environ),  # names only, never values
    }


# ---------------------------------------------------------------- network

def get(url, limit=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, */*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, (resp.read(limit) if limit else resp.read())


def reach(name, url):
    t = time.time()
    try:
        status, _ = get(url, limit=1024)
        verdict = f"reached (HTTP {status})"
    except urllib.error.HTTPError as e:
        deny = e.headers.get("x-deny-reason") if e.headers else None
        verdict = f"blocked by proxy ({deny})" if deny else f"reached (HTTP {e.code})"
    except urllib.error.URLError as e:
        r = e.reason
        msg = str(r)
        if "Tunnel connection failed" in msg:
            verdict = f"blocked by proxy ({msg})"
        elif isinstance(r, socket.gaierror):
            verdict = f"no DNS answer ({msg})"
        elif isinstance(r, ssl.SSLError):
            verdict = f"TLS certificate problem ({msg})"
        elif isinstance(r, (socket.timeout, TimeoutError)):
            verdict = "timed out"
        else:
            verdict = f"failed ({type(r).__name__}: {msg})"
    except (socket.timeout, TimeoutError):
        verdict = "timed out"
    except Exception as e:
        verdict = f"failed ({type(e).__name__}: {e})"
    return {"system": name, "url": url, "result": verdict, "seconds": round(time.time() - t, 2)}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(s):
    p = _Text()
    p.feed(s or "")
    return re.sub(r"\s+", " ", "".join(p.parts)).strip()


def fetch_board(token, details=3):
    """The same two Greenhouse calls the reference scanner makes: the job list, then details."""
    t = time.time()
    base = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        _, body = get(base)
        jobs = [{"id": j["id"], "title": j.get("title", ""), "location": (j.get("location") or {}).get("name", ""),
                 "url": j.get("absolute_url", ""), "updated": (j.get("updated_at") or "")[:10]}
                for j in json.loads(body).get("jobs", [])]
    except Exception as e:
        return {"board": token, "ok": False, "error": f"{type(e).__name__}: {e}", "seconds": round(time.time() - t, 2)}
    got = 0
    for j in jobs[:details]:
        try:
            _, d = get(f"{base}/{j['id']}")
            text = html_to_text(html.unescape(json.loads(d).get("content", "")))
            j["description chars"] = len(text)
            got += 1
        except Exception as e:
            j["description error"] = f"{type(e).__name__}: {e}"
    return {"board": token, "ok": True, "jobs": len(jobs), "details fetched": got,
            "seconds": round(time.time() - t, 2), "list": jobs}


# ---------------------------------------------------------------- the jobs page

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>My jobs (test)</title>
<style>
 body{font:16px/1.45 system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#1b1b1b;background:#fff}
 h1{font-size:22px;margin:0 0 4px} p.note{color:#555;margin:0 0 20px}
 ol{padding-left:28px} li{margin:0 0 14px} .t{font-weight:600} .l{color:#555;font-size:14px}
 button{font:inherit;font-size:14px;margin:6px 6px 0 0;padding:4px 12px;border:1px solid #888;border-radius:6px;background:#f4f4f4;cursor:pointer}
 button.on{background:#1b5e20;color:#fff;border-color:#1b5e20}
 #copy{font-size:16px;padding:8px 16px;margin-top:8px} #out{width:100%;height:90px;margin-top:10px;display:none}
 @media (prefers-color-scheme: dark){body{background:#161616;color:#eee} p.note,.l{color:#aaa} button{background:#2a2a2a;color:#eee}}
</style></head><body>
<h1>My jobs (test)</h1>
<p class="note">Test page from the platform check. Jobs from Greenhouse's public job board, fetched __WHEN__.
Pick Keep, Skip or Not sure, then press "Copy my choices" and paste the result into your Claude task.</p>
<ol id="jobs"></ol>
<button id="copy">Copy my choices</button> <span id="msg"></span>
<textarea id="out" readonly></textarea>
<script>
var JOBS = __JOBS__;
var picks = {};
var ol = document.getElementById("jobs");
JOBS.forEach(function (j, i) {
  var li = document.createElement("li");
  var a = document.createElement(j.url ? "a" : "span");
  a.className = "t"; a.textContent = j.title; if (j.url) { a.href = j.url; a.target = "_blank"; a.rel = "noopener"; }
  var loc = document.createElement("div"); loc.className = "l"; loc.textContent = j.location || "location not stated";
  li.appendChild(a); li.appendChild(loc);
  ["keep", "skip", "not sure"].forEach(function (v) {
    var b = document.createElement("button"); b.textContent = v.charAt(0).toUpperCase() + v.slice(1);
    b.onclick = function () {
      picks[i + 1] = v;
      Array.prototype.forEach.call(li.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
      b.classList.add("on");
    };
    li.appendChild(b);
  });
  ol.appendChild(li);
});
document.getElementById("copy").onclick = function () {
  var keys = Object.keys(picks).sort(function (a, b) { return a - b; });
  var text = keys.length ? "Platform check choices: " + keys.map(function (k) { return k + " " + picks[k]; }).join(", ")
                         : "Platform check choices: none picked";
  var out = document.getElementById("out"), msg = document.getElementById("msg");
  function manual() { out.style.display = "block"; out.value = text; out.focus(); out.select();
    msg.textContent = "Copy the text below (Ctrl+C), then paste it into Claude."; }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(function () { msg.textContent = "Copied. Paste it into Claude."; }, manual);
  } else { manual(); }
};
</script></body></html>
"""


def write_page(path, board, when):
    jobs = [{"title": j["title"], "location": j["location"], "url": j["url"]} for j in board.get("list", [])[:15]]
    data = json.dumps(jobs).replace("</", "<\\/")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(PAGE.replace("__WHEN__", html.escape(when)).replace("__JOBS__", data))


# ---------------------------------------------------------------- output

def pick_output(folder, out):
    """The folder itself when the script can write there, otherwise the fallback."""
    if folder and os.path.isdir(folder):
        target = os.path.join(folder, "platform-check")
        try:
            os.makedirs(target, exist_ok=True)
            probe = os.path.join(target, ".write-test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return target, "direct: the script wrote into the connected folder"
        except Exception as e:
            reason = f"folder visible but not writable ({type(e).__name__}: {e})"
    elif folder:
        reason = "folder not visible to the script"
    else:
        reason = "no folder given"
    os.makedirs(out, exist_ok=True)
    return out, f"fallback: {reason}; Claude must copy the output across"


def bump_state(target, when, mode, where):
    path = os.path.join(target, "state.json")
    state = {"runs": 0, "history": []}
    found = os.path.exists(path)
    if found:
        try:
            with open(path, encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
    state["runs"] = int(state.get("runs", 0)) + 1
    state.setdefault("history", []).append({"when": when, "mode": mode, "ran on": where})
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=2)
    return state["runs"], found


def summary(r):
    e, b = r["environment"], r["board fetch"]
    reached = sum(1 for h in r["reachability"] if h["result"].startswith("reached") and not h["system"].startswith("control"))
    lines = [
        f"# Platform check, {r['mode']} run {r['run number']}",
        "",
        f"- When: {r['when']} (UTC {r['when utc']})",
        f"- Ran on: {r['ran on']}, Python {e['python']}, {e['cpus']} CPUs, {e['memory'] or 'memory unknown'}",
        f"- Output: {r['output route']}",
        f"- Saved state found from an earlier run: {'yes' if r['state found'] else 'no'} (this is run {r['run number']})",
        f"- Job-board systems reached: {reached} of {len(HOSTS) - 2}",
        "",
        "| System | Result | Seconds |",
        "|---|---|---|",
    ]
    lines += [f"| {h['system']} | {h['result']} | {h['seconds']} |" for h in r["reachability"]]
    lines.append("")
    if b.get("ok"):
        lines.append(f"Greenhouse board `{b['board']}`: {b['jobs']} jobs listed, {b['details fetched']} descriptions fetched, "
                     f"{b['seconds']} s.")
    else:
        lines.append(f"Greenhouse board `{b['board']}`: fetch failed, {b.get('error')}.")
    return "\n".join(lines) + "\n"


def main(argv):
    mode = "scheduled" if argv and argv[0] == "scheduled" else "check"
    args = {"--folder": "", "--out": os.path.join(tempfile.gettempdir(), "platform-check-output"), "--board": "greenhouse"}
    for i, a in enumerate(argv):
        if a in args and i + 1 < len(argv):
            args[a] = argv[i + 1]
    folder = args["--folder"]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    now = dt.datetime.now().astimezone()
    when = now.isoformat(timespec="seconds")
    stamp = now.strftime("%Y%m%d-%H%M%S")
    env = environment(folder, script_dir)
    where = f"{env['os']}, {env['computer name']}"

    with cf.ThreadPoolExecutor(max_workers=len(HOSTS)) as pool:
        hosts = list(pool.map(lambda h: reach(*h), HOSTS))
    board = fetch_board(args["--board"], details=0 if mode == "scheduled" else 3)

    target, route = pick_output(folder, args["--out"])
    runs, found = bump_state(target, when, mode, redact(where))
    result = redact_all({
        "mode": mode, "when": when, "when utc": now.astimezone(dt.timezone.utc).isoformat(timespec="seconds"),
        "ran on": where, "run number": runs, "state found": found, "output route": route,
        "output folder": target, "environment": env, "reachability": hosts,
    })
    result["board fetch"] = board  # public job data, left as the board published it

    text = summary(result)
    with open(os.path.join(target, f"run-{stamp}.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    with open(os.path.join(target, f"run-{stamp}.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if mode == "scheduled":
        reached = sum(1 for h in hosts if h["result"].startswith("reached") and not h["system"].startswith("control"))
        log = os.path.join(target, "scheduled-log.md")
        new = not os.path.exists(log)
        with open(log, "a", encoding="utf-8", newline="\n") as f:
            if new:
                f.write("| When | Ran on | Output | Boards reached | Greenhouse jobs | Run |\n|---|---|---|---|---|---|\n")
            f.write(redact(f"| {when} | {where} | {route.split(':')[0]} | {reached} of {len(HOSTS) - 2} | "
                           f"{board.get('jobs', 'failed')} | {runs} |\n"))
    elif board.get("ok"):
        write_page(os.path.join(target, "My jobs (test).html"), board, when)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(text)
    print(f"Files written to: {redact(target)}")
    print(f"Output route: {route}")


if __name__ == "__main__":
    main(sys.argv[1:])
