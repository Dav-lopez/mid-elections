"""Provider JSON streaming must be bounded without inventing missing data."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import requests

from civicpulse_client import ElectionFeedClient
from civicpulse_core import FeedValidationError
from civicpulse_transport import read_bounded_json
from test_client import Response, Session, payload


class StreamResponse(Response):
    def __init__(self, chunks, **kwargs):
        super().__init__(**kwargs)
        self.chunks = chunks
        self.chunk_sizes = []

    def iter_content(self, chunk_size):
        self.chunk_sizes.append(chunk_size)
        yield from self.chunks


class BoundedTransportTests(unittest.TestCase):
    def client(self, session, clock=lambda: 0):
        return ElectionFeedClient(
            session=session, clock=clock,
            utcnow=lambda: datetime(2026, 11, 4, tzinfo=timezone.utc),
        )

    def test_streamed_response_is_validated_and_closed(self):
        response = StreamResponse([json.dumps(payload()).encode("utf-8")])
        session = Session(response)
        result = self.client(session).fetch("House")
        self.assertIsNone(result.error)
        self.assertEqual(result.feed.races["AZ-01"]["total"], 12)
        self.assertTrue(response.closed)
        self.assertTrue(response.chunk_sizes)
        self.assertTrue(session.calls[0][1]["stream"])

    def test_streamed_304_retry_closes_both_responses(self):
        first = Response(status=304)
        second = StreamResponse([json.dumps(payload()).encode("utf-8")])
        session = Session(first, second)
        result = self.client(session).fetch("House")
        self.assertIsNone(result.error)
        self.assertTrue(first.closed)
        self.assertTrue(second.closed)
        self.assertTrue(all(call[1]["stream"] for call in session.calls))

    def test_oversized_stream_keeps_last_validated_snapshot(self):
        first = Response(data=payload())
        oversized = StreamResponse([b"x" * 65])
        now = [0]
        client = self.client(Session(first, oversized), clock=lambda: now[0])
        good = client.fetch("House")
        now[0] = 60
        with patch("civicpulse_transport.MAX_RESPONSE_BYTES", 64):
            failed = client.fetch("House")
        self.assertIs(failed.feed, good.feed)
        self.assertIn("size limit", failed.error)
        self.assertIn("last-known", failed.status)
        self.assertTrue(oversized.closed)

    def test_elapsed_budget_detects_trickling_chunks(self):
        response = StreamResponse([b'{"api":', b"1}"])
        ticks = iter((0, 16))
        with self.assertRaises(requests.Timeout):
            read_bounded_json(response, 0, clock=lambda: next(ticks))

    def test_invalid_json_remains_validation_failure(self):
        response = StreamResponse([b'{"api":'])
        with self.assertRaises(ValueError):
            read_bounded_json(response, 0, clock=lambda: 0)


if __name__ == "__main__":
    unittest.main()
