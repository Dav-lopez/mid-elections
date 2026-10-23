"""Best-effort disk recovery for previously validated election feed snapshots.

This is not a shared/distributed cache. Files are server-local, verified against
the feed contract, expire after 72 hours, and never imply that results are fresh.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from civicpulse_core import Feed, FeedValidationError, parse_feed

MAX_AGE = timedelta(hours=72)


class DiskFeedCache:
    def __init__(self, directory: str | Path, source_url: str):
        self.directory = Path(directory)
        self.source_url = source_url

    def _path(self, office: str) -> Path:
        if office not in ("House", "Senate"):
            raise ValueError("Unsupported office")
        return self.directory / f"2026-{office.lower()}.json"

    def save(self, feed: Feed, checked_at: datetime, etag: str | None) -> None:
        """Atomic best-effort write; caller handles filesystem failures."""
        if checked_at.tzinfo is None:
            raise ValueError("check timestamp requires a timezone")
        document = {
            "version": 1, "url": self.source_url,
            "last_success_at": checked_at.astimezone(timezone.utc).isoformat(),
            "etag": etag,
            "payload": {
                "api": 1, "year": feed.year, "office": feed.office,
                "live": feed.live, "stale": feed.stale, "counting": feed.counting,
                "final": feed.final, "as_of": feed.as_of, "source": feed.source,
                "races": feed.races,
            },
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.directory, prefix=".civicpulse-",
                suffix=".tmp", delete=False
            ) as temp:
                temp_path = Path(temp.name)
                json.dump(document, temp, separators=(",", ":"))
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_path, self._path(feed.office))
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def load(self, office: str, now: datetime) -> tuple[Feed, datetime, str | None] | None:
        """Reject malformed, expired, wrong-source and wrong-office cached data."""
        if now.tzinfo is None:
            raise ValueError("Current time must carry timezone")
        try:
            path = self._path(office)
            if path.stat().st_size > 8_000_000:
                return None
            with path.open("r", encoding="utf-8") as file:
                document = json.load(file)
            if (document.get("version") != 1 or
                    document.get("url") != self.source_url):
                return None
            checked = datetime.fromisoformat(document["last_success_at"])
            if checked.tzinfo is None:
                return None
            age = now.astimezone(timezone.utc) - checked.astimezone(timezone.utc)
            if not timedelta(0) <= age <= MAX_AGE:
                return None
            feed = parse_feed(document["payload"], office)
            etag = document.get("etag")
            if etag is not None and not isinstance(etag, str):
                return None
            return feed, checked, etag
        except (OSError, ValueError, TypeError, KeyError, AttributeError,
                FeedValidationError):
            return None
