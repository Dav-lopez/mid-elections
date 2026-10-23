"""Unit tests for conditional requests, backoff and last-known-good snapshots."""
import unittest
from datetime import datetime, timezone

import requests

from civicpulse_client import ElectionFeedClient


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
    def __init__(self, status=200, data=None, etag=None):
        self.status_code = status
        self.data = data
        self.headers = {"ETag": etag} if etag else {}

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

    def test_invalid_office_rejected_without_request(self):
        session = Session()
        with self.assertRaises(ValueError):
            self.client(session).fetch("Governor")
        self.assertEqual(session.calls, [])

    def test_independent_office_caches(self):
        session = Session(Response(data=payload()), Response(data=payload(office="Senate")))
        client = self.client(session)
        self.assertEqual(client.fetch("House").feed.office, "House")
        self.assertEqual(client.fetch("Senate").feed.office, "Senate")
        self.assertEqual(len(session.calls), 2)


if __name__ == "__main__":
    unittest.main()
