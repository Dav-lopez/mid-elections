"""Exercise the actual Streamlit script, not only the server's /health endpoint.

All provider responses are synthetic *empty* contract fixtures or explicit
network failures. These tests never represent actual election returns.
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

    def __init__(self, office):
        self.office = office

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
            "races": {},
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

    def test_source_outage_still_renders_a_warning_and_no_vote_totals(self):
        with patch.object(requests.Session, "get", side_effect=requests.Timeout("offline")):
            app = self._run()
        self.assertGreaterEqual(len(app.warning), 1)
        self.assertEqual(len(app.metric), 4)
        self.assertEqual(app.metric[2].value, "0")
        self.assertEqual(app.metric[3].value, "0")


if __name__ == "__main__":
    unittest.main()
