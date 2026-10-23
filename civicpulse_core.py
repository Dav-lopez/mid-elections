"""Data contracts and normalization for CivicPulse.

Pure functions in this module are deliberately independent of Streamlit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


class FeedValidationError(ValueError):
    """A response did not conform to the documented election feed."""


@dataclass(frozen=True)
class Feed:
    office: str
    year: int
    races: dict[str, dict[str, Any]]
    live: bool
    stale: bool
    counting: bool
    final: bool
    as_of: str | None
    source: str

    @property
    def status(self) -> str:
        if self.stale:
            return "Stale at source"
        if self.live:
            return "Live counting"
        if self.final:
            return "Precinct reporting complete (not certified)"
        if self.counting:
            return "Counting / awaiting feed refresh"
        return "Awaiting election results"


def parse_feed(payload: Any, office: str, year: int = 2026) -> Feed:
    if not isinstance(payload, dict):
        raise FeedValidationError("Feed payload must be a JSON object")
    if payload.get("api") != 1:
        raise FeedValidationError("Unsupported results API version")
    if payload.get("year") != year or str(payload.get("office", "")).casefold() != office.casefold():
        raise FeedValidationError("Provider returned a different election or office")
    races = payload.get("races")
    if not isinstance(races, dict):
        raise FeedValidationError("'races' must be an object")
    for field in ("live", "stale", "counting", "final"):
        if not isinstance(payload.get(field), bool):
            raise FeedValidationError(f"'{field}' must be boolean")
    cleaned: dict[str, dict[str, Any]] = {}
    for key, race in races.items():
        if not isinstance(key, str) or not isinstance(race, dict):
            raise FeedValidationError("Invalid race entry")
        cleaned[key.upper()] = race
    timestamp = payload.get("as_of")
    if timestamp is not None:
        if not isinstance(timestamp, str):
            raise FeedValidationError("'as_of' must be ISO-8601 string or null")
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise FeedValidationError("Invalid provider timestamp") from exc
    return Feed(
        office=office.title(), year=year, races=cleaned,
        live=payload["live"], stale=payload["stale"],
        counting=payload["counting"], final=payload["final"],
        as_of=timestamp, source=str(payload.get("source") or "unknown"),
    )


def valid_votes(value: Any) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value


def percent(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not 0 <= number <= 100:
        return None
    return number


def normalize_race(office: str, state: str, seat: str, race: dict | None,
                   feed_status: str, as_of: str | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "Chamber": office, "State": state, "Seat": seat,
        "Coverage": "Not available from this provider",
        "Votes": None, "Precincts (%)": None, "Leader (not winner)": "—",
        "Source call": "—", "Source timestamp": as_of or "—",
        "Feed health": feed_status, "candidates": [],
    }
    if race is None:
        return row
    candidates = []
    raw = race.get("cands", [])
    if isinstance(raw, list):
        for candidate in raw:
            if not isinstance(candidate, dict):
                continue
            name = candidate.get("n", "")
            if not isinstance(name, str) or not name.strip():
                continue
            candidates.append({
                "Candidate": name, "Party": str(candidate.get("p") or "—"),
                "Votes": valid_votes(candidate.get("v")),
                "Share (%)": percent(candidate.get("pct")),
            })
    candidates.sort(key=lambda entry: entry["Votes"] if entry["Votes"] is not None else -1, reverse=True)
    total = valid_votes(race.get("total"))
    if total is None and any(c["Votes"] is not None for c in candidates):
        total = sum(c["Votes"] or 0 for c in candidates)
    leader = str(race.get("leader") or "—")
    row.update({
        "Coverage": "Results reported" if total is not None and total > 0 else "Listed, no votes yet",
        "Votes": total, "Precincts (%)": percent(race.get("pct_in")),
        "Leader (not winner)": leader,
        "Source call": str(race.get("winner") or "—") if race.get("called") is True else "—",
        "candidates": candidates,
    })
    return row


def refresh_seconds(feeds: list[Feed | None], failures: int = 0) -> int:
    """Provider guidance: 60s live, 10m before votes, 15m when not live."""
    if failures:
        return min(60 * (2 ** min(failures, 4)), 600)
    active = [feed for feed in feeds if feed is not None]
    if any(feed.live for feed in active):
        return 60
    if any(feed.counting for feed in active):
        return 900
    return 600
