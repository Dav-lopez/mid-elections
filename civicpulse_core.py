"""Data contracts and normalization for CivicPulse.

Pure functions in this module are deliberately independent of Streamlit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
        if not key or key != key.strip():
            raise FeedValidationError("Invalid race identifier")
        canonical = key.upper()
        if canonical in cleaned:
            # Silent overwrites can replace one contest's results with another.
            # Fail the whole response and retain the last validated snapshot.
            raise FeedValidationError(
                f"Duplicate race identifier after case normalization: {canonical}"
            )
        cleaned[canonical] = race
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


def format_feed_timestamp(value: str | None) -> str:
    """Render provider ISO timestamps in real UTC; never relabel raw offsets."""
    if not value:
        return "Not published"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return f"{value} (timezone unspecified)"
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return "Invalid timestamp"


# The browser and Plotly represent JSON numbers as IEEE-754 doubles. Keep
# provider counts in the lossless integer range to prevent pandas overflow and
# misleading rounded counts. This is a transport bound, not a vote estimate.
MAX_SAFE_VOTES = (1 << 53) - 1


def valid_votes(value: Any) -> int | None:
    if type(value) is not int or not 0 <= value <= MAX_SAFE_VOTES:
        return None
    return value


def percent(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    # Check the range before converting: a valid JSON integer can be too
    # large for float(), raising OverflowError and crashing the dashboard.
    # These comparisons also reject NaN and infinities without conversion.
    if not 0 <= value <= 100:
        return None
    return float(value)


def normalize_race(office: str, state: str, seat: str, race: dict | None,
                   feed_status: str, as_of: str | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "Chamber": office, "State": state, "Seat": seat,
        "Coverage": "Not available from this provider",
        "Votes": None, "Precincts (%)": None, "Leader (not winner)": "—",
        "Source call": "—", "Feed as-of (UTC)": as_of or "—",
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
    # The published candidate list may be partial (write-ins, omitted candidates,
    # or delayed reporting). Never manufacture a race-wide total by summing it.
    total = valid_votes(race.get("total"))
    candidate_votes_published = any(
        candidate["Votes"] is not None and candidate["Votes"] > 0
        for candidate in candidates
    )
    has_reported_votes = (total is not None and total > 0) or candidate_votes_published
    # A provider's leader/call fields cannot substantiate a result when no
    # positive vote counts have been published. Suppress them rather than
    # implying a candidate is leading (or has won) a zero-vote contest.
    leader = race.get("leader")
    winner = race.get("winner")
    displayed_leader = (
        leader.strip() if has_reported_votes and isinstance(leader, str)
        and leader.strip() else "—"
    )
    source_call = (
        winner.strip() if has_reported_votes and race.get("called") is True
        and isinstance(winner, str) and winner.strip() else "—"
    )
    row.update({
        "Coverage": "Results reported" if has_reported_votes else "Listed, no votes yet",
        "Votes": total, "Precincts (%)": percent(race.get("pct_in")),
        "Leader (not winner)": displayed_leader,
        "Source call": source_call,
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


# States documented by Open America's results API (contract as of 2026-09-27).
# This describes provider capability, NOT a claim that votes have been reported.
PROVIDER_STATES = frozenset(
    "AR AZ CO CT FL GA IA ID IN LA MI MN NC PA RI SC TX UT VA VT WA WV".split()
)


def coverage_status(state: str, feed_available: bool, race_present: bool) -> str:
    """Distinguish unsupported geography from a pending race and feed outage.

    A supported state can still omit specific races (including unopposed races).
    Consequently, never equate a missing race with no votes cast.
    """
    if not feed_available:
        return "Source unavailable"
    if state not in PROVIDER_STATES:
        return "State not supported by provider"
    if not race_present:
        return "Race absent from provider feed"
    return "Present in provider feed"


def national_coverage_metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Count actual feed coverage, not inferred winners or missing-row zeros."""
    return {
        "reported": sum(row.get("Coverage") == "Results reported" for row in rows),
        "listed": sum(row.get("Coverage") in ("Results reported", "Listed, no votes yet") for row in rows),
        "provider_unsupported": sum(row.get("Coverage") == "State not supported by provider" for row in rows),
        "source_unavailable": sum(row.get("Coverage") == "Source unavailable" for row in rows),
    }
