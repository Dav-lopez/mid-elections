import unittest

from civicpulse_core import (
    FeedValidationError, coverage_status, national_coverage_metrics,
    normalize_race, parse_feed, percent, refresh_seconds, valid_votes
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

    def test_api_version_requires_json_integer_not_bool_or_float(self):
        for api in (True, 1.0):
            with self.subTest(api=api):
                with self.assertRaisesRegex(FeedValidationError, "API version"):
                    parse_feed(payload(api=api), "House")

    def test_election_year_requires_json_integer_not_float(self):
        with self.assertRaisesRegex(FeedValidationError, "different election"):
            parse_feed(payload(year=2026.0), "House")
        self.assertEqual(parse_feed(payload(year=2026), "House").year, 2026)

    def test_malformed_races_rejected(self):
        with self.assertRaises(FeedValidationError):
            parse_feed(payload(races=[]), "House")

    def test_case_normalization_keeps_single_identifier(self):
        feed = parse_feed(payload(races={"az-01": {"total": 12}}), "House")
        self.assertEqual(feed.races, {"AZ-01": {"total": 12}})

    def test_case_colliding_identifiers_rejected_not_overwritten(self):
        with self.assertRaisesRegex(FeedValidationError, "Duplicate race identifier"):
            parse_feed(payload(races={
                "az-01": {"total": 12},
                "AZ-01": {"total": 99},
            }), "House")

    def test_empty_and_whitespace_padded_identifiers_rejected(self):
        for identifier in ("", " AZ-01", "AZ-01 ", "  "):
            with self.subTest(identifier=identifier):
                with self.assertRaisesRegex(FeedValidationError, "Invalid race identifier"):
                    parse_feed(payload(races={identifier: {"total": 12}}), "House")

    def test_missing_race_not_zero(self):
        row = normalize_race("House", "CA", "CA-12", None, "Awaiting results", None)
        self.assertIsNone(row["Votes"])
        self.assertIn("Not available", row["Coverage"])

    def test_candidate_votes_do_not_imply_published_race_total(self):
        raw = {"leader": "D", "called": False,
               "cands": [{"n": "A", "p": "D", "v": 150, "pct": 60},
                         {"n": "B", "p": "R", "v": 100, "pct": 40}]}
        row = normalize_race("House", "CA", "CA-12", raw, "Live counting", "2026-11-04T01:00:00+00:00")
        self.assertIsNone(row["Votes"], "Never infer a race total from candidate entries")
        self.assertEqual([candidate["Votes"] for candidate in row["candidates"]], [150, 100])
        self.assertEqual(row["Leader (not winner)"], "D")
        self.assertEqual(row["Source call"], "—")
        self.assertEqual(row["Coverage"], "Results reported")

    def test_partial_candidate_list_does_not_treat_missing_as_zero(self):
        row = normalize_race("House", "TX", "TX-01", {
            "cands": [{"n": "A", "v": 100}, {"n": "B"},
                      {"n": "C", "v": "25"}],
        }, "Live counting", None)
        self.assertIsNone(row["Votes"])
        self.assertEqual([candidate["Votes"] for candidate in row["candidates"]],
                         [100, None, None])
        self.assertEqual(row["Coverage"], "Results reported")

    def test_explicit_provider_total_is_preserved_not_recomputed(self):
        row = normalize_race("Senate", "TX", "TX", {
            "total": 500, "cands": [{"n": "A", "v": 120},
                                    {"n": "B", "v": 90}],
        }, "Live counting", None)
        self.assertEqual(row["Votes"], 500)
        self.assertEqual(row["Coverage"], "Results reported")

    def test_invisible_only_candidate_cannot_imply_reported_votes(self):
        row = normalize_race("House", "TX", "TX-01", {
            "leader": "\u200b", "winner": "\u2060", "called": True,
            "cands": [{"n": "\u200b", "v": 15},
                      {"n": "\ufe0f", "v": 12}],
        }, "Live counting", None)
        self.assertEqual(row["Coverage"], "Listed, no votes yet")
        self.assertEqual(row["candidates"], [])
        self.assertEqual(row["Leader (not winner)"], "—")
        self.assertEqual(row["Source call"], "—")

    def test_invisible_only_leader_and_winner_suppressed_with_real_votes(self):
        row = normalize_race("Senate", "TX", "TX", {
            "total": 9, "leader": "\u200b", "winner": "\u2060",
            "called": True, "cands": [{"n": "A\u200b", "v": 9}],
        }, "Live counting", None)
        self.assertEqual(row["Coverage"], "Results reported")
        self.assertEqual(row["candidates"][0]["Candidate"], "A")
        self.assertEqual(row["Leader (not winner)"], "—")
        self.assertEqual(row["Source call"], "—")

    def test_bidi_formatting_controls_cannot_spoof_visible_result_labels(self):
        row = normalize_race("House", "TX", "TX-01", {
            "leader": "Alice\u202eXYZ", "winner": "Alice\u2067XYZ",
            "called": True, "cands": [
                {"n": "Alice\u202eXYZ", "v": 10},
                {"n": "\u061c\u200e", "v": 99},
                {"n": "علي", "v": 3},
                {"n": "👩\u200d💻", "v": 4},
            ],
        }, "Live counting", None)
        self.assertEqual(row["Coverage"], "Results reported")
        self.assertEqual(row["Leader (not winner)"], "AliceXYZ")
        self.assertEqual(row["Source call"], "AliceXYZ")
        self.assertEqual([c["Candidate"] for c in row["candidates"]],
                         ["AliceXYZ", "👩\u200d💻", "علي"])
        self.assertEqual([c["Votes"] for c in row["candidates"]], [10, 4, 3])

    def test_line_and_paragraph_separators_cannot_split_result_labels(self):
        row = normalize_race("House", "TX", "TX-01", {
            "leader": "Al\u2028ice", "winner": "Al\u2029ice",
            "called": True,
            "cands": [
                {"n": "Al\u2028ice", "p": "D\u2029R", "v": 11},
                {"n": "\u2028\u2029", "v": 99},
            ],
        }, "Live counting", None)
        self.assertEqual(row["Coverage"], "Results reported")
        self.assertEqual(row["Leader (not winner)"], "Al ice")
        self.assertEqual(row["Source call"], "Al ice")
        self.assertEqual(len(row["candidates"]), 1)
        self.assertEqual(row["candidates"][0]["Candidate"], "Al ice")
        self.assertEqual(row["candidates"][0]["Party"], "D R")
        self.assertEqual(row["candidates"][0]["Votes"], 11)

    def test_embedded_controls_and_surrogates_removed_from_result_labels(self):
        row = normalize_race("House", "TX", "TX-01", {
            "leader": "Al\u200b\u0000\ud800ice",
            "winner": "Al\u2060ice",
            "called": True,
            "cands": [
                {"n": "Al\u200b\u0000\ud800ice", "p": "D\u202eR", "v": 10},
                {"n": "👩\u200d💻", "p": "I\u000a", "v": 2},
                {"n": "علي\u200c", "p": "\udfff", "v": 1},
            ],
        }, "Live counting", None)
        self.assertEqual(row["Coverage"], "Results reported")
        self.assertEqual(row["Leader (not winner)"], "Alice")
        self.assertEqual(row["Source call"], "Alice")
        self.assertEqual(
            [entry["Candidate"] for entry in row["candidates"]],
            ["Alice", "👩\u200d💻", "علي\u200c"],
        )
        self.assertEqual(
            [entry["Party"] for entry in row["candidates"]],
            ["DR", "I", "—"],
        )
        self.assertEqual(
            [entry["Votes"] for entry in row["candidates"]],
            [10, 2, 1],
        )
        for entry in row["candidates"]:
            entry["Candidate"].encode("utf-8")
            entry["Party"].encode("utf-8")

    def test_no_positive_votes_and_no_total_stays_unreported(self):
        row = normalize_race("House", "TX", "TX-01", {
            "cands": [{"n": "A", "v": 0}, {"n": "B", "v": None}],
        }, "Awaiting results", None)
        self.assertIsNone(row["Votes"])
        self.assertEqual(row["Coverage"], "Listed, no votes yet")

    def test_invalid_provider_total_is_not_replaced_by_candidate_sum(self):
        for bad_total in (-1, True, "300"):
            with self.subTest(total=bad_total):
                row = normalize_race("House", "TX", "TX-01", {
                    "total": bad_total, "cands": [{"n": "A", "v": 50}],
                }, "Live counting", None)
                self.assertIsNone(row["Votes"])
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


class CoverageTests(unittest.TestCase):
    def test_unsupported_state(self):
        self.assertEqual(coverage_status("CA", True, False), "State not supported by provider")

    def test_supported_state_with_missing_race(self):
        self.assertEqual(coverage_status("TX", True, False), "Race absent from provider feed")

    def test_outage_takes_precedence(self):
        self.assertEqual(coverage_status("CA", False, False), "Source unavailable")
        self.assertEqual(coverage_status("TX", False, False), "Source unavailable")

    def test_race_present(self):
        self.assertEqual(coverage_status("TX", True, True), "Present in provider feed")

    def test_coverage_metrics(self):
        rows = [
            {"Coverage": "Results reported"},
            {"Coverage": "Listed, no votes yet"},
            {"Coverage": "State not supported by provider"},
            {"Coverage": "Race absent from provider feed"},
            {"Coverage": "Source unavailable"},
        ]
        self.assertEqual(national_coverage_metrics(rows), {
            "reported": 1, "listed": 2, "provider_unsupported": 1, "source_unavailable": 1
        })


if __name__ == "__main__":
    unittest.main()
