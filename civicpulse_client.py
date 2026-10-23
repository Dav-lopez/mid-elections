"""Process-local, conditional-GET client for the Open America election results feed.

The cache is shared between Streamlit sessions, not persisted to disk. Every snapshot
distinguishes provider timestamps from HTTP check times and records failures even
when the last validated result is still displayed.
"""
from __future__ import annotations

import threading
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import requests

from civicpulse_core import Feed, FeedValidationError, parse_feed, refresh_seconds
from civicpulse_disk_cache import DiskFeedCache


@dataclass(frozen=True)
class FeedSnapshot:
    feed: Feed | None
    error: str | None
    checked_at: datetime
    last_success_at: datetime | None
    etag: str | None
    next_due: float
    failures: int
    http_status: int | None

    @property
    def status(self) -> str:
        if self.error:
            return ("Source request failed — displaying last-known results, not verified fresh"
                    if self.feed else "Source unavailable — no validated results")
        return self.feed.status if self.feed else "Source unavailable"


class ElectionFeedClient:
    """Shared per-office cache with ETag support, adaptive polling and error fallback."""

    def __init__(
        self,
        url: str = "https://openamerica.io/elections/results.json",
        session: requests.Session | None = None,
        clock: Callable[[], float] | None = None,
        utcnow: Callable[[], datetime] | None = None,
        disk_cache: DiskFeedCache | None = None,
    ):
        self.url = url
        self.session = session if session is not None else requests.Session()
        self.clock = clock if clock is not None else time.monotonic
        self.utcnow = utcnow if utcnow is not None else lambda: datetime.now(timezone.utc)
        self._locks = {name: threading.Lock() for name in ('House', 'Senate')}
        self._snapshots: dict[str, FeedSnapshot] = {}
        self._last_attempt_clock: dict[str, float] = {}
        self._minimum_force_gap = 60
        self.disk_cache = disk_cache if disk_cache is not None else DiskFeedCache(
            os.getenv('CIVICPULSE_CACHE_DIR', '.civicpulse-cache'), url)
        self._restored: set[str] = set()

    def fetch(self, office: str, *, force: bool = False) -> FeedSnapshot:
        if office not in ("House", "Senate"):
            raise ValueError("Unsupported office")
        lock = self._locks[office]
        if not lock.acquire(blocking=False):
            cached = self._snapshots.get(office)
            if cached is not None:
                return cached
            return FeedSnapshot(None, "Request in progress; no validated results yet",
                                self.utcnow(), None, None, self.clock(), 0, None)
        try:
            now = self.clock()
            previous = self._snapshots.get(office)
            if previous is None and office not in self._restored:
                self._restored.add(office)
                restored = self.disk_cache.load(office, self.utcnow())
                if restored is not None:
                    saved_feed, saved_at, saved_etag = restored
                    previous = FeedSnapshot(
                        feed=saved_feed,
                        error="Disk recovery: results not yet checked after restart",
                        checked_at=self.utcnow(),
                        last_success_at=saved_at,
                        etag=saved_etag,
                        next_due=now,
                        failures=0,
                        http_status=None,
                    )
                    self._snapshots[office] = previous
            if previous is not None:
                if previous.error and now < previous.next_due:
                    return previous
                if now < previous.next_due and (not force or
                    now - self._last_attempt_clock.get(office, now) < self._minimum_force_gap):
                    return previous
            checked_at = self.utcnow()
            self._last_attempt_clock[office] = now
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "User-Agent": "CivicPulse/4.0 (independent election dashboard)",
            }
            if previous is not None and previous.feed is not None and previous.etag:
                headers["If-None-Match"] = previous.etag
            status = None
            try:
                response = self.session.get(
                    self.url, params={"year": 2026, "office": office},
                    timeout=(5, 8), headers=headers,
                )
                status = response.status_code
                if status == 304 and (previous is None or previous.feed is None):
                    # Defensive recovery: a 304 is unusable without a cached body.
                    headers.pop("If-None-Match", None)
                    response = self.session.get(
                        self.url, params={"year": 2026, "office": office},
                        timeout=(5, 8), headers=headers,
                    )
                    status = response.status_code
                if status == 304:
                    feed = previous.feed
                    etag = response.headers.get("ETag") or previous.etag
                else:
                    response.raise_for_status()
                    feed = parse_feed(response.json(), office)
                    etag = response.headers.get("ETag")
                    try:
                        self.disk_cache.save(feed, checked_at, etag)
                    except OSError:
                        # No writable disk on some hosted systems; keep in-memory data.
                        pass
                if feed is None:
                    raise ValueError("No validated body available for HTTP 304")
                snapshot = FeedSnapshot(
                    feed=feed, error=None, checked_at=checked_at,
                    last_success_at=checked_at, etag=etag,
                    next_due=now + refresh_seconds([feed]), failures=0,
                    http_status=status,
                )
            except (requests.RequestException, FeedValidationError, ValueError) as exc:
                failures = (previous.failures if previous else 0) + 1
                snapshot = FeedSnapshot(
                    feed=previous.feed if previous else None,
                    error=f"{type(exc).__name__}: {exc}",
                    checked_at=checked_at,
                    last_success_at=previous.last_success_at if previous else None,
                    etag=previous.etag if previous else None,
                    next_due=now + refresh_seconds([], failures=failures),
                    failures=failures, http_status=status,
                )
            self._snapshots[office] = snapshot
            return snapshot
        finally:
            lock.release()
