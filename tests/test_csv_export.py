"""Offline regression checks for CSV downloads containing provider-supplied text."""
import csv
import io
import unittest

import pandas as pd

from civicpulse_csv import neutralize_csv_cell, spreadsheet_safe_csv


class CsvExportTests(unittest.TestCase):
    def test_formula_prefixes_including_invisible_and_fullwidth_variants(self):
        risky = (
            "=1+1", "+SUM(1,2)", "-1+2", "@SUM(A1)",
            " \t=1+1", "\r=1+1", "\n=1+1", "\tplain text",
            "\ufeff=1+1", "\u200b＝SUM(A1)", "＝1+1", "＋1+1", "－1+1", "＠SUM(A1)",
        )
        for value in risky:
            with self.subTest(value=repr(value)):
                self.assertEqual(neutralize_csv_cell(value), "'" + value)
        for value in ("Jane Doe", "A, B", 'A"B', "", "  Jane", "'already text", "-", "=", "@"):
            if value in ("-", "=", "@"):
                self.assertEqual(neutralize_csv_cell(value), "'" + value)
            else:
                self.assertEqual(neutralize_csv_cell(value), value)
        for value in (None, 0, -5, 3.5):
            self.assertEqual(neutralize_csv_cell(value), value)

    def test_export_quotes_fields_preserves_numbers_and_does_not_mutate_frame(self):
        suspicious = '=HYPERLINK("https://example.invalid", "click")'
        frame = pd.DataFrame({
            "Seat": ["TX-01", "TX-02"],
            "Leader (not winner)": [suspicious, 'Name ",=1+1\nnext"'],
            "Source call": [" +SUM(A1)", "—"],
            "Votes": [42, None],
        })
        original = frame.copy(deep=True)
        output = spreadsheet_safe_csv(frame)
        self.assertTrue(output.startswith(b'"Seat","Leader (not winner)"'))
        rows = list(csv.DictReader(io.StringIO(output.decode("utf-8"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Leader (not winner)"], "'" + suspicious)
        self.assertEqual(rows[1]["Leader (not winner)"], 'Name ",=1+1\nnext"')
        self.assertEqual(rows[0]["Source call"], "' +SUM(A1)")
        self.assertEqual(rows[0]["Votes"], "42.0")
        self.assertEqual(rows[1]["Votes"], "")
        pd.testing.assert_frame_equal(frame, original)

    def test_plain_registry_export_retains_values(self):
        frame = pd.DataFrame({"State": ["TN", "NY"], "Contests": [9, 26]})
        rows = list(csv.DictReader(io.StringIO(spreadsheet_safe_csv(frame).decode())))
        self.assertEqual(rows, [
            {"State": "TN", "Contests": "9"},
            {"State": "NY", "Contests": "26"},
        ])


    def test_categorical_provider_text_and_untrusted_headers_are_escaped(self):
        # Categorical text is not an object or string dtype; previously it
        # bypassed the export sanitizer. Headers are spreadsheet cells too.
        frame = pd.DataFrame({
            "=HYPERLINK(A1)": pd.Series(["=SUM(1,2)", "safe"], dtype="category"),
            "Votes": [10, 20],
        })
        original = frame.copy(deep=True)
        rows = list(csv.DictReader(io.StringIO(spreadsheet_safe_csv(frame).decode("utf-8"))))
        self.assertEqual(rows[0]["'=HYPERLINK(A1)"], "'=SUM(1,2)")
        self.assertEqual(rows[1]["'=HYPERLINK(A1)"], "safe")
        self.assertEqual(rows[0]["Votes"], "10")
        pd.testing.assert_frame_equal(frame, original)

    def test_additional_invisible_formula_prefixes(self):
        for prefix in (chr(0x200c), chr(0x200d), chr(0x2060), chr(0x00a0), chr(0x202f)):
            value = prefix + "=1+1"
            with self.subTest(prefix=repr(prefix)):
                self.assertEqual(neutralize_csv_cell(value), "'" + value)


    def test_duplicate_column_labels_do_not_crash_or_skip_sanitization(self):
        frame = pd.DataFrame(
            [["=1+1", 9, "safe"], ["text", 10, "+SUM(1,2)"]],
            columns=["Name", "Votes", "Name"],
        )
        original = frame.copy(deep=True)
        rows = list(csv.reader(io.StringIO(spreadsheet_safe_csv(frame).decode("utf-8"))))
        self.assertEqual(rows, [
            ["Name", "Votes", "Name"],
            ["'=1+1", "9", "safe"],
            ["text", "10", "'+SUM(1,2)"],
        ])
        pd.testing.assert_frame_equal(frame, original)


if __name__ == "__main__":
    unittest.main()
