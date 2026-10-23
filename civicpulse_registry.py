"""Officially scheduled 2026 congressional election seat registry.

Special Senate seats are distinct from regular Senate contests.
The provider is only documented to serve these results where a state adapter exists.
"""
HOUSE = {
    "AL": 7, "AK": 1, "AZ": 9, "AR": 4, "CA": 52, "CO": 8, "CT": 5, "DE": 1,
    "FL": 28, "GA": 14, "HI": 2, "ID": 2, "IL": 17, "IN": 9, "IA": 4, "KS": 4,
    "KY": 6, "LA": 6, "ME": 2, "MD": 8, "MA": 9, "MI": 13, "MN": 8, "MS": 4,
    "MO": 8, "MT": 2, "NE": 3, "NV": 4, "NH": 2, "NJ": 12, "NM": 3, "NY": 26,
    "NC": 14, "ND": 1, "OH": 15, "OK": 5, "OR": 6, "PA": 17, "RI": 2, "SC": 7,
    "SD": 1, "TN": 9, "TX": 38, "UT": 4, "VT": 1, "VA": 11, "WA": 10, "WV": 2,
    "WI": 8, "WY": 1,
}
SENATE_2026 = "AL AK AR CO DE GA ID IL IA KS KY LA ME MA MI MN MS MT NE NH NJ NM NC OK OR RI SC SD TN TX VA WV WY".split()
SENATE_SPECIAL_2026 = {"FL": "FL-SPECIAL", "OH": "OH-SPECIAL"}


def registry() -> list[dict]:
    entries = []
    for state, count in HOUSE.items():
        for district in range(1, count + 1):
            seat = f"{state}-{district:02d}" if count > 1 else f"{state}-00"
            entries.append({"Chamber": "House", "State": state, "Seat": seat, "Election": "Regular"})
    for state in SENATE_2026:
        entries.append({"Chamber": "Senate", "State": state, "Seat": state, "Election": "Regular"})
    for state, key in SENATE_SPECIAL_2026.items():
        entries.append({"Chamber": "Senate", "State": state, "Seat": key, "Election": "Special"})
    return entries


STATES = sorted(HOUSE)
