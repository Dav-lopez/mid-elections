"""CivicPulse: source-aware, nonpartisan congressional results viewer."""
from __future__ import annotations

import os
from datetime import datetime, timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from civicpulse_client import ElectionFeedClient
from civicpulse_disk_cache import DiskFeedCache
from civicpulse_polling import fetch_offices
from civicpulse_map import STATUS_LABELS, STATUS_COLORS, state_coverage
from civicpulse_explorer import candidate_vote_rows, state_contests
from civicpulse_registry import HOUSE, SENATE_2026, SENATE_SPECIAL_2026, STATES, registry
from civicpulse_core import (PROVIDER_STATES, coverage_status, national_coverage_metrics,
                             normalize_race, refresh_seconds, format_feed_timestamp)

st.set_page_config(page_title="CivicPulse | Election Results", page_icon="🗳️", layout="wide",
                   initial_sidebar_state="expanded")

API_URL = os.getenv("ELECTION_RESULTS_URL", "https://openamerica.io/elections/results.json")

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



@st.cache_resource
def get_feed_client() -> ElectionFeedClient:
    """Share the HTTP cache across viewers within one Streamlit server process."""
    return ElectionFeedClient(API_URL, disk_cache=DiskFeedCache(
        os.getenv('CIVICPULSE_CACHE_DIR', '.civicpulse-cache'), API_URL))


client = get_feed_client()
force_refresh = st.session_state.pop("force_refresh", False)
snapshots = fetch_offices(client, force=force_refresh)
house, senate = snapshots["House"].feed, snapshots["Senate"].feed
feeds = [house, senate]
errors = [f"{office}: {snapshot.error}" for office, snapshot in snapshots.items() if snapshot.error]
poll_seconds = refresh_seconds(feeds, failures=1 if errors else 0)

st_autorefresh(interval=poll_seconds * 1000, key="civicpulse_poll")

