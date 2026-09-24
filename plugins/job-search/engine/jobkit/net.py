"""Fetching.

Every job-board request goes through fetch(), so a scan can run live, record what the boards
answered into a cassette (a folder of one gzip file per request), or replay a cassette with no
network at all. Replay is how the engine is tested against real board data, and how it is
compared with the reference scanner it was ported from.
"""

import gzip
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request

from . import __version__

UA = f"Mozilla/5.0 (compatible; job-search-kit/{__version__}; +https://github.com/acrosbie/job-search-kit)"
TIMEOUT = 60


def request_key(url, data=None):
    """One request's identity in a cassette: method, URL and JSON body. Headers don't count."""
    body = json.dumps(data, sort_keys=True) if data is not None else ""
    method = "POST" if data is not None else "GET"
    return hashlib.sha1(f"{method} {url}\n{body}".encode("utf-8")).hexdigest()


class Live:
    """The real network. Same request shape as the reference scanner."""

    def __init__(self, user_agent=UA, timeout=TIMEOUT):
        self.user_agent = user_agent
        self.timeout = timeout

    def request(self, url, data=None, headers=None):
        hdrs = {"User-Agent": self.user_agent, "Accept": "application/json, text/html;q=0.9, */*;q=0.8"}
        if headers:
            hdrs.update(headers)
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=hdrs)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def pause(self, seconds):
        time.sleep(seconds)


class Cassette:
    """A folder of recorded answers, one gzip JSON file per request."""

    def __init__(self, folder):
        self.folder = folder

    def path(self, key):
        return os.path.join(self.folder, key + ".json.gz")

    def write(self, url, data, text=None, error=None):
        os.makedirs(self.folder, exist_ok=True)
        entry = {"method": "POST" if data is not None else "GET", "url": url, "body": data, "text": text, "error": error}
        with gzip.open(self.path(request_key(url, data)), "wt", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)

    def read(self, url, data):
        p = self.path(request_key(url, data))
        if not os.path.exists(p):
            return None
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)


def error_record(exc):
    """What went wrong, in a form a replay can raise again."""
    if isinstance(exc, urllib.error.HTTPError):
        return {"type": "HTTPError", "code": exc.code, "message": str(exc.reason)}
    return {"type": type(exc).__name__, "message": str(exc)}


def raise_recorded(url, err):
    if err.get("type") == "HTTPError":
        raise urllib.error.HTTPError(url, err.get("code", 0), err.get("message", ""), None, None)
    raise urllib.error.URLError(f"{err.get('type')}: {err.get('message')}")


class Record:
    """Fetches live and writes every answer, and every failure, to a cassette."""

    def __init__(self, folder, inner=None):
        self.cassette = Cassette(folder)
        self.inner = inner or Live()

    def request(self, url, data=None, headers=None):
        try:
            text = self.inner.request(url, data, headers)
        except Exception as e:
            self.cassette.write(url, data, error=error_record(e))
            raise
        self.cassette.write(url, data, text=text)
        return text

    def pause(self, seconds):
        self.inner.pause(seconds)


class ReplayMiss(Exception):
    """The replay was asked for something the recording doesn't have."""


class Replay:
    """Serves a cassette and never touches the network. Every miss is kept in `misses`, so a
    test can fail on a request the recording didn't make, instead of passing on a skipped board."""

    def __init__(self, folder):
        self.cassette = Cassette(folder)
        self.misses = []
        self._lock = threading.Lock()

    def request(self, url, data=None, headers=None):
        entry = self.cassette.read(url, data)
        if entry is None:
            with self._lock:
                self.misses.append(url)
            raise ReplayMiss(f"not in the recording: {url}")
        if entry.get("error"):
            raise_recorded(url, entry["error"])
        return entry["text"]

    def pause(self, seconds):
        pass


_transport = Live()


def use(transport):
    """Switch every fetch to `transport`; returns the previous one."""
    global _transport
    previous, _transport = _transport, transport
    return previous


def fetch(url, data=None, headers=None):
    return _transport.request(url, data, headers)


def fetch_json(url, data=None, headers=None):
    return json.loads(fetch(url, data=data, headers=headers))


def pause(seconds):
    _transport.pause(seconds)
