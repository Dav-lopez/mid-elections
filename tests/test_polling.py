"""Concurrency regression tests for Streamlit office polling."""
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from civicpulse_polling import fetch_offices


class PollingTests(unittest.TestCase):
    def test_both_offices_run_in_parallel(self):
        house_started = threading.Event()
        senate_started = threading.Event()
        release = threading.Event()
        observed = []

        class Client:
            def fetch(self, office, *, force=False):
                observed.append((office, force))
                if office == "House":
                    house_started.set()
                    if not senate_started.wait(2):
                        raise AssertionError("Senate request did not start while House was running")
                else:
                    senate_started.set()
                    if not house_started.wait(2):
                        raise AssertionError("House request did not start while Senate was running")
                return office + "-ok"

        result = fetch_offices(Client(), force=True)
        self.assertEqual(result, {"House": "House-ok", "Senate": "Senate-ok"})
        self.assertCountEqual(observed, [("House", True), ("Senate", True)])

    def test_office_failure_is_not_silenced(self):
        class Client:
            def fetch(self, office, *, force=False):
                if office == "Senate":
                    raise RuntimeError("unexpected programming failure")
                return "house-ok"

        with self.assertRaisesRegex(RuntimeError, "unexpected programming failure"):
            fetch_offices(Client())

    def test_default_does_not_force_request(self):
        class Client:
            def fetch(self, office, *, force=False):
                self.forced.append(force)
                return office
            forced = []

        client = Client()
        self.assertEqual(list(fetch_offices(client)), ["House", "Senate"])
        self.assertEqual(client.forced, [False, False])


    def test_many_viewers_share_only_two_polling_workers(self):
        """Simulate 120 simultaneous viewer reruns without a thread explosion."""
        lock = threading.Lock()
        active = 0
        peak = 0
        worker_names = set()

        class Client:
            def fetch(self, office, *, force=False):
                nonlocal active, peak
                with lock:
                    active += 1
                    peak = max(peak, active)
                    worker_names.add(threading.current_thread().name)
                try:
                    time.sleep(0.003)
                    return office
                finally:
                    with lock:
                        active -= 1

        client = Client()
        with ThreadPoolExecutor(max_workers=40) as viewers:
            results = list(viewers.map(lambda _: fetch_offices(client), range(120)))

        self.assertTrue(all(result == {"House": "House", "Senate": "Senate"}
                            for result in results))
        self.assertLessEqual(peak, 2, "Polling must not create per-viewer workers")
        self.assertLessEqual(len(worker_names), 2)
        self.assertTrue(all(name.startswith("civicpulse-poll")
                            for name in worker_names))


if __name__ == "__main__":
    unittest.main()
