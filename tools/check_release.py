"""Refuse a push that changes the plugin without moving its version.

A user's Claude takes a new plugin when its version moves, and the folder's engine follows the
plugin. Eight commits from 2026-10-12 sat unpushed under 0.11.1, so nothing reached the user. This
makes the version part of every push that changes what users run.

The pre-push hook in .githooks runs it: python tools/check_release.py <what the remote has> <what's pushed>.
"""

import json
import subprocess
import sys

PLUGIN = "plugins/job-search/"
PLUGIN_JSON = PLUGIN + ".claude-plugin/plugin.json"


def _v(text):
    try:
        return tuple(int(x) for x in text.split("."))
    except ValueError:
        return ()


def problems(old_version, new_version, changed):
    """What's wrong with pushing `changed` paths when the plugin goes from `old_version` to `new_version`."""
    touched = [p for p in changed if p.startswith(PLUGIN)]
    if not touched:
        return []
    if _v(new_version) < _v(old_version):
        return [f"the plugin's version goes back, from {old_version} to {new_version}"]
    if new_version == old_version:
        return [f"{len(touched)} plugin file(s) changed since {old_version} was pushed, but the version didn't move. "
                "Bump it in plugins/job-search/.claude-plugin/plugin.json and engine/jobkit/__init__.py, "
                "with a line in engine/jobkit/news.py, in its own commit"]
    return []


def _git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def main(argv):
    old, new = argv
    version = lambda sha: json.loads(_git("show", f"{sha}:{PLUGIN_JSON}"))["version"]
    changed = _git("diff", "--name-only", old, new).splitlines()
    found = problems(version(old), version(new), changed)
    for p in found:
        print(f"push refused: {p}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
