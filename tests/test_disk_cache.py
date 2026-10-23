"""Disk recovery is verified, bounded and always visibly stale on restart."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from civicpulse_client import ElectionFeedClient
from civicpulse_disk_cache import DiskFeedCache, MAX_AGE
from tests.test_client import Response, Session, payload


class DiskCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.url = "https://example.org/elections"
        self.cache = DiskFeedCache(self.tmp.name, self.url)
        self.when = datetime(2026, 11, 4, 1, tzinfo=timezone.utc)

    def client(self, session, *, now=None):
        now = now or self.when
        return ElectionFeedClient(
            url=self.url, session=session, disk_cache=self.cache,
            utcnow=lambda: now, clock=lambda: 0,
        )

    def test_restart_reuses_validated_data_but_warns_on_failure(self):
        first = self.client(Session(Response(data=payload(), etag='"a"'))).fetch("House")
        self.assertIsNotNone(first.feed)
        restored = self.client(Session(requests.Timeout("offline"))).fetch("House")
        self.assertEqual(restored.feed.races["AZ-01"]["total"], 12)
        self.assertEqual(restored.last_success_at, self.when)
        self.assertIn("last-known", restored.status)
        self.assertIsNotNone(restored.error)

    def test_restart_304_is_validated_success(self):
        self.client(Session(Response(data=payload(), etag='"a"'))).fetch("House")
        session = Session(Response(status=304))
        next_time = self.when + timedelta(minutes=5)
        result = self.client(session, now=next_time).fetch("House")
        self.assertEqual(result.http_status, 304)
        self.assertIsNone(result.error)
        self.assertEqual(result.last_success_at, next_time)
        self.assertEqual(session.calls[0][1]["headers"]["If-None-Match"], '"a"')
        self.assertEqual(self.cache.load("House", next_time)[1], next_time)

    def test_expired_data_is_ignored(self):
        self.client(Session(Response(data=payload()))).fetch("House")
        self.assertIsNone(self.cache.load("House", self.when + MAX_AGE + timedelta(seconds=1)))

    def test_wrong_endpoint_is_rejected(self):
        self.client(Session(Response(data=payload()))).fetch("House")
        other = DiskFeedCache(self.tmp.name, "https://other.example/elections")
        self.assertIsNone(other.load("House", self.when))

    def test_corruption_and_invalid_schema_are_rejected(self):
        path = Path(self.tmp.name) / "2026-house.json"
        path.write_text("{broken", encoding="utf-8")
        self.assertIsNone(self.cache.load("House", self.when))
        self.client(Session(Response(data=payload()))).fetch("House")
        record = json.loads(path.read_text(encoding="utf-8"))
        record["payload"]["api"] = 999
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertIsNone(self.cache.load("House", self.when))

    def test_source_failure_does_not_replace_last_success(self):
        self.client(Session(Response(data=payload()))).fetch("House")
        self.client(Session(requests.Timeout("offline"))).fetch("House")
        self.assertEqual(self.cache.load("House", self.when)[1], self.when)


if __name__ == "__main__":
    unittest.main()
