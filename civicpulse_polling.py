"""Concurrent office polling: one UI rerun waits for the slowest office, not both.

The underlying ElectionFeedClient guarantees at most one request per office
within a process; concurrent viewers receive cached/pending snapshots.
"""
from concurrent.futures import ThreadPoolExecutor

OFFICES = ("House", "Senate")


def fetch_offices(client, *, force=False):
    """Issue independent office fetches concurrently without sharing a session lock."""
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="civicpulse-poll") as pool:
        futures = {name: pool.submit(client.fetch, name, force=force) for name in OFFICES}
        return {name: futures[name].result() for name in OFFICES}
