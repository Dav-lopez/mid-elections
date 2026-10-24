"""Race detail selection must preserve chamber-qualified keys and source data."""
import unittest
import pandas as pd


def choices_and_index(rows, filtered):
    index = {(r["Chamber"], r["Seat"]): r for r in rows}
    choices = list(filtered[["Chamber", "Seat"]].itertuples(index=False, name=None))
    return choices, index


class RaceDetailIndexTests(unittest.TestCase):
    def test_filtered_order_and_chamber_qualified_keys(self):
        rows = [
            {"Chamber": "House", "Seat": "OH-01", "Votes": None},
            {"Chamber": "Senate", "Seat": "OH-01", "Votes": 120},
            {"Chamber": "House", "Seat": "TX-23", "Votes": None},
        ]
        frame = pd.DataFrame([{k: v for k, v in r.items()} for r in rows])
        choices, index = choices_and_index(rows, frame.iloc[[2, 0]])
        self.assertEqual(choices, [("House", "TX-23"), ("House", "OH-01")])
        self.assertIsNone(index[choices[0]]["Votes"])
        self.assertEqual(index[("Senate", "OH-01")]["Votes"], 120)

    def test_empty_filter_has_no_choices(self):
        rows = [{"Chamber": "House", "Seat": "TX-23", "Votes": None}]
        frame = pd.DataFrame(rows)
        choices, index = choices_and_index(rows, frame.iloc[0:0])
        self.assertEqual(choices, [])
        self.assertEqual(len(index), 1)


if __name__ == "__main__":
    unittest.main()