st.markdown("""<section class="hero"><div class="eyebrow">CivicPulse / public election information</div>
<h1>2026 U.S. Congressional Elections</h1>
<p>Explore 435 House districts and 35 Senate contests (33 regular, 2 special), sourced from published
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
    row["Election"] = seat["Election"]
    row["Feed as-of (UTC)"] = format_feed_timestamp(feed.as_of if feed else None)
    if found is None:
        row["Coverage"] = coverage_status(seat["State"], feed is not None, False)
    rows.append(row)

frame = pd.DataFrame([{k: v for k, v in row.items() if k != "candidates"} for row in rows])
metrics = national_coverage_metrics(rows)
reported = metrics["reported"]
listed = metrics["listed"]
overview, explorer, sources = st.tabs(["Overview & map", "Race explorer", "Data & methodology"])

with overview:
    a, b, c, d = st.columns(4)
    a.metric("House districts", sum(1 for r in rows if r["Chamber"] == "House"))
    b.metric("Senate contests (incl. special)", len(SENATE_2026) + len(SENATE_SPECIAL_2026))
    c.metric("Races with votes", reported)
    d.metric("Races included in feed", listed)
    st.subheader("U.S. results-data availability map")
    st.caption("This map shows the availability of source data — **not** partisan control, predicted winners, or certified results.")
    map_data = state_coverage(rows, {office for office, snapshot in snapshots.items() if snapshot.error})
    map_frame = pd.DataFrame(map_data)
    legend = {label: idx for idx, label in enumerate(STATUS_LABELS)}
    fig = go.Figure()
    for label, color in zip(STATUS_LABELS, STATUS_COLORS):
        selection = map_frame[map_frame["Status"] == label]
        if selection.empty:
            continue
        hover = selection.apply(
            lambda r: (f'{r["State"]} — {r["Status"]}'
                       f'<br>Tracked contests: {r["Contests tracked"]}'
                       f'<br>Listed in source: {r["Races listed"]}'
                       f'<br>With votes: {r["Races with votes"]}'
                       + ('<br>Source warning: office feed unavailable' if r["Partial outage"] else '')),
            axis=1,
        ).tolist()
        fig.add_trace(go.Choropleth(
            locations=selection["State"], locationmode="USA-states", z=[1] * len(selection),
            colorscale=[[0, color], [1, color]], showscale=False, name=label,
            showlegend=True, customdata=hover, hovertemplate="%{customdata}<extra></extra>",
            marker_line_color="white", marker_line_width=1.1,
        ))
    fig.update_geos(scope="usa", bgcolor="rgba(0,0,0,0)", showlakes=False,
                    showland=True, landcolor="#E5E9EF")
    fig.update_layout(height=480, margin=dict(l=0, r=0, t=12, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", legend_title_text="Coverage status",
                      legend=dict(orientation="h", y=-0.05, x=0, font=dict(size=11)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with st.expander("Accessible state-by-state coverage table"):
        st.dataframe(map_frame, hide_index=True, use_container_width=True)
        st.download_button("Download state coverage CSV", map_frame.to_csv(index=False).encode("utf-8"),
                           file_name="civicpulse_state_coverage.csv", mime="text/csv")
    st.subheader("State spotlight")
    st.caption("Select a state to inspect its tracked races. This keyboard-accessible selector also works when the map is difficult to use on mobile.")
    spotlight_state = st.selectbox("Inspect state", ["Choose a state"] + STATES, key="spotlight_state")
    if spotlight_state != "Choose a state":
        spotlight_chamber = st.radio("Show contests", ["Both", "House", "Senate"],
                                    horizontal=True, key="spotlight_chamber")
        spotlight_rows = state_contests(rows, spotlight_state, spotlight_chamber)
        summary = next(item for item in map_data if item["State"] == spotlight_state)
        st.caption(f'{spotlight_state} · {summary["Status"]} · '
                   f'{summary["Races listed"]} source-listed contests · '
                   f'{summary["Races with votes"]} with votes')
        if not spotlight_rows:
            st.info("No tracked contests match this chamber and state.")
        else:
            spotlight_table = pd.DataFrame([
                {name: item.get(name) for name in
                 ("Chamber", "Seat", "Election", "Coverage", "Votes", "Leader (not winner)", "Source call")}
                for item in spotlight_rows
            ])
            st.dataframe(spotlight_table, hide_index=True, use_container_width=True)
            selected_key = st.selectbox(
                "Inspect a race", [(item["Chamber"], item["Seat"]) for item in spotlight_rows],
                format_func=lambda key: f"{key[0]} · {key[1]}",
                key=f"spotlight_race_{spotlight_state}_{spotlight_chamber}",
            )
            selected_race = next(item for item in spotlight_rows
                                 if (item["Chamber"], item["Seat"]) == selected_key)
            st.caption(f'{selected_race["Coverage"]} · {selected_race["Feed health"]}')
            vote_rows = candidate_vote_rows(selected_race)
            if vote_rows:
                vote_frame = pd.DataFrame(vote_rows)
                st.dataframe(vote_frame, hide_index=True, use_container_width=True)
                if any(candidate["Votes"] > 0 for candidate in vote_rows):
                    st.bar_chart(vote_frame.set_index("Candidate")["Votes"], horizontal=True)
                else:
                    st.info("Candidate entries are listed, but no votes have been reported yet.")
            else:
                st.info("No candidate vote breakdown is available from this provider for this race.")
    st.caption("Senate scope: 33 regular elections + Florida and Ohio specials.")
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
    for office, snapshot in snapshots.items():
        if snapshot.last_success_at is None:
            st.caption(f"{office}: No successful source check yet")
        else:
            checked = snapshot.last_success_at.astimezone(timezone.utc)
            age = max(0, int((datetime.now(timezone.utc) - checked).total_seconds() // 60))
            st.caption(f"{office}: Last successful check {checked:%H:%M UTC} ({age} min ago)")
    st.caption(f"Source adapters: {len(PROVIDER_STATES)} states; a state adapter does not guarantee a race has appeared. These are not national vote or seat totals.")
    source_update = [f"{feed.office}: {format_feed_timestamp(feed.as_of)}"
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
    st.caption("Votes shows only a provider-published race total. If the source lists candidate votes but no race total, Votes stays blank; candidate details remain available.")
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
    st.write("**State spotlight:** The selector below the map exposes each state's tracked races and published candidate votes without requiring map interaction. Missing votes are never shown as zero.")
    st.write(f"**Coverage:** The provider documents adapters for {len(PROVIDER_STATES)} states: "
             + ", ".join(sorted(PROVIDER_STATES)) + ". "
             "An unsupported state is different from a supported state whose race has not appeared. "
             "An HTTP failure is not evidence of zero votes or absent coverage.")
    st.write("**HTTP caching:** A process-shared cache sends ETag conditional requests and reuses "
             "validated results on HTTP 304. On errors it retains the last validated snapshot "
             "with a warning and a real check timestamp. A validated local disk snapshot can " 
             "be recovered after a process restart if its filesystem persists and it is " 
             "at most 72 hours old; it is never treated as freshly verified until rechecked. " 
             "Cloud redeploys or instance replacement may discard the local cache.")
    st.write("**Vote totals:** The race-wide Votes column is populated only when the provider publishes a valid race total. Candidate vote counts can establish that reporting has begun, but CivicPulse never sums a potentially partial candidate list to invent a race total.")
    st.write("**Timestamps:** The feed as-of value is the newest state update anywhere in that office feed, "
             "not necessarily the update time of the selected race.")
    st.write("**Election scope:** 435 House districts, 33 regular Senate contests, and two Senate specials (FL, OH). "
             "The special seats have distinct keys; inclusion in the registry does not guarantee source coverage.")
    st.write("**Certification:** Reporting 100% of precincts is not legal certification. "
             "Verify authoritative results with [USA.gov](https://www.usa.gov/election-results) "
             "and the responsible state election office.")
    st.caption("No predictions or inferred winners · Independent civic information · Open source")
