#!/usr/bin/env python3
"""Rebuild tests/fixtures/sample-expected.json: the engine's result on the recorded sample, which
tests/test_recorded.py then holds it to. Rebuild only after a change that is meant to alter results,
and say why in the commit."""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.dont_write_bytecode = True

from tests.test_recorded import expected_view, replay_sample  # noqa: E402

if __name__ == "__main__":
    view = expected_view(*replay_sample())
    with open(os.path.join(REPO, "tests", "fixtures", "sample-expected.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(view, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(json.dumps(view["counts"], indent=1))
