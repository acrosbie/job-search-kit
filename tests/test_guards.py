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


class VersionTest(unittest.TestCase):
    def test_engine_version_is_the_plugin_version(self):
        import json
        with open(os.path.join(REPO, "plugins", "job-search", ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            plugin = json.load(f)["version"]
        engine = re.search(r'__version__ = "([^"]+)"', read(os.path.join(ENGINE, "jobkit", "__init__.py"))).group(1)
        self.assertEqual(engine, plugin)

    def test_each_version_says_whats_new(self):
        import sys
        sys.path.insert(0, ENGINE)
        from jobkit import __version__, news
        self.assertIn(__version__, news.NEWS, "add a line for this version to engine/jobkit/news.py")

    def test_a_push_that_changes_the_plugin_moves_its_version(self):
        # 2026-10-12: eight commits sat under 0.11.1 and never reached the user (tools/check_release.py).
        import sys
        sys.path.insert(0, os.path.join(REPO, "tools"))
        from check_release import problems
        plugin = ["plugins/job-search/engine/page/jobs-page.html", "tests/test_page_browser.py"]
        self.assertEqual(len(problems("0.11.1", "0.11.1", plugin)), 1)
        self.assertEqual(problems("0.11.1", "0.12.0", plugin), [])
        self.assertIn("goes back", problems("0.12.0", "0.11.1", plugin)[0])
        self.assertEqual(problems("0.11.1", "0.11.1", ["docs/decisions/README.md", "tests/test_start.py"]), [])
        self.assertEqual(problems("0.9.0", "0.10.0", plugin), [])  # by number, not as text

    def test_the_recorded_fingerprint_is_the_files(self):
        # Skills refresh a user's copy of the engine when its fingerprint differs from the plugin's, so
        # any change to an engine file must change the recorded one. Line endings don't count.
        import sys
        sys.path.insert(0, ENGINE)
        from jobkit import fingerprint
        recorded = re.search(r'__fingerprint__ = "([0-9a-f]*)"', read(os.path.join(ENGINE, "jobkit", "__init__.py"))).group(1)
        self.assertEqual(recorded, fingerprint.compute(), "an engine file changed: run python tools/update_fingerprint.py")

    def test_line_endings_dont_change_the_fingerprint(self):
        import shutil
        import sys
        import tempfile
        sys.path.insert(0, ENGINE)
        from jobkit import fingerprint
        copy = os.path.join(tempfile.mkdtemp(), "engine")
        self.addCleanup(shutil.rmtree, os.path.dirname(copy))
        shutil.copytree(ENGINE, copy, ignore=shutil.ignore_patterns("__pycache__"))
        path = os.path.join(copy, "jobkit", "_vendor", "tomli", "_re.py")
        with open(path, "rb") as f:
            body = f.read()
        with open(path, "wb") as f:
            f.write(body.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(fingerprint.compute(copy), fingerprint.compute())
        with open(path, "ab") as f:
            f.write(b"# changed" + bytes([13, 10]))
        self.assertNotEqual(fingerprint.compute(copy), fingerprint.compute())


class OnRequestTest(unittest.TestCase):
    def test_only_the_resume_skill_makes_a_resume(self):
        # Resume help is on request only: nothing is made because a job was marked worth applying.
        skills = os.path.join(REPO, "plugins", "job-search", "skills")
        for name in sorted(os.listdir(skills)):
            text = read(os.path.join(skills, name, "SKILL.md"))
            if name == "resume":
                self.assertIn("resume render", text)
            else:
                self.assertNotIn("resume render", text, name)
                self.assertNotIn("resume check", text, name)


class SkillFrontmatterTest(unittest.TestCase):
    def test_every_description_reaches_cowork_whole(self):
        # The frontmatter is YAML: in an unquoted value " #" starts a comment and ": " starts a
        # mapping, so either one cuts the description Cowork matches requests against.
        skills = os.path.join(REPO, "plugins", "job-search", "skills")
        for name in sorted(os.listdir(skills)):
            head = read(os.path.join(skills, name, "SKILL.md")).split("\n---", 1)[0]
            fields = dict(line.split(": ", 1) for line in head.splitlines()[1:] if ": " in line)
            self.assertEqual(fields.get("name"), name)
            value = fields.get("description", "")
            self.assertTrue(value, name)
            if value[0] not in "'\"":
                self.assertNotIn(" #", value, name)
                self.assertNotIn(": ", value, name)


class TriggerTest(unittest.TestCase):
    def test_each_phrase_has_one_skill(self):
        # A phrase listed by two skills makes it a coin toss which one answers ("I have an interview
        # with ..." was in both track and interview).
        skills = os.path.join(REPO, "plugins", "job-search", "skills")
        owner = {}
        for name in sorted(os.listdir(skills)):
            head = read(os.path.join(skills, name, "SKILL.md")).split("\n---", 1)[0]
            desc = next(line for line in head.splitlines() if line.startswith("description: "))
            self.assertLessEqual(len(desc) - len("description: "), 330, f"{name}: keep the description short")
            for phrase in re.findall(r'"([^"]+)"', desc):
                key = re.sub(r"[^a-z' ]+", "", phrase.lower()).strip()
                self.assertNotIn(key, owner, f'"{phrase}" is in both {owner.get(key)} and {name}')
                owner[key] = name


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
