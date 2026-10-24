"""Coalesced office polling with nonblocking warm-cache viewer reads.

A viewer with both office snapshots never waits for a slow upstream refresh.
Cold-start viewers still wait for the initial attempt so the UI can distinguish
unavailable data from valid provider results. All feed safety rules remain in
ElectionFeedClient.fetch.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from weakref import WeakKeyDictionary

OFFICES = ("House", "Senate")
_POLL_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="civicpulse-poll")
_BATCH_LOCK = Lock()
_INFLIGHT = WeakKeyDictionary()


def fetch_offices(client, *, force=False):
    """Share in-flight work, returning cached snapshots without waiting.

    Schedule a new batch whenever the previous batch has completed. The
    client's next_due/backoff checks make premature scheduled calls cheap.
    A partially warmed cache waits only for offices with no snapshot yet.
    Explicit user refreshes wait for the scheduled batch to complete so the
    button does not immediately redisplay the previous snapshot. The client
    still enforces force-rate limits and provider backoff.
    """
    with _BATCH_LOCK:
        futures = _INFLIGHT.get(client)
        if futures is None or all(future.done() for future in futures.values()):
            futures = {
                name: _POLL_POOL.submit(client.fetch, name, force=force)
                for name in OFFICES
            }
            _INFLIGHT[client] = futures
        # Some test doubles expose only fetch(); they have no persistent cache.
        snapshots = getattr(client, "_snapshots", {})
        cached = {name: snapshots.get(name) for name in OFFICES}
    return {
        name: futures[name].result() if force or cached[name] is None else cached[name]
        for name in OFFICES
    }
