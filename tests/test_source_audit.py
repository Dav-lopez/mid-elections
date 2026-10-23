"""Provider ID reconciliation: never equate missing keys with missing votes."""
import json
import unittest

from civicpulse_core import parse_feed
from civicpulse_source_audit import audit_feed_keys
from scripts.monitor_deployment import check_feed


def fixture(office="House", races=None):
    return {
        "api": 1, "year": 2026, "office": office,
        "live": False, "stale": False, "counting": False, "final": False,
        "as_of": None, "source": "synthetic-test-only",
        "races": {} if races is None else races,
    }


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    def read(self, limit):
        return self.body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SourceKeyAuditTests(unittest.TestCase):
    def test_empty_feed_is_not_missing_vote_claim(self):
        audit = audit_feed_keys(parse_feed(fixture(), "House"))
        self.assertEqual(audit.tracked, 435)
        self.assertEqual(audit.published, 0)
        self.assertEqual(audit.matched, 0)
        self.assertEqual(audit.unmatched, 0)
        self.assertIn("do not imply zero votes", audit.detail)

    def test_known_and_unknown_keys_are_distinguished(self):
        audit = audit_feed_keys(parse_feed(fixture("Senate", {
            "TX": {}, "FL-SPECIAL": {}, "FL": {}, "OH-EXTRA": {},
        }), "Senate"))
        self.assertEqual(audit.tracked, 35)
        self.assertEqual(audit.published, 4)
        self.assertEqual(audit.matched, 2)
        self.assertEqual(audit.unmatched, 2)
        self.assertEqual(audit.unmatched_examples, ("FL", "OH-EXTRA"))
        self.assertIn("review source-to-registry mapping", audit.detail)
        self.assertIn("identifiers do not prove votes", audit.detail)

    def test_provider_keys_are_sanitized_for_markdown(self):
        audit = audit_feed_keys(parse_feed(fixture(races={
            "x|injected\nrow": {}, "AZ-01": {},
        }), "House"))
        self.assertEqual(audit.matched, 1)
        self.assertEqual(audit.unmatched, 1)
        self.assertEqual(audit.unmatched_examples, ("X?INJECTED?ROW",))
        self.assertNotIn("|injected", audit.detail)
        self.assertNotIn("\n", audit.detail)

    def test_diagnostic_samples_are_bounded(self):
        races = {f"UNKNOWN-{i:02d}": {} for i in range(20)}
        audit = audit_feed_keys(parse_feed(fixture(races=races), "House"))
        self.assertEqual(audit.unmatched, 20)
        self.assertEqual(len(audit.unmatched_examples), 5)

    def test_health_monitor_reports_mismatch_without_failing_valid_feed(self):
        def opener(request, timeout):
            self.assertIn("office=Senate", request.full_url)
            return FakeResponse(fixture("Senate", races={"TX": {}, "FL": {}}))

        check = check_feed("Senate", "https://example.invalid/results", opener)
        self.assertEqual(check.status, "PASS")
        self.assertIn("1/2 published race identifiers match", check.detail)
        self.assertIn("FL", check.detail)
        self.assertNotIn("zero votes", check.detail)

    def test_health_monitor_does_not_invent_coverage_on_empty_feed(self):
        def opener(request, timeout):
            return FakeResponse(fixture())

        check = check_feed("House", "https://example.invalid/results", opener)
        self.assertEqual(check.status, "PASS")
        self.assertIn("0 race identifiers published", check.detail)
        self.assertNotIn("435/435", check.detail)


if __name__ == "__main__":
    unittest.main()
