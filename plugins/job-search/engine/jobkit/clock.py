"""Dates and times.

Dates a person reads (first seen, triaged, gone) are the user's local date. Timestamps are ISO
with an offset. Cowork's workspace on the user's computer keeps its clock in UTC, so the local
date comes from the timezone in settings.toml, not from the machine.
"""

import datetime as dt

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


def _zone(name):
    if not name or ZoneInfo is None:
        return None
    try:
        return ZoneInfo(name)
    except Exception:  # unknown name, or no time zone data on this machine
        return None


class Clock:
    """`fixed` pins the time (an aware datetime), for tests and for replaying recorded boards."""

    def __init__(self, timezone="", fixed=None):
        self.tz = _zone(timezone)
        self.fixed = fixed

    def now(self):
        n = self.fixed or dt.datetime.now(dt.timezone.utc)
        return n.astimezone(self.tz) if self.tz else n.astimezone()

    def today(self):
        return self.now().date().isoformat()

    def stamp(self):
        return self.now().isoformat(timespec="seconds")
