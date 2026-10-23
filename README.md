# CivicPulse — 2026 U.S. Congressional Elections

A modern, nonpartisan Streamlit dashboard with filters, race drill-downs, CSV export, and a refresh interval of 60 seconds.

## Deploy for free

1. Merge this feature PR into `main`.
2. Go to https://share.streamlit.io and connect the GitHub repository `Dav-lopez/mid-elections`.
3. Set the entrypoint to `app.py`, select `main`, and deploy.
4. Confirm that the app builds and that results can be fetched from the API.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Included features

- Registry of 435 House seats and 33 regularly scheduled Senate elections.
- Responsive editorial UI, source-status indicators, state/chamber filtering, candidate search, race details, and CSV download.
- Results adapter for Open America's public `results.json` API for 2026 House and Senate races.
- Auto-refresh every 60 seconds, manual refresh button, cached HTTP requests, and error warnings.
- Distinguishes **no source coverage**, **feed listed without results**, and **reported votes**. Does not extrapolate, predict winners, or treat missing results as zero.

## Data and reliability caveats

The Open America provider is not a nationwide source for all 50 states. A 60-second application refresh does not guarantee a provider publishes updates that quickly. No production verification has been completed yet. Source-reported race calls, if any, must be confirmed with the originating election authority. The Senate registry excludes special elections. Do not present this MVP as an authoritative national results service.

Additional national coverage will require reliable state-level or licensed feeds, state/district key validation, source reconciliation, monitoring, and election-night load testing.

Official election resources: https://www.usa.gov/election-results
