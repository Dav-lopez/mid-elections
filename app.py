"""CivicPulse v3: source-aware, nonpartisan congressional results viewer."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from civicpulse_core import FeedValidationError, normalize_race, parse_feed, refresh_seconds

st.set_page_config(page_title="CivicPulse | Election Results", page_icon="🗳️", layout="wide",
                   initial_sidebar_state="expanded")

API_URL = os.getenv("ELECTION_RESULTS_URL", "https://openamerica.io/elections/results.json")
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
STATES = sorted(HOUSE)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
html,body,[data-testid="stApp"] {font-family:'DM Sans',sans-serif}
.stApp {background:#f5f8fc}
.block-container {max-width:1430px;padding-top:1rem}
h1,h2,h3 {font-family:'Manrope',sans-serif;letter-spacing:-.035em}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid #e5ebf3}
[data-testid="stMetric"] {background:#fff;border:1px solid #e0e8f1;border-radius:16px;padding:17px;box-shadow:0 4px 20px #14233b08}
[data-testid="stMetricValue"] {color:#14233b;font-family:'Manrope',sans-serif}
.hero {background:linear-gradient(115deg,#14233b,#1e436d 58%,#12676d);
border-radius:22px;padding:30px;color:white;margin-bottom:22px;box-shadow:0 14px 32px #1d3d6622}
.hero .eyebrow {letter-spacing:.15em;text-transform:uppercase;color:#b0d4e1;font-size:.76rem;font-weight:700}
.hero h1 {color:white;font-size:clamp(1.8rem,3vw,2.8rem);margin:.5rem 0}
.hero p {color:#e6edf8;max-width:860px;margin:0;line-height:1.65}
.pill {display:inline-block;border:1px solid #ffffff50;border-radius:100px;padding:6px 12px;
font-size:.81rem;margin-top:17px;color:#eaf7fe}
.callout {background:#eaf2f6;color:#304760;border-left:4px solid #176d78;border-radius:0 10px 10px 0;
padding:14px 17px;margin:14px 0}
@media(max-width:720px){.block-container{padding:1rem .55rem}.hero{padding:22px 18px}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def registry() -> list[dict]:
    entries = []
    for state, count in HOUSE.items():
        for district in range(1, count + 1):
            seat = f"{state}-{district:02d}" if count > 1 else f"{state}-00"
            entries.append({"Chamber": "House", "State": state, "Seat": seat})
    for state in SENATE_2026:
        entries.append({"Chamber": "Senate", "State": state, "Seat": state})
    return entries


@st.cache_data(ttl=60, show_spinner=False)
def fetch_feed(chamber: str):
    try:
        result = requests.get(API_URL, params={"year": 2026, "office": chamber},
                              timeout=(5, 15), headers={"Accept": "application/json",
                              "Accept-Encoding": "gzip", "User-Agent": "CivicPulse/3.0 (election viewer)"})
        result.raise_for_status()
        return parse_feed(result.json(), chamber), None
    except (requests.RequestException, ValueError, FeedValidationError) as exc:
        return None, str(exc)


house, house_error = fetch_feed("House")
senate, senate_error = fetch_feed("Senate")
feeds = [house, senate]
errors = [message for message in [house_error, senate_error] if message]
poll_seconds = refresh_seconds(feeds, failures=1 if errors else 0)
st_autorefresh(interval=poll_seconds * 1000, key="civicpulse_poll")

st.markdown("""<section class="hero"><div class="eyebrow">CivicPulse / public election information</div>
<h1>2026 U.S. Congressional Elections</h1>
<p>Explore 435 House districts and regularly scheduled Senate contests, sourced from published
state returns where available. No forecasts, inferred winners, or fabricated vote totals.</p>
<span class="pill">Election Day · November 3, 2026</span>
<span class="pill">Source-aware refresh</span></section>""", unsafe_allow_html=True)

statuses = [f"{feed.office}: {feed.status}" if feed else
            f"{office}: Source unavailable" for office, feed in [("House", house), ("Senate", senate)]]
with st.sidebar:
    st.header("Explore races")
    chosen_chamber = st.selectbox("Chamber", ["Both", "House", "Senate"])
    chosen_state = st.selectbox("State", ["All states"] + STATES)
    chosen_coverage = st.selectbox("Coverage", ["All", "Results reported", "Listed, no votes yet",
                                               "Not available from this provider"])
    search = st.text_input("Find district or candidate", placeholder="e.g. TX-23")
    if st.button("Check source now", use_container_width=True):
        fetch_feed.clear()
        st.rerun()
    st.caption(f"Next automatic source check: roughly {poll_seconds // 60} minute(s)")
    st.caption("This is an independent, nonpartisan information service.")

feed_lookup = {"House": house, "Senate": senate}
rows = []
for seat in registry():
    feed = feed_lookup[seat["Chamber"]]
    found = feed.races.get(seat["Seat"]) if feed else None
    health = feed.status if feed else "Feed unavailable"
    rows.append(normalize_race(seat["Chamber"], seat["State"], seat["Seat"], found,
                               health, feed.as_of if feed else None))

frame = pd.DataFrame([{k: v for k, v in row.items() if k != "candidates"} for row in rows])
reported = int((frame["Coverage"] == "Results reported").sum())
listed = int((frame["Coverage"] != "Not available from this provider").sum())
overview, explorer, sources = st.tabs(["Overview", "Race explorer", "Data & methodology"])

with overview:
    a, b, c, d = st.columns(4)
    a.metric("House districts", sum(1 for r in rows if r["Chamber"] == "House"))
    b.metric("Regular Senate contests", len(SENATE_2026))
    c.metric("Races with votes", reported)
    d.metric("Races included in feed", listed)
    st.markdown('<div class="callout">Missing vote counts are not zero. A vote leader is not a winner. '
                'Source precinct completion does not mean certified election results.</div>',
                unsafe_allow_html=True)
    if errors:
        st.error("One or more source requests failed. Source coverage cannot be assessed reliably until they recover.")
        with st.expander("Source error details"):
            for message in errors:
                st.code(message)
    for message in statuses:
        st.info(message)
    st.caption("Numbers reflect this provider's limited coverage; these are not national vote or seat totals.")
    source_update = [f"{feed.office}: {feed.as_of or 'Not yet published'}"
                     for feed in feeds if feed is not None]
    if source_update:
        st.write("**Publisher timestamps:** " + " | ".join(source_update))

with explorer:
    filtered = frame
    if chosen_chamber != "Both":
        filtered = filtered[filtered["Chamber"] == chosen_chamber]
    if chosen_state != "All states":
        filtered = filtered[filtered["State"] == chosen_state]
    if chosen_coverage != "All":
        filtered = filtered[filtered["Coverage"] == chosen_coverage]
    if search.strip():
        needle = search.strip().casefold()
        seats = {r["Seat"] for r in rows if needle in r["Seat"].casefold() or
                 any(needle in candidate["Candidate"].casefold() for candidate in r["candidates"])}
        filtered = filtered[filtered["Seat"].isin(seats)]
    st.subheader("Find a race")
    st.caption(f"{len(filtered):,} matching contests · Last app check: "
               f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    st.dataframe(filtered, hide_index=True, use_container_width=True,
                 column_config={"Votes": st.column_config.NumberColumn(format="%d"),
                                "Precincts (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%")})
    st.download_button("Download filtered CSV", filtered.to_csv(index=False).encode("utf-8"),
                       file_name="civicpulse_2026_filtered.csv", mime="text/csv")
    if not filtered.empty:
        choices = [(r["Chamber"], r["Seat"]) for r in rows if
                   ((filtered["Chamber"] == r["Chamber"]) & (filtered["Seat"] == r["Seat"])).any()]
        selection = st.selectbox("Race details", choices,
                                format_func=lambda item: f"{item[0]} · {item[1]}")
        detail = next(r for r in rows if (r["Chamber"], r["Seat"]) == selection)
        st.subheader(f"{detail['Chamber']} · {detail['Seat']}")
        st.caption(f"{detail['Coverage']} · {detail['Feed health']} · "
                   f"Publisher timestamp: {detail['Source timestamp']}")
        if detail["candidates"]:
            candidates = pd.DataFrame(detail["candidates"])
            st.dataframe(candidates, hide_index=True, use_container_width=True)
            votes = candidates.dropna(subset=["Votes"])
            if not votes.empty and votes["Votes"].sum() > 0:
                st.bar_chart(votes.set_index("Candidate")["Votes"], horizontal=True)
        else:
            st.info("This provider has no candidate vote breakdown for the selected race.")

with sources:
    st.subheader("Transparency and source status")
    st.write("**Provider:** [Open America election results](https://openamerica.io/elections/api/). "
             "The feed integrates official returns from participating states and does not call races.")
    st.write("**Refresh:** The site checks every 60 seconds when any feed is live, "
             "every 10 minutes before counting, and every 15 minutes when counting is no longer live. "
             "Failures trigger a slower retry. The provider may update less frequently.")
    st.write("**Coverage:** Not all 50 states provide compatible public feeds. "
             "Unlisted races are explicitly labeled unavailable from this provider. "
             "An unavailable feed is treated as an error, not as proof no race was reported.")
    st.write("**Election scope:** 435 House districts and 33 regularly scheduled Senate contests; "
             "special elections require separate integration.")
    st.write("**Certification:** Reporting 100% of precincts is not legal certification. "
             "Verify authoritative results with [USA.gov](https://www.usa.gov/election-results) "
             "and the responsible state election office.")
    st.caption("No predictions or inferred winners · Independent civic information · Open source")
