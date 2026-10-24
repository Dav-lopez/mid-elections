"""State-level provider coverage status for the visual election explorer.

This is a *data availability* map, never a map of winners or partisan outcomes.
"""
from __future__ import annotations

from typing import Any

from civicpulse_core import PROVIDER_STATES
from civicpulse_registry import STATES

STATUS_LABELS = (
    "Provider unavailable",
    "State not supported",
    "No races published",
    "Races listed; no votes",
    "Some votes reported",
)
STATUS_COLORS = ("#B4BEC9", "#E5E9EF", "#F4D6A1", "#86B9D1", "#167F79")

_LISTED = frozenset(("Results reported", "Listed, no votes yet"))


def state_coverage(rows: list[dict[str, Any]], unavailable_offices: set[str] | None = None
                   ) -> list[dict[str, Any]]:
    """Aggregate availability in one row pass, then emit states in registry order.

    O(number of rows + number of states), rather than scanning every race for
    each state. A partial House/Senate outage still takes precedence over any
    last-known votes, without treating missing results as zero.
    """
    unavailable = unavailable_offices or set()
    # Preserve the original state ordering and ignore rows outside the registry.
    grouped = {
        state: {"listed": 0, "reported": 0, "tracked": 0, "offices": set()}
        for state in STATES
    }
    for row in rows:
        entry = grouped.get(row.get("State"))
        if entry is None:
            continue
        entry["tracked"] += 1
        entry["offices"].add(row.get("Chamber"))
        coverage = row.get("Coverage")
        if coverage in _LISTED:
            entry["listed"] += 1
        if coverage == "Results reported":
            entry["reported"] += 1

    summaries = []
    for state, entry in grouped.items():
        has_outage = bool(entry["offices"] & unavailable)
        if has_outage:
            status = "Provider unavailable"
        elif state not in PROVIDER_STATES:
            status = "State not supported"
        elif entry["reported"]:
            status = "Some votes reported"
        elif entry["listed"]:
            status = "Races listed; no votes"
        else:
            status = "No races published"
        summaries.append({
            "State": state, "Status": status,
            "Races listed": entry["listed"],
            "Races with votes": entry["reported"],
            "Contests tracked": entry["tracked"],
            "Partial outage": has_outage,
        })
    return summaries
