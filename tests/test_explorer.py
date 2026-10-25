"""State spotlight tests: navigation does not manufacture election data."""
import unittest

from civicpulse_explorer import candidate_vote_rows, has_positive_candidate_votes, state_contests


class StateExplorerTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"State": "TX", "Chamber": "House", "Seat": "TX-02",
             "Coverage": "Race absent from provider feed", "Votes": None,
             "candidates": []},
            {"State": "TX", "Chamber": "House", "Seat": "TX-01",
             "Coverage": "Results reported", "Votes": 12,
             "candidates": [{"Candidate": "Example", "Votes": 12}]},
            {"State": "TX", "Chamber": "Senate", "Seat": "TX",
             "Coverage": "Listed, no votes yet", "Votes": None,
             "candidates": []},
            {"State": "CA", "Chamber": "House", "Seat": "CA-01",
             "Coverage": "Results reported", "Votes": 1, "candidates": []},
        ]

    def test_state_filter_prioritizes_reported_then_listed(self):
        result = state_contests(self.rows, "TX")
        self.assertEqual([row["Seat"] for row in result], ["TX-01", "TX", "TX-02"])
        self.assertIsNone(result[-1]["Votes"])
        self.assertIs(result[0], self.rows[1])

    def test_chamber_filter(self):
        result = state_contests(self.rows, "TX", "Senate")
        self.assertEqual([row["Seat"] for row in result], ["TX"])

    def test_missing_chamber_has_empty_result(self):
        self.assertEqual(state_contests(self.rows, "CA", "Senate"), [])

    def test_invalid_state_or_chamber_rejected(self):
        with self.assertRaises(ValueError):
            state_contests(self.rows, "XX")
        with self.assertRaises(ValueError):
            state_contests(self.rows, "TX", "Governor")

    def test_candidate_votes_only_accept_nonnegative_integers(self):
        row = {"candidates": [
            {"Candidate": "A", "Votes": 0},
            {"Candidate": "B", "Votes": 23},
            {"Candidate": "C", "Votes": None},
            {"Candidate": "D", "Votes": -3},
            {"Candidate": "E", "Votes": True},
            {"Candidate": "F", "Votes": "4"},
            {"Candidate": "", "Votes": 1},
            {"Votes": 1},
        ]}
        result = candidate_vote_rows(row)
        self.assertEqual([candidate["Candidate"] for candidate in result], ["A", "B"])

    def test_missing_candidate_breakdown(self):
        self.assertEqual(candidate_vote_rows({"candidates": None}), [])
        self.assertEqual(candidate_vote_rows({}), [])

    def test_positive_candidate_detection_avoids_int64_sum_overflow(self):
        # 1,025 individually valid browser-safe counts overflow pandas int64
        # when summed, incorrectly hiding the chart despite positive votes.
        maximum = (1 << 53) - 1
        candidates = [
            {"Candidate": f"Example {i}", "Votes": maximum}
            for i in range(1025)
        ]
        self.assertTrue(has_positive_candidate_votes(candidates))

    def test_positive_candidate_detection_ignores_missing_and_zero(self):
        self.assertFalse(has_positive_candidate_votes([]))
        self.assertFalse(has_positive_candidate_votes([
            {"Candidate": "A", "Votes": 0},
            {"Candidate": "B", "Votes": None},
        ]))
        self.assertTrue(has_positive_candidate_votes([
            {"Candidate": "A", "Votes": 0},
            {"Candidate": "B", "Votes": 1},
        ]))

    def test_positive_candidate_detection_rejects_malformed_values(self):
        self.assertFalse(has_positive_candidate_votes([
            None, {"Candidate": "A", "Votes": True},
            {"Candidate": "B", "Votes": "12"},
            {"Candidate": "", "Votes": 12},
            {"Candidate": "C", "Votes": -1},
        ]))


if __name__ == "__main__":
    unittest.main()
