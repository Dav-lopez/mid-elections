"""Coalesced concurrent office polling shared by Streamlit viewer sessions.

At most one pair of office jobs is submitted for concurrent viewers using the
same client. This bounds queued work during a burst, but viewers still wait for
the initial slow provider response; nonblocking background refresh is future work.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from weakref import WeakKeyDictionary

OFFICES = ("House", "Senate")
_POLL_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="civicpulse-poll")
_BATCH_LOCK = Lock()
_INFLIGHT = WeakKeyDictionary()


def fetch_offices(client, *, force=False):
    """Share one in-flight batch across concurrent callers of the same client.

    A forced refresh arriving while another batch is active shares that batch;
    the client's own rate-limit and retry policy remains authoritative.
    """
    with _BATCH_LOCK:
        futures = _INFLIGHT.get(client)
        if futures is None or all(future.done() for future in futures.values()):
            futures = {
                name: _POLL_POOL.submit(client.fetch, name, force=force)
                for name in OFFICES
            }
            _INFLIGHT[client] = futures
    return {name: futures[name].result() for name in OFFICES}
