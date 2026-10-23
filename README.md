# CivicPulse — 2026 U.S. Congressional Elections

CivicPulse is an independent, nonpartisan Streamlit viewer for **partial-coverage, unofficial** congressional election returns. It does not predict, infer, or call races. Its national map visualizes **source-data availability**, not party control or winners.

## Features

- Registry of 435 House districts, 33 regular Senate contests, and the Florida and Ohio Senate special elections (470 contests in total).
- State-level data-availability map with five neutral status categories, an accessible table, and a downloadable state CSV.
- **State spotlight:** choose a state and chamber to see tracked contests, source coverage, and candidate vote breakdowns where available. The selector is a keyboard-accessible alternative to relying on map interaction.
- Race explorer with state/chamber/coverage filters, candidate search, race details, and filtered CSV export.
- Clear distinction between votes reported, races listed without votes, missing races, unsupported states, and feed failures. Missing data is **not zero**.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Set `ELECTION_RESULTS_URL` to override the default provider endpoint. The endpoint must implement the expected API v1 JSON contract.

## Deploy

Connect this repository to Streamlit Community Cloud, select the `main` branch and `app.py` entrypoint, then deploy. Before promoting the deployment, verify the real provider connection, mobile layout, keyboard navigation, and live error behavior. CI alone does not validate production hosting.

## Feed contract and coverage

- Provider: [Open America election results API](https://openamerica.io/elections/api/), version 1. Its returns are unofficial, and provider-supplied calls are not legal certification.
- The app's documented adapter list (recorded **2026-09-27**) covers **22 states**: AR, AZ, CO, CT, FL, GA, IA, ID, IN, LA, MI, MN, NC, PA, RI, SC, TX, UT, VA, VT, WA, WV. An adapter is not a promise of data for every race.
- Florida and Ohio special Senate elections have distinct registry identifiers. Their inclusion does not imply that the provider supplies both results.
- The publisher's `as_of` timestamp is the newest update anywhere in an office feed, **not** the update time of each race.
- The map does not represent partisan winners or forecast outcomes. Source outages take precedence in its availability classification, even when last-known results remain visible.

## HTTP resilience

The process-shared `ElectionFeedClient` caches House and Senate separately. Conditional requests use ETags; HTTP 304 reuses the last validated body. Normal polling is 60 seconds when live, 10 minutes before results, and 15 minutes when counting but not live. Failures back off exponentially up to 10 minutes; manual refresh cannot bypass backoff or the minimum 60-second request gap.

On HTTP failures or invalid payloads, the last validated snapshot is retained and marked not verified fresh. The cache also writes validated JSON snapshots atomically under `.civicpulse-cache/` (override with `CIVICPULSE_CACHE_DIR`). After a process restart, snapshots no older than 72 hours are validated against the feed contract, their source endpoint is checked, and they are displayed only as **last-known, not verified fresh** until a new successful HTTP check (including HTTP 304). A restart always attempts a new request. Cache corruption, expiration and filesystem write errors cannot replace valid live data. Local disk is **not durable across redeploys, ephemeral instance replacement, or multiple server processes**, so external storage is required for those scenarios.

## Independent health monitoring

A separate GitHub Actions workflow (`.github/workflows/health-monitor.yml`) runs every
15 minutes (subject to GitHub scheduler delays) and can also be started from
**Actions → CivicPulse independent source and deployment monitor → Run workflow**.
It makes read-only checks of the House and Senate 2026 API-v1 payloads and validates
the returned office/year/schema. Empty feeds before election night **pass**; the
monitor never invents race coverage, reads candidate winners, or records vote totals.

**After deploying Streamlit**, open **GitHub repository Settings → Secrets and
variables → Actions → Variables → New repository variable**, and set
`CIVICPULSE_SITE_URL` to the deployed HTTPS origin (for example,
`https://your-app.streamlit.app`). The workflow then checks
`/_stcore/health` in addition to both provider feeds. If the variable is absent,
the deployment check explicitly reports **SKIP**; source checks still run.
Optionally set `ELECTION_RESULTS_URL` to match the app's configured HTTPS source.
No API key or secret is required for the default provider.

Each successful source check also compares the identifiers actually published in
that office feed with the 2026 tracked-seat registry. The summary shows the number
of matched and unmatched identifiers and up to five sanitized examples of unmatched
keys. These are **mapping diagnostics**, not votes, winners, certified results, or
proof of statewide/national coverage. Empty pre-election feeds are valid; an
unmatched identifier prompts manual mapping review but does not fail a valid feed.
The source may use different IDs for special contests, so no automatic aliasing is
performed without provider verification.

Each run writes a component-by-component GitHub Actions summary and fails if a
source contract or configured site-health check fails. To receive notifications,
configure your GitHub Actions workflow-failure notifications or an independent
uptime alert. **GitHub Actions does not automatically send a custom alert email
from this workflow.** Failures may reflect a provider outage rather than an app
defect. This is a transport/schema check, **not** proof of election-night vote
freshness, all-state coverage, full page rendering, or browser accessibility.
Streamlit's server health endpoint can return OK even if a session script fails.
A separate external uptime monitor and browser-level smoke test are still advised.

## Tests

```bash
python -m compileall -q app.py civicpulse_core.py civicpulse_client.py civicpulse_registry.py civicpulse_map.py civicpulse_explorer.py civicpulse_polling.py civicpulse_disk_cache.py civicpulse_source_audit.py
python -m unittest discover -s tests -v
```

GitHub Actions runs compilation, unit tests, and Streamlit AppTest script execution on feature pushes and pull requests. AppTest exercises an empty-but-valid source and a provider outage with deterministic fixtures, detecting runtime script failures that a server health endpoint alone can miss. Mocked HTTP tests cover conditional requests, timeouts, backoff, and recovery. Pure tests cover registry completeness, map aggregation, state navigation, and candidate vote filtering. These checks **do not** establish live provider availability, actual election-night performance, visual responsiveness, or browser-level accessibility.

## Responsible use and limitations

Attribute provider data to **official state election offices via Open America** and preserve timestamps. Open America does not provide complete national results coverage. Reporting 100% of precincts is not legal certification. Verify consequential claims with the responsible state election office or [USA.gov's election results guide](https://www.usa.gov/election-results). Contact the provider before repackaging its feed as a standalone commercial results service.

Next priorities: browser accessibility checks, mobile responsiveness, live source reconciliation, load testing, deployment monitoring, and external durable storage.
