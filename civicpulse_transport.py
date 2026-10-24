"""Bounded streaming JSON reads for an untrusted election-results provider.

The elapsed-time budget is checked after response headers and each received
chunk. Requests' 8-second socket read timeout still applies within a chunk;
this is a best-effort elapsed cap, not a hard wall-clock cancellation.
"""
import json
import time

import requests

from civicpulse_core import FeedValidationError

MAX_RESPONSE_BYTES = 8_000_000
MAX_REQUEST_SECONDS = 15


def read_bounded_json(response, started_at: float, clock=time.monotonic):
    """Read a streamed JSON response with an elapsed and decoded-body cap.

    The fallback is only for lightweight injected response doubles that expose
    json() but not iter_content(); actual requests.Response streams are bounded.
    """
    iterator = getattr(response, "iter_content", None)
    if not callable(iterator):
        return response.json()

    def check_deadline():
        if clock() - started_at > MAX_REQUEST_SECONDS:
            raise requests.Timeout("Provider response exceeded elapsed read budget")

    check_deadline()
    chunks = []
    size = 0
    for chunk in iterator(chunk_size=16_384):
        check_deadline()
        if not chunk:
            continue
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise FeedValidationError("Provider JSON response exceeds size limit")
        chunks.append(chunk)
    check_deadline()
    return json.loads(b"".join(chunks))
