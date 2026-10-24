"""Malformed numeric percentages must not reach dashboard charts."""
import unittest

from civicpulse_core import normalize_race, percent


class NonfinitePercentTests(unittest.TestCase):
    def test_nan_infinity_and_boolean_are_missing(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, False):
            with self.subTest(value=value):
                self.assertIsNone(percent(value))

    def test_boundary_values_are_preserved(self):
        self.assertEqual(percent(0), 0.0)
        self.assertEqual(percent(100), 100.0)
        self.assertEqual(percent(33.5), 33.5)
        self.assertIsNone(percent(101))

    def test_race_candidate_and_precinct_values_are_safe(self):
        race = {
            "pct_in": float("nan"),
            "cands": [{"n": "Synthetic Candidate", "pct": float("inf"), "v": 7}],
        }
        row = normalize_race("House", "AZ", "AZ-01", race, "Live counting", None)
        self.assertIsNone(row["Precincts (%)"])
        self.assertIsNone(row["candidates"][0]["Share (%)"])
        self.assertIsNone(row["Votes"])
        self.assertEqual(row["Coverage"], "Results reported")


if __name__ == "__main__":
    unittest.main()
