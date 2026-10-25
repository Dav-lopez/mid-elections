"""Provider vote counts must be safe for pandas and browser number rendering."""
import unittest

import pandas as pd

from civicpulse_core import MAX_SAFE_VOTES, normalize_race, valid_votes


class OversizedVoteCountTests(unittest.TestCase):
    def test_out_of_range_counts_are_missing_not_zero(self):
        huge = 10 ** 400
        for invalid in (huge, -huge, MAX_SAFE_VOTES + 1, -1, True, 1.0, "12"):
            with self.subTest(value=str(invalid)[:30]):
                self.assertIsNone(valid_votes(invalid))
        self.assertEqual(valid_votes(0), 0)
        self.assertEqual(valid_votes(MAX_SAFE_VOTES), MAX_SAFE_VOTES)

    def test_oversized_total_and_candidate_counts_do_not_replace_valid_votes(self):
        huge = 10 ** 400
        row = normalize_race(
            "House", "AZ", "AZ-01",
            {"total": huge, "cands": [
                {"n": "Invalid provider count", "v": huge},
                {"n": "Valid provider count", "v": 12},
            ]}, "Live counting", None,
        )
        self.assertIsNone(row["Votes"], "Do not fabricate a race total")
        self.assertEqual(row["Coverage"], "Results reported")
        self.assertEqual([c["Votes"] for c in row["candidates"]], [12, None])

    def test_only_invalid_counts_are_not_reported_results(self):
        row = normalize_race(
            "Senate", "AZ", "AZ",
            {"total": 10 ** 400, "cands": [{"n": "A", "v": 10 ** 400}]},
            "Awaiting results", None,
        )
        self.assertEqual(row["Coverage"], "Listed, no votes yet")
        self.assertIsNone(row["Votes"])
        self.assertIsNone(row["candidates"][0]["Votes"])

    def test_mixed_race_rows_can_be_serialized_by_pandas(self):
        # Without the bound, pandas raises OverflowError while constructing
        # a mixed-size numeric column, before Streamlit can render the table.
        huge = 10 ** 400
        rows = [
            normalize_race("House", "AZ", "AZ-01", {"total": huge}, "Live counting", None),
            normalize_race("House", "AZ", "AZ-02", {"total": 25}, "Live counting", None),
        ]
        frame = pd.DataFrame([{k: v for k, v in row.items() if k != "candidates"}
                              for row in rows])
        self.assertTrue(pd.isna(frame.loc[0, "Votes"]))
        self.assertEqual(frame.loc[1, "Votes"], 25)


if __name__ == "__main__":
    unittest.main()
