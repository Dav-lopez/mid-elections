import unittest

from civicpulse_core import (
    FeedValidationError, normalize_race, parse_feed, percent, refresh_seconds, valid_votes
)


def payload(**overrides):
    base = {
        "api": 1, "year": 2026, "office": "House", "live": False,
        "stale": False, "counting": False, "final": False,
        "as_of": None, "source": "", "races": {},
    }
    base.update(overrides)
    return base


class FeedTests(unittest.TestCase):
    def test_valid_empty_feed(self):
        feed = parse_feed(payload(), "House")
        self.assertEqual(feed.races, {})
        self.assertEqual(refresh_seconds([feed]), 600)

    def test_wrong_office_rejected(self):
        with self.assertRaises(FeedValidationError):
            parse_feed(payload(office="Senate"), "House")

    def test_wrong_year_rejected(self):
        with self.assertRaises(FeedValidationError):
            parse_feed(payload(year=2024), "House")

    def test_wrong_api_version_rejected(self):
        with self.assertRaises(FeedValidationError):
            parse_feed(payload(api=2), "House")

    def test_malformed_races_rejected(self):
        with self.assertRaises(FeedValidationError):
            parse_feed(payload(races=[]), "House")

    def test_missing_race_not_zero(self):
        row = normalize_race("House", "CA", "CA-12", None, "Awaiting results", None)
        self.assertIsNone(row["Votes"])
        self.assertIn("Not available", row["Coverage"])

    def test_candidate_vote_totals_and_leader(self):
        raw = {"leader": "D", "called": False,
               "cands": [{"n": "A", "p": "D", "v": 150, "pct": 60},
                         {"n": "B", "p": "R", "v": 100, "pct": 40}]}
        row = normalize_race("House", "CA", "CA-12", raw, "Live counting", "2026-11-04T01:00:00+00:00")
        self.assertEqual(row["Votes"], 250)
        self.assertEqual(row["Leader (not winner)"], "D")
        self.assertEqual(row["Source call"], "—")
        self.assertEqual(row["Coverage"], "Results reported")

    def test_zero_votes_are_not_reported_results(self):
        row = normalize_race("Senate", "GA", "GA", {"total": 0}, "Awaiting results", None)
        self.assertEqual(row["Coverage"], "Listed, no votes yet")

    def test_reject_bad_vote_counts(self):
        self.assertIsNone(valid_votes(-1))
        self.assertIsNone(valid_votes(True))
        self.assertIsNone(valid_votes("100"))
        self.assertIsNone(percent(105))

    def test_adaptive_refresh(self):
        live = parse_feed(payload(live=True, counting=True), "House")
        stale = parse_feed(payload(stale=True, counting=True), "House")
        self.assertEqual(refresh_seconds([live, stale]), 60)
        self.assertEqual(refresh_seconds([stale]), 900)
        self.assertEqual(refresh_seconds([None], failures=5), 600)


if __name__ == "__main__":
    unittest.main()
