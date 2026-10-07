"""What the engine refuses, and what it can't find. The command line turns these into exit codes 3
and 1 and prints the message, which is written so Claude can pass it on in plain words."""


class Refused(ValueError):
    """Refused on purpose: a change that would make the records or settings wrong. The message says why."""


class NotFound(LookupError):
    """A posting or application that isn't in the user's records."""


class BadFile(ValueError):
    """A file Claude wrote that isn't in the shape the engine reads, such as a resume source. The
    message names the line."""
