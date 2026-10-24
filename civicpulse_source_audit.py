"""Audit observed provider race identifiers against the tracked 2026 seat registry.

This is diagnostic only: a published key does not establish vote reporting,
and an absent key does not establish zero votes or a cancelled election.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from civicpulse_core import Feed
from civicpulse_registry import registry


@dataclass(frozen=True)
class KeyAudit:
    office: str
    tracked: int
    published: int
    matched: int
    unmatched: int
    not_published: int
    unmatched_examples: tuple[str, ...]

    @property
    def detail(self) -> str:
        if not self.published:
            return ("0 race identifiers published; empty pre-election feeds are valid "
                    "and do not imply zero votes")
        message = (
            f"{self.matched}/{self.published} published race identifiers match "
            f"the {self.tracked} tracked {self.office} contests"
        )
        if self.unmatched:
            examples = ", ".join(self.unmatched_examples)
            message += (
                f"; {self.unmatched} unmatched provider identifier(s) "
                f"(sample: {examples}) — review source-to-registry mapping"
            )
        message += (f"; {self.not_published} tracked contest identifier(s) not published "
                    "in this snapshot (not evidence of zero votes or no election)")
        return message + "; identifiers do not prove votes were reported"


def _safe_identifier(value: str) -> str:
    """Bound and sanitize untrusted source keys before Markdown reports."""
    return re.sub(r"[^A-Z0-9_-]", "?", value.upper())[:32] or "?"


def audit_feed_keys(feed: Feed) -> KeyAudit:
    """Compare actual published identifiers without inferring unreported races."""
    if feed.office not in ("House", "Senate"):
        raise ValueError("Unsupported office")
    expected = {item["Seat"] for item in registry()
                if item["Chamber"] == feed.office}
    published = set(feed.races)
    unknown = published - expected
    return KeyAudit(
        office=feed.office,
        tracked=len(expected),
        published=len(published),
        matched=len(published & expected),
        unmatched=len(unknown),
        not_published=len(expected - published),
        unmatched_examples=tuple(_safe_identifier(key)
                                 for key in sorted(unknown)[:5]),
    )


def reconciliation_rows(feed: Feed) -> list[dict[str, str]]:
    """Export every observed/missing registry key and every unmatched source key.

    These rows reconcile *identifiers*, not vote totals, results, or verified
    provider coverage. An unobserved key may be published later.
    Untrusted provider identifiers are sanitized for spreadsheet export.
    """
    if feed.office not in ("House", "Senate"):
        raise ValueError("Unsupported office")
    expected = {
        item["Seat"]: item["State"]
        for item in registry() if item["Chamber"] == feed.office
    }
    published = set(feed.races)
    rows = []
    for seat, state in sorted(expected.items()):
        observed = seat in published
        rows.append({
            "Office": feed.office,
            "State": state,
            "Tracked contest": seat,
            "Provider identifier": seat if observed else "",
            "Identifier audit": ("Observed in validated snapshot" if observed
                                 else "Not published in snapshot"),
        })
    for key in sorted(published - expected):
        rows.append({
            "Office": feed.office,
            "State": "Unverified",
            "Tracked contest": "",
            "Provider identifier": _safe_identifier(key),
            "Identifier audit": "Unmatched provider identifier",
        })
    return rows
