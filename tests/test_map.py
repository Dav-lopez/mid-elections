"""Pure coverage-map tests: no remote feed or UI dependency."""
import unittest

from civicpulse_map import STATUS_LABELS, state_coverage


class CoverageMapTests(unittest.TestCase):
    def test_all_fifty_states_unique(self):
        result = state_coverage([])
        self.assertEqual(len(result), 50)
        self.assertEqual(len({r["State"] for r in result}), 50)

    def test_unsupported_state_is_not_a_zero_vote_claim(self):
        rows = [{"State": "CA", "Chamber": "House", "Coverage": "State not supported by provider"}]
        data = {r["State"]: r for r in state_coverage(rows)}
        self.assertEqual(data["CA"]["Status"], "State not supported")
        self.assertEqual(data["CA"]["Races with votes"], 0)

    def test_supported_state_missing_entries(self):
        data = {r["State"]: r for r in state_coverage([])}
        self.assertEqual(data["TX"]["Status"], "No races published")

    def test_listed_and_reported_count_distinct(self):
        rows = [
            {"State": "TX", "Chamber": "House", "Coverage": "Results reported"},
            {"State": "TX", "Chamber": "House", "Coverage": "Listed, no votes yet"},
            {"State": "TX", "Chamber": "House", "Coverage": "Race absent from provider feed"},
        ]
        tx = {r["State"]: r for r in state_coverage(rows)}["TX"]
        self.assertEqual(tx["Status"], "Some votes reported")
        self.assertEqual(tx["Races listed"], 2)
        self.assertEqual(tx["Races with votes"], 1)
        self.assertEqual(tx["Contests tracked"], 3)

    def test_partial_outage_takes_precedence_over_old_votes(self):
        rows = [{"State": "TX", "Chamber": "House", "Coverage": "Results reported"}]
        tx = {r["State"]: r for r in state_coverage(rows, {"House"})}["TX"]
        self.assertEqual(tx["Status"], "Provider unavailable")
        self.assertTrue(tx["Partial outage"])
        self.assertEqual(tx["Races with votes"], 1)

    def test_a_senate_outage_only_affects_states_with_senate_contests(self):
        rows = [{"State": "TX", "Chamber": "House", "Coverage": "Results reported"}]
        tx = {r["State"]: r for r in state_coverage(rows, {"Senate"})}["TX"]
        self.assertEqual(tx["Status"], "Some votes reported")
        self.assertFalse(tx["Partial outage"])

    def test_mixed_state_counts_and_partial_outage_remain_isolated(self):
        rows = [
            {"State": "TX", "Chamber": "House", "Coverage": "Results reported"},
            {"State": "TX", "Chamber": "Senate", "Coverage": "Listed, no votes yet"},
            {"State": "TX", "Chamber": "House", "Coverage": "Race absent from provider feed"},
            {"State": "AZ", "Chamber": "House", "Coverage": "Results reported"},
            {"State": "UNKNOWN", "Chamber": "House", "Coverage": "Results reported"},
        ]
        result = state_coverage(rows, {"Senate"})
        self.assertEqual(len(result), 50)
        data = {item["State"]: item for item in result}
        self.assertEqual(data["TX"]["Contests tracked"], 3)
        self.assertEqual(data["TX"]["Races listed"], 2)
        self.assertEqual(data["TX"]["Races with votes"], 1)
        self.assertEqual(data["TX"]["Status"], "Provider unavailable")
        self.assertTrue(data["TX"]["Partial outage"])
        self.assertEqual(data["AZ"]["Status"], "Some votes reported")
        self.assertFalse(data["AZ"]["Partial outage"])
        self.assertEqual(data["AZ"]["Races with votes"], 1)
        self.assertEqual(data["CA"]["Contests tracked"], 0)

    def test_large_synthetic_feed_aggregates_without_double_counting(self):
        rows = [
            {"State": "TX", "Chamber": "House",
             "Coverage": "Results reported" if i % 3 == 0 else "Listed, no votes yet"}
            for i in range(3000)
        ]
        tx = {item["State"]: item for item in state_coverage(rows)}["TX"]
        self.assertEqual(tx["Contests tracked"], 3000)
        self.assertEqual(tx["Races listed"], 3000)
        self.assertEqual(tx["Races with votes"], 1000)

    def test_status_palette_is_complete(self):
        self.assertEqual(len(STATUS_LABELS), 5)


if __name__ == "__main__":
    unittest.main()
