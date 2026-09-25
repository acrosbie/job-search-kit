"""Job-board readers, one per hiring system.

Each reader takes a company entry from companies.toml and a Context, and returns a list of
records (see common.make_record). The `ats` value in companies.toml picks the reader;
"manual" entries have none and are checked by hand.
"""

from . import ashby, atlassian, careers_api, greenhouse, himalayas, lever, rippling, smartrecruiters, talentbrew, workday
from .common import Context, make_record, watched_names

READERS = {
    "greenhouse": greenhouse.read,
    "ashby": ashby.read,
    "lever": lever.read,
    "smartrecruiters": smartrecruiters.read,
    "workday": workday.read,
    "rippling": rippling.read,
    "careers_api": careers_api.read,
    "atlassian": atlassian.read,
    "talentbrew": talentbrew.read,
    "himalayas": himalayas.read,
}

__all__ = ["READERS", "Context", "make_record", "watched_names"]
