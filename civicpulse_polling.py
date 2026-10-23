"""Bounded concurrent office polling shared by all Streamlit viewer sessions.

A process-wide pool prevents creating two additional threads for every viewer
rerun. ElectionFeedClient remains responsible for per-office single-flight,
ETag caching, refresh throttling, and failure backoff.
"""
from concurrent.futures import ThreadPoolExecutor

OFFICES = ("House", "Senate")

# Exactly two worker threads per app process, not two per viewer session.
# Python's ThreadPoolExecutor is shutdown by the interpreter at process exit.
_POLL_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="civicpulse-poll")


def fetch_offices(client, *, force=False):
    """Poll both offices concurrently through the process-shared bounded pool.

    Viewers can still wait for a slow first request. A future background
    snapshot API can eliminate that latency without multiplying worker threads.
    """
    futures = {
        name: _POLL_POOL.submit(client.fetch, name, force=force)
        for name in OFFICES
    }
    return {name: futures[name].result() for name in OFFICES}
