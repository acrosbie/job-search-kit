#!/usr/bin/env python3
"""
job-search-kit engine. Standard library only; runs on Python 3.10 and later.

    python3 run.py <command> --folder "<the user's Job Search folder>" [options]

Claude runs this; the user never does. Commands are listed by `python3 run.py help`.
"""

import os
import sys

# The engine may be copied into the user's folder, where Cowork's workspace can't delete files.
# Don't leave __pycache__ folders behind that nobody can clear.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jobkit.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
