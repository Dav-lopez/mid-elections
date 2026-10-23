from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="CivicPulse | 2026 Elections", page_icon="🗳️", layout="wide")
REFRESH_SECONDS = 60
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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
html,body,[data-testid="stApp"] {font-family: 'DM Sans',sans-serif;}
.stApp {background:#f5f8fc;}
.block-container {max-width:1440px;padding-top:1.3rem;}
h1,h2,h3 {font-family:'Manrope',sans-serif;letter-spacing:-.035em;color:#14233b;}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid #e5ebf3;}
[data-testid="stMetric"] {background:#fff;border:1px solid #e0e8f1;border-radius:17px;padding:18px;box-shadow:0 4px 20px #14233b08;}
[data-testid="stMetricValue"] {font-family:'Manrope',sans-serif;color:#14233b;}
.hero {background:linear-gradient(115deg,#14233b,#1e436d 58%,#12676d);border-radius:22px;padding:32px;color:white;margin-bottom:25px;box-shadow:0 14px 32px #1d3d6622;}
.hero .eyebrow {letter-spacing:.16em;text-transform:uppercase;font-size:.76rem;color:#b0d4e1;font-weight:700;}
.hero h1 {color:white;font-size:clamp(1.8rem,3vw,2.75rem);margin:.4rem 0;}
.hero p {color:#e6edf8;max-width:780px;line-height:1.6;margin:0;}
.pill {display:inline-block;margin-top:18px;padding:7px 11px;border-radius:100px;border:1px solid #ffffff55;color:#ecf5ff;font-size:.82rem;}
.note {border-left:3px solid #176d78;padding:10px 14px;background:#eef5f8;border-radius:0 8px 8px 0;color:#344b62;font-size:.9rem;}
a {color:#176d78;}
@media(max-width:720px){.block-container{padding:1rem .7rem}.hero{padding:22px 18px}}
</style>
""", unsafe_allow_html=True)


def num(v: Any) -> int | None:
    try:
        return None if v is None else int(v)
    except (ValueError, TypeError):
        return None


def pct(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (ValueError, TypeError):
        return None


def registry() -> list[dict[str, Any]]:
    rows = []
    for state, count in HOUSE.items():
        for i in range(1, count + 1):
            seat = f"{state}-{i:02d}" if count > 1 else f"{state}-00"
            rows.append({"chamber": "House", "state": state, "seat": seat})
    for state in SENATE_2026:
        rows.append({"chamber": "Senate", "state": state, "seat": state})
    return rows


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def fetch(chamber: str) -> tuple[dict[str, dict], str | None, str]:
    try:
        response = requests.get(API_URL, params={"year": 2026, "office": chamber},
                                timeout=(5, 15), headers={"Accept": "application/json",
                                "User-Agent": "CivicPulseElectionDashboard/1.0"})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected response type")
        races = payload.get("races", {})
        if not isinstance(races, dict):
            raise ValueError("Unexpected races schema")
        return {str(k).upper(): v for k, v in races.items() if isinstance(v, dict)}, str(payload.get("as_of") or ""), ""
    except (requests.RequestException, ValueError) as error:
        return {}, None, str(error)


def normalize(seat: dict, source: dict | None, as_of: str | None) -> dict:
    basic = dict(seat)
    basic.update({"coverage": "No source coverage", "reporting": None,
                  "votes": None, "leader": "—", "called": False,
                  "winner": "—", "updated": as_of or "—", "candidates": []})
    if source is None:
        return basic
    cands = source.get("cands", [])
    if not isinstance(cands, list):
        cands = []
    candidates = []
    for c in cands:
        if isinstance(c, dict):
            candidates.append({"Candidate": str(c.get("n") or "Unspecified"),
                               "Party": str(c.get("p") or "—"),
                               "Votes": num(c.get("v")),
                               "Percent": pct(c.get("pct"))})
    candidates.sort(key=lambda c: c["Votes"] or 0, reverse=True)
    total = num(source.get("total"))
    if total is None and any(c["Votes"] is not None for c in candidates):
        total = sum(c["Votes"] or 0 for c in candidates)
    leader = str(source.get("leader") or "")
    winner = str(source.get("winner") or "")
    called = bool(source.get("called", False))
    basic.update({"coverage": "Reported" if total is not None else "Feed listed; awaiting votes",
                  "reporting": pct(source.get("pct_in")),
                  "votes": total, "leader": leader or "—",
                  "called": called, "winner": winner if called and winner else "—",
                  "candidates": candidates})
    return basic


st_autorefresh(interval=REFRESH_SECONDS * 1000, key="civicpulse_refresh")
st.markdown("""<div class="hero"><div class="eyebrow">CivicPulse · Nonpartisan election coverage</div>
<h1>2026 Congressional Elections</h1>
<p>Explore U.S. House and Senate races, reported vote totals, and the availability of source data.
Updates reflect the publisher's schedule—not an instant official certification.</p>
<span class="pill">Tuesday, November 3, 2026</span> &nbsp;
<span class="pill">Automatically checks every 60 seconds</span></div>""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Explore")
    chamber_filter = st.selectbox("Chamber", ["Both", "House", "Senate"])
    state_filter = st.selectbox("State", ["All states"] + STATES)
    coverage_filter = st.selectbox("Feed status", ["All", "Reported", "Awaiting results", "No source coverage"])
    search = st.text_input("Find a seat or candidate", placeholder="e.g., CA-12 or name")
    if st.button("Refresh source data", use_container_width=True):
        fetch.clear()
        st.rerun()
    st.caption("Unofficial returns. This dashboard is not a government election authority.")

house, house_at, house_error = fetch("House")
senate, senate_at, senate_error = fetch("Senate")
rows = []
for seat in registry():
    source = (house if seat["chamber"] == "House" else senate).get(seat["seat"])
    # Alternate statewide Senate key formats may be provided by the source.
    rows.append(normalize(seat, source, house_at if seat["chamber"] == "House" else senate_at))
frame = pd.DataFrame([{k: v for k, v in row.items() if k != "candidates"} for row in rows])
reported = int(frame["coverage"].eq("Reported").sum())
listed = int(frame["coverage"].ne("No source coverage").sum())
a, b, c, d = st.columns(4)
a.metric("House districts", len([r for r in rows if r["chamber"] == "House"]))
b.metric("Regular Senate races", len(SENATE_2026))
c.metric("Races with vote totals", reported)
d.metric("Races in provider feed", listed)
st.markdown('<div class="note">Coverage is limited to participating states. A race without source data is not a zero-vote race. A leading candidate is not necessarily a winner.</div>', unsafe_allow_html=True)
if house_error or senate_error:
    st.warning("One or more live feeds could not be retrieved. Registry remains available. " +
               " | ".join(x for x in [house_error, senate_error] if x))
left, right = st.columns([3, 1])
with left:
    st.subheader("Race explorer")
with right:
    st.caption(f"Last checked: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
if chamber_filter != "Both":
    frame = frame[frame["chamber"] == chamber_filter]
if state_filter != "All states":
    frame = frame[frame["state"] == state_filter]
if coverage_filter == "Awaiting results":
    frame = frame[frame["coverage"] == "Feed listed; awaiting votes"]
elif coverage_filter != "All":
    frame = frame[frame["coverage"] == coverage_filter]
if search:
    matched_seats = [r["seat"] for r in rows
                     if search.lower() in r["seat"].lower() or
                     any(search.lower() in str(c["Candidate"]).lower() for c in r["candidates"])]
    frame = frame[frame["seat"].isin(matched_seats)]
display = frame.rename(columns={"chamber": "Chamber", "state": "State", "seat": "Seat",
                                "coverage": "Feed status", "votes": "Votes",
                                "reporting": "Precincts reported (%)", "leader": "Leader party",
                                "called": "Called by source", "winner": "Source winner", "updated": "Source as-of"})
st.dataframe(display, use_container_width=True, hide_index=True,
             column_config={"Votes": st.column_config.NumberColumn(format="%d")})
st.download_button("Download filtered results (CSV)", display.to_csv(index=False).encode("utf-8"),
                   file_name="civicpulse_2026_results.csv", mime="text/csv")
seats = frame["seat"].tolist()
if seats:
    selected = st.selectbox("Inspect race", seats)
    row = next(r for r in rows if r["seat"] == selected and (chamber_filter == "Both" or r["chamber"] == chamber_filter))
    st.subheader(selected + " · " + row["chamber"])
    st.caption(f"Feed status: {row['coverage']} | Source as-of: {row['updated']}")
    if row["candidates"]:
        st.dataframe(pd.DataFrame(row["candidates"]), hide_index=True, use_container_width=True)
    else:
        st.info("The provider has not published candidate vote details for this race.")
st.markdown("### Sources and methodology")
st.markdown("Election result data: [Open America election feed](https://openamerica.io/elections/api/). "
            "House districts use 2020 census apportionment; Senate registry covers the 33 regularly scheduled seats. "
            "The feed covers participating states only. Special elections, if any, require a separate audited registry. "
            "Check [USA.gov's election resources](https://www.usa.gov/election-results) and individual state election offices for authoritative information.")
st.caption("CivicPulse · Nonpartisan civic information · No predictions or inferred winners")
