"""Warm viewer reads must not block behind provider refreshes."""
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from civicpulse_polling import fetch_offices


class ControlledClient:
    def __init__(self, warm):
        self._snapshots = dict(warm)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.lock = threading.Lock()
        self.calls = []

    def fetch(self, office, *, force=False):
        with self.lock:
            self.calls.append(office)
            if len(self.calls) == 2:
                self.entered.set()
        if not self.release.wait(5):
            raise TimeoutError("fixture was not released")
        value = office + "-new"
        self._snapshots[office] = value
        return value


class WarmCacheTests(unittest.TestCase):
    def test_warm_viewers_return_without_waiting_for_refresh(self):
        client = ControlledClient({"House": "House-old", "Senate": "Senate-old"})
        expected = {"House": "House-old", "Senate": "Senate-old"}
        try:
            self.assertEqual(fetch_offices(client), expected)
            self.assertTrue(client.entered.wait(3))
            start = time.monotonic()
            with ThreadPoolExecutor(max_workers=50) as pool:
                results = list(pool.map(lambda _: fetch_offices(client), range(50)))
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, 1.0, "warm viewers waited for upstream")
            self.assertTrue(all(result == expected for result in results))
            with client.lock:
                self.assertEqual(len(client.calls), 2)
        finally:
            client.release.set()

    def test_cold_start_waits_for_first_snapshot(self):
        client = ControlledClient({})
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                waiting = pool.submit(fetch_offices, client)
                self.assertTrue(client.entered.wait(3))
                self.assertFalse(waiting.done())
                client.release.set()
                self.assertEqual(waiting.result(timeout=3), {
                    "House": "House-new", "Senate": "Senate-new"
                })
        finally:
            client.release.set()


if __name__ == "__main__":
    unittest.main()
