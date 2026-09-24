"""Tests for the job-search-kit engine. Standard library unittest; run from the repo root with
`python -m unittest discover -s tests -t .` on Python 3.10 and on a current Python."""

import os
import sys

sys.dont_write_bytecode = True
ENGINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", "job-search", "engine")
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)
