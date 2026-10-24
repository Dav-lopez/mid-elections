"""Exercise the actual Streamlit script, not only the server's /health endpoint.

All provider responses are synthetic contract fixtures (empty, partial, or
unavailable). These tests never represent actual election returns.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
import streamlit as st
from streamlit.testing.v1 import AppTest


APP_PATH = str(Path(__file__).resolve().parents[1] / "app.py")


class EmptyFeedResponse:
    status_code = 200
    headers = {}

    def __init__(self, office, races=None):
        self.office = office
        self.races = {} if races is None else races

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "api": 1,
            "year": 2026,
            "office": self.office,
            "live": False,
            "stale": False,
            "counting": False,
            "final": False,
            "as_of": None,
            "source": "test-fixture-not-real-results",
            "races": self.races,
        }


class StreamlitExecutionSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            "ELECTION_RESULTS_URL": "https://example.invalid/civicpulse-fixture",
            "CIVICPULSE_CACHE_DIR": self.temp.name,
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        st.cache_resource.clear()

    def _run(self):
        app = AppTest.from_file(APP_PATH, default_timeout=30)
        app.run()
        self.assertEqual(
            len(app.exception), 0,
            "The Streamlit script must render without runtime exceptions: "
            + repr([item.message for item in app.exception]),
        )
        return app

    def test_empty_valid_feeds_render_without_invented_results(self):
        def respond(*args, **kwargs):
            return EmptyFeedResponse(kwargs["params"]["office"])

        with patch.object(requests.Session, "get", side_effect=respond) as get:
            app = self._run()
        self.assertEqual(get.call_count, 2)
        self.assertEqual(len(app.metric), 4)
        self.assertEqual(app.metric[0].value, "435")
        self.assertEqual(app.metric[1].value, "35")
        self.assertEqual(app.metric[2].value, "0")
        self.assertEqual(app.metric[3].value, "0")
        self.assertEqual(len(app.warning), 0)

    def test_partial_candidate_returns_render_without_inferred_race_total(self):
        """A partial synthetic race must show candidate votes, not a made-up total or call."""
        partial_house = {
            "AZ-01": {
                "cands": [
                    {"n": "Synthetic Candidate A", "p": "I", "v": 120, "pct": 60},
                    {"n": "Synthetic Candidate B", "p": "I", "v": 80, "pct": 40},
                ],
                "leader": "Synthetic Candidate A",
                "winner": "Synthetic Candidate A",
                "called": False,
                # No published race-wide total: candidate sums must not fill it.
            }
        }

        def respond(*args, **kwargs):
            office = kwargs["params"]["office"]
            return EmptyFeedResponse(office, partial_house if office == "House" else {})

        with patch.object(requests.Session, "get", side_effect=respond) as get:
            app = self._run()
            self.assertEqual(app.metric[2].value, "1", "One synthetic race reports votes")
            self.assertEqual(app.metric[3].value, "1", "Only one race is source-listed")
            spotlight = next(widget for widget in app.selectbox
                             if widget.label == "Inspect state")
            spotlight.set_value("AZ").run()

        self.assertEqual(get.call_count, 2, "State selection must reuse the shared feed cache")
        self.assertEqual(len(app.exception), 0)
        race_tables = [item.value for item in app.dataframe
                       if {"Seat", "Votes", "Source call"}.issubset(item.value.columns)]
        self.assertTrue(race_tables, "The state spotlight must show its race table")
        az_races = [table.loc[table["Seat"] == "AZ-01"]
                    for table in race_tables if "AZ-01" in table["Seat"].values]
        self.assertTrue(az_races, "The AZ-01 synthetic race must be visible")
        self.assertTrue(az_races[0]["Votes"].isna().all(),
                        "Never infer a total from the partial candidate list")
        self.assertEqual(az_races[0]["Source call"].iloc[0], "—",
                         "An uncalled provider leader is not a winner")

        candidate_tables = [item.value for item in app.dataframe
                            if {"Candidate", "Votes"}.issubset(item.value.columns)]
        self.assertTrue(candidate_tables, "Candidate breakdown must be rendered")
        votes = dict(zip(candidate_tables[0]["Candidate"], candidate_tables[0]["Votes"]))
        self.assertEqual(votes, {"Synthetic Candidate A": 120,
                                 "Synthetic Candidate B": 80})
        self.assertEqual(len(app.warning), 0)

    def test_unmatched_provider_keys_are_disclosed_without_assigning_results(self):
        """A valid but unmapped synthetic identifier must not become a tracked race."""
        def respond(*args, **kwargs):
            office = kwargs["params"]["office"]
            races = {"ZZ-99": {}} if office == "House" else {}
            return EmptyFeedResponse(office, races)

        with patch.object(requests.Session, "get", side_effect=respond) as get:
            app = self._run()

        self.assertEqual(get.call_count, 2)
        self.assertEqual(app.metric[2].value, "0", "Unmapped keys are not reported votes")
        self.assertEqual(app.metric[3].value, "0", "Unmapped keys are not tracked races")
        disclosures = [str(item.value) for item in app.markdown]
        self.assertTrue(
            any("0/1 published race identifiers match" in value for value in disclosures),
            "The source audit must disclose that no published House key matched",
        )
        warnings = [str(item.message) for item in app.warning]
        self.assertTrue(
            any("House: 1 provider race identifier(s)" in value for value in warnings),
            "Unmatched source identifiers must trigger an explicit mapping warning",
        )

    def test_source_outage_still_renders_a_warning_and_no_vote_totals(self):
        with patch.object(requests.Session, "get", side_effect=requests.Timeout("offline")):
            app = self._run()
        self.assertGreaterEqual(len(app.warning), 1)
        self.assertEqual(len(app.metric), 4)
        self.assertEqual(app.metric[2].value, "0")
        self.assertEqual(app.metric[3].value, "0")


if __name__ == "__main__":
    unittest.main()
