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


def state_coverage(rows: list[dict[str, Any]], unavailable_offices: set[str] | None = None
                   ) -> list[dict[str, Any]]:
    """Return one independently verifiable availability summary per state.

    A failed House or Senate request cannot silently become a zero-result state.
    When there is a partial outage, flag it even if other races are reporting.
    """
    unavailable = unavailable_offices or set()
    summaries = []
    for state in STATES:
        local = [r for r in rows if r.get("State") == state]
        listed = sum(r.get("Coverage") in ("Results reported", "Listed, no votes yet") for r in local)
        reported = sum(r.get("Coverage") == "Results reported" for r in local)
        active_offices = {r.get("Chamber") for r in local}
        has_outage = bool(active_offices & unavailable)
        if has_outage:
            status = "Provider unavailable"
        elif state not in PROVIDER_STATES:
            status = "State not supported"
        elif reported:
            status = "Some votes reported"
        elif listed:
            status = "Races listed; no votes"
        else:
            status = "No races published"
        summaries.append({
            "State": state, "Status": status,
            "Races listed": listed, "Races with votes": reported,
            "Contests tracked": len(local), "Partial outage": has_outage,
        })
    return summaries
