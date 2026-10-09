"""The engine's fingerprint: one short hash of every file the engine is made of.

A user's copy of the engine (<folder>/.kit/engine) is refreshed when its fingerprint differs from
the plugin's. A version number only moves when someone remembers to move it; the fingerprint moves
with any change to any file, and a test fails until the one recorded in __init__.py is the one the
files have (tools/update_fingerprint.py writes it). Line endings don't count: a copy made on Windows
may turn them into CRLF.
"""

import hashlib
import os

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDED_IN = "jobkit/__init__.py"  # holds the fingerprint, so it can't be part of it


def compute(engine=ENGINE):
    h = hashlib.sha1()
    for top, dirs, names in os.walk(engine):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(names):
            path = os.path.join(top, name)
            rel = os.path.relpath(path, engine).replace(os.sep, "/")
            if rel == RECORDED_IN or name.endswith(".pyc"):
                continue
            with open(path, "rb") as f:
                body = f.read().replace(b"\r\n", b"\n")
            h.update(rel.encode("utf-8") + b"\0" + body + b"\0")
    return h.hexdigest()[:16]
