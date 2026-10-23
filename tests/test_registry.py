import unittest
from civicpulse_registry import HOUSE, SENATE_2026, SENATE_SPECIAL_2026, registry


class RegistryTests(unittest.TestCase):
    def test_complete_unique_contests(self):
        rows = registry()
        self.assertEqual(sum(r["Chamber"] == "House" for r in rows), 435)
        self.assertEqual(sum(r["Chamber"] == "Senate" for r in rows), 35)
        keys = [(r["Chamber"], r["Seat"]) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_senate_specials_are_separate(self):
        rows = registry()
        specials = [r for r in rows if r["Election"] == "Special"]
        self.assertEqual({r["Seat"] for r in specials}, {"FL-SPECIAL", "OH-SPECIAL"})
        self.assertEqual({r["State"] for r in specials}, {"FL", "OH"})
        self.assertEqual(len(SENATE_2026), 33)
        self.assertEqual(len(SENATE_SPECIAL_2026), 2)
        self.assertNotIn("FL", SENATE_2026)
        self.assertNotIn("OH", SENATE_2026)

    def test_at_large_seats(self):
        rows = registry()
        house = [r["Seat"] for r in rows if r["Chamber"] == "House"]
        self.assertIn("AK-00", house)
        self.assertIn("WY-00", house)
        self.assertEqual(sum(HOUSE.values()), 435)


if __name__ == "__main__":
    unittest.main()
