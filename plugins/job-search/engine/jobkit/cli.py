"""Command line for the engine. Claude runs these; see run.py."""

import sys

from . import __version__

HELP = f"""job-search-kit engine {__version__}

    python3 run.py version
"""


def main(argv):
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(HELP)
        return 0
    if argv[0] == "version":
        print(f"job-search-kit engine {__version__}, Python {sys.version.split()[0]}")
        return 0
    print(f"unknown command: {argv[0]}\n\n{HELP}", file=sys.stderr)
    return 2
