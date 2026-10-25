"""Regression tests: source labels must not imply leads or wins before votes exist."""
import unittest

from civicpulse_core import normalize_race


def normalize(race):
    return normalize_race("House", "AZ", "AZ-01", race, "Awaiting results", None)


class NoVoteLeaderTests(unittest.TestCase):
    def test_zero_vote_race_suppresses_unsubstantiated_leader_and_call(self):
        row = normalize({
            "total": 0,
            "cands": [{"n": "Example A", "v": 0}, {"n": "Example B", "v": 0}],
            "leader": "Example A", "winner": "Example A", "called": True,
        })
        self.assertEqual(row["Coverage"], "Listed, no votes yet")
        self.assertEqual(row["Votes"], 0)
        self.assertEqual(row["Leader (not winner)"], "—")
        self.assertEqual(row["Source call"], "—")

    def test_missing_or_invalid_vote_counts_cannot_establish_lead(self):
        for votes in (None, "200", -1, True, 2 ** 70):
            with self.subTest(votes=votes):
                row = normalize({
                    "cands": [{"n": "Example A", "v": votes}],
                    "leader": "Example A", "winner": "Example A", "called": True,
                })
                self.assertEqual(row["Coverage"], "Listed, no votes yet")
                self.assertEqual(row["Leader (not winner)"], "—")
                self.assertEqual(row["Source call"], "—")

    def test_positive_candidate_votes_can_support_leader_without_race_total(self):
        row = normalize({
            "cands": [{"n": "Example A", "v": 12}],
            "leader": "Example A", "winner": "Example A", "called": False,
        })
        self.assertEqual(row["Coverage"], "Results reported")
        self.assertIsNone(row["Votes"], "Never sum partial candidate lists")
        self.assertEqual(row["Leader (not winner)"], "Example A")
        self.assertEqual(row["Source call"], "—")

    def test_positive_published_total_preserves_explicit_source_call(self):
        row = normalize({
            "total": 17, "leader": " Example A ",
            "winner": " Example A ", "called": True,
        })
        self.assertEqual(row["Votes"], 17)
        self.assertEqual(row["Leader (not winner)"], "Example A")
        self.assertEqual(row["Source call"], "Example A")

    def test_malformed_label_types_are_not_rendered_as_names(self):
        row = normalize({
            "total": 10, "leader": {"name": "Example A"},
            "winner": ["Example A"], "called": True,
        })
        self.assertEqual(row["Leader (not winner)"], "—")
        self.assertEqual(row["Source call"], "—")

    def test_blank_source_labels_are_not_rendered(self):
        row = normalize({"total": 10, "leader": "  ", "winner": "\n", "called": True})
        self.assertEqual(row["Leader (not winner)"], "—")
        self.assertEqual(row["Source call"], "—")


if __name__ == "__main__":
    unittest.main()
