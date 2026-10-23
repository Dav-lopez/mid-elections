# CivicPulse — 2026 U.S. Congressional Elections

A nonpartisan Streamlit results viewer with filters, race details, candidate comparisons and CSV export. This is a **partial-coverage election results viewer**, not a nationwide results authority.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Connect this repository to [Streamlit Community Cloud](https://share.streamlit.io), select the `main` branch and `app.py` entrypoint, and deploy. Verify the public URL, the network feed, and the mobile layout before sharing widely.

## Feed contract and coverage

- Provider: [Open America election results API](https://openamerica.io/elections/api/), version 1. Results originate with participating official state election offices, are **unofficial**, and do **not** constitute race calls or certified winners.
- As documented on **2026-09-27**, the provider has adapters for **22 states**: AR, AZ, CO, CT, FL, GA, IA, ID, IN, LA, MI, MN, NC, PA, RI, SC, TX, UT, VA, VT, WA, WV. This is not a promise that every race in those states is listed or reporting.
- The app displays all 435 House districts and 33 **regularly scheduled** Senate contests. Special elections are not currently included in the registry. No source results are inferred for districts absent from the feed.
- Race statuses distinguish **state not supported by provider**, **race absent from provider feed**, **source unavailable**, **listed without votes**, and **results reported**.
- Candidate search requires candidate data to have appeared in the feed. No pre-election roster is supplied by this API.
- The publisher's **`as_of` timestamp** is the newest update *anywhere in that office's feed*, not a per-race timestamp. The UI also displays the last actual HTTP attempt time.

## HTTP resilience

The `ElectionFeedClient` uses one shared in-memory cache per server process for House and Senate. It sends `If-None-Match` when an ETag exists and reuses the validated payload on HTTP 304. The polling cadence is 60 seconds while live, 10 minutes before results, 15 minutes when counting is not live, and exponential backoff (up to 10 minutes) after request failures.

A network failure or schema mismatch **does not erase the last validated feed**. The app visibly marks it as cached and not verified fresh; it never treats missing votes as zero. This cache is **not durable**: it is lost on server restart or when the process is replaced. Scaling across multiple app instances would require an external shared cache.

## Testing

```bash
python -m compileall -q app.py civicpulse_core.py civicpulse_client.py
python -m unittest discover -s tests -v
```

GitHub Actions runs these checks on pushes and PRs. They use deterministic mocked HTTP responses, including 304, 503, malformed payloads, timeouts, and recovery. They do **not** prove that the live provider endpoint is reachable or that a production Streamlit deployment is healthy. For optional integration testing, the provider documents `?year=2024&office=House` as a replay dataset.

## Limitations and responsible use

Open America is not a full national election results service. State feed terms vary; attribute displayed results to **"official state election offices via Open America (openamerica.io)"** and preserve timestamps. Contact the provider before repackaging its live feed as a standalone results service. No election forecasts, inferred calls, or winners are created by this application. Reporting 100% of precincts is **not** certification.

For authoritative information, see [USA.gov's election results guide](https://www.usa.gov/election-results) and the relevant state election office. Future work includes source reconciliation, election-night load tests, optional durable caching, and special-election coverage.
