"""Concurrency regression tests for Streamlit office polling."""
import threading
import unittest

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


if __name__ == "__main__":
    unittest.main()
