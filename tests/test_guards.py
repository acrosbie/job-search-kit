"""Checks on the code itself, not its behaviour: the engine never deletes a file, runs on Python
3.10, and nothing personal is committed."""

import ast
import hashlib
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(REPO, "plugins", "job-search", "engine")
SKIP_DIRS = {".git", "__pycache__", "_vendor", "recorded"}


def files(top, suffixes):
    for root, dirs, names in os.walk(top):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if n.endswith(suffixes):
                yield os.path.join(root, n)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class EngineGuardTest(unittest.TestCase):
    def test_never_deletes(self):
        # Cowork's workspace on the user's computer can't delete files, and renaming over a file may
        # count as deleting. The engine writes in place instead.
        banned = re.compile(r"\bos\.(remove|unlink|rmdir|removedirs|replace|rename|renames)\(|\.unlink\(|\.rmdir\(|shutil\.(rmtree|move)\(")
        for path in files(ENGINE, (".py",)):
            for n, line in enumerate(read(path).splitlines(), 1):
                self.assertIsNone(banned.search(line), f"{os.path.relpath(path, REPO)}:{n}: {line.strip()}")

    def test_runs_on_python_3_10(self):
        newer = re.compile(r"\bdt\.UTC\b|\bdatetime\.UTC\b|\bexcept\s*\*|\bExceptionGroup\b|\bStrEnum\b|typing\.Self|\bimport tomllib\b|\bfrom tomllib\b")
        for path in files(ENGINE, (".py",)):
            text = read(path)
            ast.parse(text, filename=path, feature_version=(3, 10))
            for n, line in enumerate(text.splitlines(), 1):
                if path.endswith(os.path.join("jobkit", "toml.py")) and "tomllib" in line:
                    continue  # the one place tomllib is tried, with the vendored fallback
                self.assertIsNone(newer.search(line), f"{os.path.relpath(path, REPO)}:{n}: {line.strip()}")


class PrivacyTest(unittest.TestCase):
    # The reference system's own file names may appear only where the reference format is the subject:
    # the tools that read it, the tests of those tools, this file, and the docs that explain them.
    REFERENCE_NAMES = re.compile(r"verified-facts|triage-log|seen\.json|pipeline\.md|career[\\/]")
    ALLOWED = ("tools", os.path.join("tests", "test_import.py"), os.path.join("tests", "test_guards.py"), "docs")

    # Fingerprints of the reference system's owner's names (first, last, and two account names), so
    # this file can check for them without containing them.
    NAMES = {"79069711144d44b4", "9de330b1935204c7", "c7d2522bf4ebe500", "5d573d7f872003bf"}

    def test_no_names(self):
        for path in files(REPO, (".py", ".md", ".toml", ".json", ".txt", ".html")):
            for n, line in enumerate(read(path).splitlines(), 1):
                line = line.replace("acrosbie/job-search-kit", "")  # the repo's own address
                for word in re.findall(r"[a-z]+", line.lower()):
                    self.assertNotIn(hashlib.sha1(word.encode()).hexdigest()[:16], self.NAMES,
                                     f"{os.path.relpath(path, REPO)}:{n}")

    def test_no_reference_files_in_the_kit(self):
        for path in files(REPO, (".py", ".md", ".toml", ".json")):
            rel = os.path.relpath(path, REPO)
            if rel.startswith(self.ALLOWED):
                continue
            for n, line in enumerate(read(path).splitlines(), 1):
                self.assertIsNone(self.REFERENCE_NAMES.search(line), f"{rel}:{n}: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
