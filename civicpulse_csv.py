"""Spreadsheet-oriented CSV export with formula-like provider text neutralized.

CSV has no cell types: spreadsheet programs may execute untrusted values as
formulas. This protects downloaded human-viewing exports without altering the
in-app data. It is not a universal guarantee after spreadsheet save/reopen.
"""
from __future__ import annotations

import csv

import pandas as pd

_FORMULA_PREFIXES = frozenset("=+-@＝＋－＠")
_LEADING_IGNORABLE = " \t\r\n\v\f\x00\ufeff\u200b"


def neutralize_csv_cell(value: object) -> object:
    """Prefix risky text with an apostrophe; leave numbers and nulls intact."""
    if not isinstance(value, str) or not value:
        return value
    trimmed = value.lstrip(_LEADING_IGNORABLE)
    if value[0] in "\t\r\n" or (trimmed and trimmed[0] in _FORMULA_PREFIXES):
        return "'" + value
    return value


def spreadsheet_safe_csv(frame: pd.DataFrame) -> bytes:
    """Quote every CSV field and neutralize untrusted text at export time."""
    safe = frame.copy()
    for column in safe.columns:
        if (pd.api.types.is_object_dtype(safe[column].dtype)
                or pd.api.types.is_string_dtype(safe[column].dtype)):
            safe[column] = safe[column].map(neutralize_csv_cell)
    return safe.to_csv(index=False, quoting=csv.QUOTE_ALL).encode("utf-8")
