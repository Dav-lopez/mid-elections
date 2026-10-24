"""Unit tests for conditional requests, backoff and last-known-good snapshots."""
import unittest
import threading
from unittest.mock import patch
from datetime import datetime, timezone

import requests

from civicpulse_client import ElectionFeedClient
from civicpulse_polling import fetch_offices


def payload(office="House", **changes):
    data = {
        "api": 1, "year": 2026, "office": office,
        "live": True, "stale": False, "counting": True, "final": False,
        "as_of": "2026-11-04T01:00:00+00:00", "source": "state",
        "races": {"AZ-01": {"leader": "D", "total": 12, "cands": []}},
    }
    data.update(changes)
    return data


class Response:
    def __init__(self, status=200, data=None, etag=None, headers=None):
        self.status_code = status
        self.data = data
        self.headers = dict(headers or {})
        self.closed = False
        if etag:
            self.headers["ETag"] = etag

    def close(self):
        self.closed = True

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self.status_code == 304:
            raise AssertionError("Must not parse body of HTTP 304")
        return self.data


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.t = 0.0
        self.when = datetime(2026, 11, 4, 1, 0, tzinfo=timezone.utc)

    def client(self, session):
        return ElectionFeedClient(
            session=session, clock=lambda: self.t, utcnow=lambda: self.when,
        )

    def test_responses_closed_on_success_and_http_failure(self):
        good = Response(data=payload())
        bad = Response(status=503)
        client = self.client(Session(good, bad))
        client.fetch("House")
        self.assertTrue(good.closed)
        self.t = 60
        client.fetch("House")
        self.assertTrue(bad.closed)

    def test_304_retry_closes_both_responses(self):
        invalid_304 = Response(status=304)
        fresh = Response(data=payload())
        result = self.client(Session(invalid_304, fresh)).fetch("House")
        self.assertIsNone(result.error)
        self.assertTrue(invalid_304.closed)
        self.assertTrue(fresh.closed)

    def test_etag_304_and_shared_ttl(self):
        session = Session(Response(data=payload(), etag='"v1"'), Response(status=304))
        client = self.client(session)
        first = client.fetch("House")
        self.assertEqual(first.feed.races["AZ-01"]["total"], 12)
        self.assertEqual(first.http_status, 200)
        self.t = 30
        self.assertIs(client.fetch("House"), first)
        self.assertEqual(len(session.calls), 1)
        self.t = 60
        second = client.fetch("House")
        self.assertEqual(second.http_status, 304)
        self.assertIs(second.feed, first.feed)
        self.assertEqual(second.error, None)
        self.assertEqual(session.calls[1][1]["headers"]["If-None-Match"], '"v1"')

    def test_last_good_data_kept_but_not_labeled_live_after_failure(self):
        session = Session(
            Response(data=payload(), etag='"v1"'),
            requests.Timeout("slow"),
            Response(data=payload(races={}), etag='"v2"'),
        )
        client = self.client(session)
        client.fetch("House")
        self.t = 60
        failed = client.fetch("House")
        self.assertEqual(failed.feed.races["AZ-01"]["total"], 12)
        self.assertIsNotNone(failed.error)
        self.assertIn("last-known", failed.status)
        self.assertEqual(failed.last_success_at, self.when)
        self.assertEqual(failed.next_due, 180)
        self.t = 100
        self.assertIs(client.fetch("House"), failed)
        self.t = 180
        recovered = client.fetch("House")
        self.assertEqual(recovered.feed.races, {})
        self.assertIsNone(recovered.error)
        self.assertEqual(recovered.failures, 0)

    def test_invalid_payload_does_not_replace_valid_snapshot(self):
        session = Session(Response(data=payload()), Response(data={"api": 2}))
        client = self.client(session)
        initial = client.fetch("House")
        self.t = 60
        later = client.fetch("House")
        self.assertEqual(later.feed, initial.feed)
        self.assertIn("FeedValidationError", later.error)

    def test_case_colliding_races_preserve_last_validated_snapshot(self):
        valid = payload(races={"AZ-01": {"total": 12}})
        ambiguous = payload(races={
            "az-01": {"total": 12},
            "AZ-01": {"total": 99},
        })
        session = Session(Response(data=valid), Response(data=ambiguous))
        client = self.client(session)
        first = client.fetch("House")
        self.t = 60
        second = client.fetch("House")
        self.assertEqual(second.feed, first.feed)
        self.assertEqual(second.feed.races["AZ-01"]["total"], 12)
        self.assertIn("Duplicate race identifier", second.error)
        self.assertEqual(second.failures, 1)
        self.assertIn("last-known", second.status)

    def test_no_snapshot_on_initial_failure(self):
        session = Session(Response(status=503))
        result = self.client(session).fetch("House")
        self.assertIsNone(result.feed)
        self.assertEqual(result.failures, 1)
        self.assertEqual(result.next_due, 120)
        self.assertIn("unavailable", result.status)

    def test_304_without_previous_body_retries_unconditionally(self):
        session = Session(Response(status=304), Response(data=payload(), etag='"new"'))
        result = self.client(session).fetch("House")
        self.assertEqual(result.http_status, 200)
        self.assertEqual(result.etag, '"new"')
        self.assertNotIn("If-None-Match", session.calls[1][1]["headers"])

    def test_backoff_caps_at_ten_minutes(self):
        session = Session(*[requests.Timeout("offline") for _ in range(5)])
        client = self.client(session)
        for expected in (120, 240, 480, 600, 600):
            snapshot = client.fetch("House")
            self.assertEqual(snapshot.next_due - self.t, expected)
            self.t = snapshot.next_due
        self.assertEqual(len(session.calls), 5)

    def test_429_retry_after_defers_requests_including_manual_refresh(self):
        session = Session(
            Response(status=429, headers={"Retry-After": "300"}),
            Response(data=payload()),
        )
        client = self.client(session)
        throttled = client.fetch("House")
        self.assertEqual(throttled.http_status, 429)
        self.assertEqual(throttled.next_due, 300)
        self.t = 299
        self.assertIs(client.fetch("House", force=True), throttled)
        self.assertEqual(len(session.calls), 1)
        self.t = 300
        recovered = client.fetch("House")
        self.assertIsNone(recovered.error)
        self.assertEqual(len(session.calls), 2)

    def test_retry_after_http_date_and_ten_minute_cap(self):
        session = Session(
            Response(status=503, headers={
                "Retry-After": "Wed, 04 Nov 2026 01:05:00 GMT"
            }),
            Response(status=429, headers={"Retry-After": "999999999999999"}),
        )
        client = self.client(session)
        first = client.fetch("House")
        self.assertEqual(first.next_due, 300)
        self.t = 300
        second = client.fetch("House")
        self.assertEqual(second.next_due - self.t, 600)

    def test_invalid_retry_after_uses_normal_backoff(self):
        session = Session(Response(status=429, headers={"Retry-After": "invalid"}))
        result = self.client(session).fetch("House")
        self.assertEqual(result.next_due, 120)

    def test_invalid_office_rejected_without_request(self):
        session = Session()
        with self.assertRaises(ValueError):
            self.client(session).fetch("Governor")
        self.assertEqual(session.calls, [])

    def test_default_parallel_office_requests_use_distinct_http_sessions(self):
        """A shared requests.Session is not safe for simultaneous office fetches."""
        house_session = Session(Response(data=payload("House")))
        senate_session = Session(Response(data=payload("Senate")))
        with patch("civicpulse_client.requests.Session",
                   side_effect=[house_session, senate_session]) as make_session:
            client = ElectionFeedClient(
                clock=lambda: self.t, utcnow=lambda: self.when)
        results = fetch_offices(client)
        self.assertEqual(make_session.call_count, 2)
        self.assertIsNot(client._sessions["House"], client._sessions["Senate"])
        self.assertEqual(results["House"].feed.office, "House")
        self.assertEqual(results["Senate"].feed.office, "Senate")
        self.assertEqual(house_session.calls[0][1]["params"]["office"], "House")
        self.assertEqual(senate_session.calls[0][1]["params"]["office"], "Senate")

    def test_independent_office_caches(self):
        session = Session(Response(data=payload()), Response(data=payload(office="Senate")))
        client = self.client(session)
        self.assertEqual(client.fetch("House").feed.office, "House")
        self.assertEqual(client.fetch("Senate").feed.office, "Senate")
        self.assertEqual(len(session.calls), 2)


    def test_manual_force_cannot_bypass_backoff(self):
        session = Session(Response(data=payload()), requests.Timeout("offline"))
        client = self.client(session)
        client.fetch("House")
        self.t = 60
        failed = client.fetch("House")
        for _ in range(20):
            self.assertIs(client.fetch("House", force=True), failed)
        self.assertEqual(len(session.calls), 2)

    def test_manual_force_obeys_minimum_gap(self):
        session = Session(Response(data=payload()), Response(data=payload()))
        client = self.client(session)
        first = client.fetch("House")
        self.t = 30
        for _ in range(20):
            self.assertIs(client.fetch("House", force=True), first)
        self.assertEqual(len(session.calls), 1)
        self.t = 60
        client.fetch("House", force=True)
        self.assertEqual(len(session.calls), 2)

    def test_other_office_does_not_wait_for_blocked_request(self):
        entered = threading.Event()
        release = threading.Event()

        class SlowSession:
            def get(self, url, **kwargs):
                office = kwargs["params"]["office"]
                if office == "House":
                    entered.set()
                    if not release.wait(timeout=4):
                        raise requests.Timeout("timed out in test")
                return Response(data=payload(office=office))

        client = self.client(SlowSession())
        thread = threading.Thread(target=lambda: client.fetch("House"))
        thread.start()
        try:
            self.assertTrue(entered.wait(timeout=2))
            done = threading.Event()

            def query_senate():
                client.fetch("Senate")
                done.set()

            senate = threading.Thread(target=query_senate)
            senate.start()
            self.assertTrue(done.wait(timeout=1), "Senate must not wait for House")
            senate.join(timeout=2)
            pending = client.fetch("House")
            self.assertIn("in progress", pending.error.lower())
        finally:
            release.set()
            thread.join(timeout=2)

if __name__ == "__main__":
    unittest.main()
