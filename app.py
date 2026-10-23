"""CivicPulse v3: source-aware, nonpartisan congressional results viewer."""
from __future__ import annotations

import os
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from civicpulse_client import ElectionFeedClient
from civicpulse_core import (PROVIDER_STATES, coverage_status, national_coverage_metrics,
                             normalize_race, refresh_seconds)

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


@st.cache_resource
def get_feed_client() -> ElectionFeedClient:
    """Share the HTTP cache across viewers within one Streamlit server process."""
    return ElectionFeedClient(API_URL)


client = get_feed_client()
force_refresh = st.session_state.pop("force_refresh", False)
house_snapshot = client.fetch("House", force=force_refresh)
senate_snapshot = client.fetch("Senate", force=force_refresh)
snapshots = {"House": house_snapshot, "Senate": senate_snapshot}
house, senate = house_snapshot.feed, senate_snapshot.feed
feeds = [house, senate]
errors = [f"{office}: {snapshot.error}" for office, snapshot in snapshots.items() if snapshot.error]
poll_seconds = refresh_seconds(feeds, failures=1 if errors else 0)

st_autorefresh(interval=poll_seconds * 1000, key="civicpulse_poll")

st.markdown("""<section class="hero"><div class="eyebrow">CivicPulse / public election information</div>
<h1>2026 U.S. Congressional Elections</h1>
<p>Explore 435 House districts and regularly scheduled Senate contests, sourced from published
state returns where available. No forecasts, inferred winners, or fabricated vote totals.</p>
<span class="pill">Election Day · November 3, 2026</span>
<span class="pill">Source-aware refresh</span></section>""", unsafe_allow_html=True)

statuses = [f"{office}: {snapshot.status}" for office, snapshot in snapshots.items()]
with st.sidebar:
    st.header("Explore races")
    chosen_chamber = st.selectbox("Chamber", ["Both", "House", "Senate"])
    chosen_state = st.selectbox("State", ["All states"] + STATES)
    chosen_coverage = st.selectbox("Coverage", ["All", "Results reported", "Listed, no votes yet",
                                               "State not supported by provider",
                                               "Race absent from provider feed", "Source unavailable"])
    search = st.text_input("Find district or candidate", placeholder="e.g. TX-23")
    if st.button("Check source now", use_container_width=True):
        st.session_state["force_refresh"] = True
        st.rerun()
    st.caption(f"Next automatic source check: roughly {poll_seconds // 60} minute(s)")
    st.caption("This is an independent, nonpartisan information service.")

feed_lookup = {"House": house, "Senate": senate}
rows = []
for seat in registry():
    feed = feed_lookup[seat["Chamber"]]
    found = feed.races.get(seat["Seat"]) if feed else None
    snapshot = snapshots[seat["Chamber"]]
    row = normalize_race(seat["Chamber"], seat["State"], seat["Seat"], found,
                         snapshot.status, feed.as_of if feed else None)
    if found is None:
        row["Coverage"] = coverage_status(seat["State"], feed is not None, False)
    rows.append(row)

frame = pd.DataFrame([{k: v for k, v in row.items() if k != "candidates"} for row in rows])
metrics = national_coverage_metrics(rows)
reported = metrics["reported"]
listed = metrics["listed"]
overview, explorer, sources = st.tabs(["Overview", "Race explorer", "Data & methodology"])

with overview:
    a, b, c, d = st.columns(4)
    a.metric("House districts", sum(1 for r in rows if r["Chamber"] == "House"))
    b.metric("Regular Senate contests", len(SENATE_2026))
    c.metric("Races with votes", reported)
    d.metric("Races included in feed", listed)
    st.caption(f"Unsupported-state contests: {metrics['provider_unsupported']} · "
               f"Feed unavailable for {metrics['source_unavailable']} contests")
    st.markdown('<div class="callout">Missing vote counts are not zero. A vote leader is not a winner. '
                'Source precinct completion does not mean certified election results.</div>',
                unsafe_allow_html=True)
    if errors:
        st.warning("A provider request failed. Previously validated results, if available, are retained but may be out of date.")
        with st.expander("Source error details"):
            for message in errors:
                st.code(message)
    for message in statuses:
        st.info(message)
    st.caption(f"Source adapters: {len(PROVIDER_STATES)} states; a state adapter does not guarantee a race has appeared. These are not national vote or seat totals.")
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
    checks = " | ".join(f"{office}: {snapshot.checked_at.strftime('%Y-%m-%d %H:%M UTC')}"
                        for office, snapshot in snapshots.items())
    st.caption(f"{len(filtered):,} matching contests · Last HTTP attempts: {checks}")
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
                   f"Feed as-of (latest update across races): {detail['Feed as-of (UTC)']}")
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
    st.write("**Refresh:** While a feed is live it is checked every 60 seconds; before counting, "
             "every 10 minutes; when counting but not live, every 15 minutes. "
             "Failures use exponential backoff up to 10 minutes. The provider may update less frequently.")
    st.write(f"**Coverage:** The provider documents adapters for {len(PROVIDER_STATES)} states: "
             + ", ".join(sorted(PROVIDER_STATES)) + ". "
             "An unsupported state is different from a supported state whose race has not appeared. "
             "An HTTP failure is not evidence of zero votes or absent coverage.")
    st.write("**HTTP caching:** A process-shared cache sends ETag conditional requests and reuses "
             "validated results on HTTP 304. On errors it retains the last validated snapshot "
             "with a warning and a real check timestamp. Cache is lost when the server restarts.")
    st.write("**Timestamps:** The feed as-of value is the newest state update anywhere in that office feed, "
             "not necessarily the update time of the selected race.")
    st.write("**Election scope:** 435 House districts and 33 regularly scheduled Senate contests; "
             "special elections require separate integration.")
    st.write("**Certification:** Reporting 100% of precincts is not legal certification. "
             "Verify authoritative results with [USA.gov](https://www.usa.gov/election-results) "
             "and the responsible state election office.")
    st.caption("No predictions or inferred winners · Independent civic information · Open source")
