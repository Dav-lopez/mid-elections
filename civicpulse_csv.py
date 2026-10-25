"""Spreadsheet-oriented CSV export with formula-like provider text neutralized.

CSV has no cell types: spreadsheet programs may execute untrusted values as
formulas. This protects downloaded human-viewing exports without altering the
in-app data. It is not a universal guarantee after spreadsheet save/reopen.
"""
from __future__ import annotations

import csv

import pandas as pd

_FORMULA_PREFIXES = frozenset("=+-@＝＋－＠")
_LEADING_IGNORABLE = " \t\r\n\v\f\x00\ufeff\u200b\u200c\u200d\u2060\u00a0\u202f"


def neutralize_csv_cell(value: object) -> object:
    """Prefix risky text with an apostrophe; leave numbers and nulls intact."""
    if not isinstance(value, str) or not value:
        return value
    trimmed = value.lstrip(_LEADING_IGNORABLE)
    if value[0] in "\t\r\n" or (trimmed and trimmed[0] in _FORMULA_PREFIXES):
        return "'" + value
    return value


def spreadsheet_safe_csv(frame: pd.DataFrame) -> bytes:
    """Quote every CSV field and neutralize untrusted text, including headers."""
    safe = frame.copy()
    # Select by position: duplicate column labels make safe[label] a DataFrame,
    # so accessing .dtype or assigning by label can fail or alter both columns.
    for position in range(safe.shape[1]):
        series = safe.iloc[:, position]
        dtype = series.dtype
        if (pd.api.types.is_object_dtype(dtype)
                or pd.api.types.is_string_dtype(dtype)
                or isinstance(dtype, pd.CategoricalDtype)):
            safe.isetitem(position, series.map(neutralize_csv_cell))
    safe.columns = [neutralize_csv_cell(column) for column in safe.columns]
    return safe.to_csv(index=False, quoting=csv.QUOTE_ALL).encode("utf-8")
