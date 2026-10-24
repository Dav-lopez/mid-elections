"""Concurrent viewers should reuse one in-flight office polling batch."""
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from civicpulse_polling import fetch_offices


class BlockingClient:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.lock = threading.Lock()
        self.calls = []

    def fetch(self, office, *, force=False):
        with self.lock:
            self.calls.append((office, force))
            if len(self.calls) == 2:
                self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("fixture release timed out")
        return office


class PollingSingleFlightTests(unittest.TestCase):
    def test_simultaneous_viewers_share_one_batch(self):
        client = BlockingClient()
        with ThreadPoolExecutor(max_workers=24) as viewers:
            first = viewers.submit(fetch_offices, client)
            self.assertTrue(client.started.wait(5))
            barrier = threading.Barrier(21)
            def join():
                barrier.wait(timeout=5)
                return fetch_offices(client)
            others = [viewers.submit(join) for _ in range(20)]
            barrier.wait(timeout=5)
            try:
                # Allow competing viewer calls to reach the shared batch.
                time.sleep(0.1)
                with client.lock:
                    self.assertEqual(len(client.calls), 2)
            finally:
                client.release.set()
            expected = {"House": "House", "Senate": "Senate"}
            self.assertEqual(first.result(timeout=5), expected)
            for future in others:
                self.assertEqual(future.result(timeout=5), expected)


if __name__ == "__main__":
    unittest.main()
