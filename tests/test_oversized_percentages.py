"""Oversized numeric fields from provider JSON must not crash race rendering."""
import unittest

from civicpulse_core import normalize_race, percent


class OversizedPercentageTests(unittest.TestCase):
    def test_oversized_positive_and_negative_json_integers_are_missing(self):
        huge = 10 ** 400
        self.assertIsNone(percent(huge))
        self.assertIsNone(percent(-huge))

    def test_valid_percentages_and_nonfinite_values_keep_existing_behavior(self):
        self.assertEqual(percent(0), 0.0)
        self.assertEqual(percent(100), 100.0)
        self.assertEqual(percent(12.5), 12.5)
        for value in (float("nan"), float("inf"), -float("inf"), True, "50"):
            with self.subTest(value=value):
                self.assertIsNone(percent(value))

    def test_oversized_precinct_and_candidate_percentages_do_not_crash_race(self):
        huge = 10 ** 400
        row = normalize_race(
            "House", "AZ", "AZ-01",
            {"total": 50, "pct_in": huge,
             "cands": [{"n": "Synthetic Candidate", "v": 50, "pct": -huge}]},
            "Live counting", None,
        )
        self.assertEqual(row["Coverage"], "Results reported")
        self.assertEqual(row["Votes"], 50)
        self.assertIsNone(row["Precincts (%)"])
        self.assertIsNone(row["candidates"][0]["Share (%)"])


if __name__ == "__main__":
    unittest.main()
