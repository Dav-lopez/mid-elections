"""Timestamp presentation must not mislabel provider timezone offsets."""
import unittest

from civicpulse_core import format_feed_timestamp


class TimestampTests(unittest.TestCase):
    def test_utc_z(self):
        self.assertEqual(format_feed_timestamp("2026-11-04T01:02:00Z"), "2026-11-04 01:02 UTC")

    def test_non_utc_provider_offset_converted(self):
        self.assertEqual(format_feed_timestamp("2026-11-03T20:02:00-05:00"), "2026-11-04 01:02 UTC")

    def test_missing_timestamp_explicit(self):
        self.assertEqual(format_feed_timestamp(None), "Not published")

    def test_timezone_naive_is_not_labeled_utc(self):
        self.assertIn("timezone unspecified", format_feed_timestamp("2026-11-03T20:02:00"))

    def test_invalid_timestamp_is_not_displayed_as_real_time(self):
        self.assertEqual(format_feed_timestamp("not a time"), "Invalid timestamp")


if __name__ == "__main__":
    unittest.main()
