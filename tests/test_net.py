import os
import shutil
import tempfile
import unittest
import urllib.error

from jobkit import net


class FakeBoards:
    """Stands in for the internet."""

    def __init__(self):
        self.calls = 0

    def request(self, url, data=None, headers=None):
        self.calls += 1
        if "missing" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return '{"url": "%s", "posted": %s}' % (url, "true" if data else "false")

    def pause(self, seconds):
        pass


class RecordReplayTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(net.use, net.use(net.Live()))

    def test_record_then_replay(self):
        fake = FakeBoards()
        net.use(net.Record(self.dir, inner=fake))
        self.assertEqual(net.fetch_json("https://example.test/a")["url"], "https://example.test/a")
        self.assertTrue(net.fetch_json("https://example.test/b", data={"offset": 0})["posted"])
        with self.assertRaises(urllib.error.HTTPError):
            net.fetch("https://example.test/missing")
        self.assertEqual(len(os.listdir(self.dir)), 3)

        replay = net.Replay(self.dir)
        net.use(replay)
        self.assertEqual(net.fetch_json("https://example.test/a")["url"], "https://example.test/a")
        self.assertTrue(net.fetch_json("https://example.test/b", data={"offset": 0})["posted"])
        with self.assertRaises(urllib.error.HTTPError) as err:
            net.fetch("https://example.test/missing")
        self.assertEqual(err.exception.code, 404)
        self.assertEqual(replay.misses, [])
        self.assertEqual(fake.calls, 3)  # the replay never reached the fake internet

    def test_replay_miss_is_recorded(self):
        replay = net.Replay(self.dir)
        net.use(replay)
        with self.assertRaises(net.ReplayMiss):
            net.fetch("https://example.test/never-recorded")
        self.assertEqual(replay.misses, ["https://example.test/never-recorded"])

    def test_body_is_part_of_the_key(self):
        self.assertNotEqual(net.request_key("https://x.test/jobs", {"offset": 0}),
                            net.request_key("https://x.test/jobs", {"offset": 20}))
        self.assertEqual(net.request_key("https://x.test/jobs", {"a": 1, "b": 2}),
                         net.request_key("https://x.test/jobs", {"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
