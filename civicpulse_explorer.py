"""Pure state and race navigation helpers for CivicPulse.

These helpers never infer missing vote totals or winners.
"""
from __future__ import annotations

from typing import Any

from civicpulse_registry import STATES


def state_contests(rows: list[dict[str, Any]], state: str,
                   chamber: str = "Both") -> list[dict[str, Any]]:
    """Return the tracked contests in one state, with available results first.

    The original normalized rows are preserved so absent source data remains
    missing (not zero) and candidate details stay attached to each race.
    """
    if state not in STATES:
        raise ValueError("Select a valid U.S. state")
    if chamber not in ("Both", "House", "Senate"):
        raise ValueError("Unsupported chamber")

    rank = {"Results reported": 0, "Listed, no votes yet": 1}
    selected = [row for row in rows if row.get("State") == state
                and (chamber == "Both" or row.get("Chamber") == chamber)]
    return sorted(
        selected,
        key=lambda row: (rank.get(row.get("Coverage"), 2),
                         0 if row.get("Chamber") == "Senate" else 1,
                         str(row.get("Seat", ""))),
    )


def candidate_vote_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only candidates with actual reported vote counts for charts."""
    candidates = row.get("candidates")
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates
            if isinstance(candidate, dict)
            and isinstance(candidate.get("Candidate"), str)
            and candidate["Candidate"].strip()
            and type(candidate.get("Votes")) is int
            and candidate["Votes"] >= 0]


def has_positive_candidate_votes(candidates: list[dict[str, Any]]) -> bool:
    """Detect a real positive candidate count without summing partial votes.

    Summing even individually valid integer counts through pandas int64 can
    overflow and turn a positive total negative, hiding the race chart. This
    predicate never manufactures a race-wide total or treats missing as zero.
    """
    return any(
        isinstance(candidate, dict)
        and isinstance(candidate.get("Candidate"), str)
        and bool(candidate["Candidate"].strip())
        and type(candidate.get("Votes")) is int
        and candidate["Votes"] > 0
        for candidate in candidates
    )
