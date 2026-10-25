# CivicPulse — 2026 U.S. Congressional Elections

CivicPulse is an independent, nonpartisan Streamlit viewer for **partial-coverage, unofficial** congressional election returns. It does not predict, infer, or call races. Its national map visualizes **source-data availability**, not party control or winners.

## Features

- Registry of 435 House districts, 33 regular Senate contests, and the Florida and Ohio Senate special elections (470 contests in total).
- State-level data-availability map with five neutral status categories, an accessible table, and a downloadable state CSV.
- **State spotlight:** choose a state and chamber to see tracked contests, source coverage, and candidate vote breakdowns where available. The selector is a keyboard-accessible alternative to relying on map interaction.
- Race explorer with state/chamber/coverage filters, candidate search, race details, and filtered CSV export.
- Clear distinction between votes reported, races listed without votes, missing races, unsupported states, and feed failures. Missing data is **not zero**.
- Downloaded CSVs are intended for spreadsheet viewing: provider-supplied strings beginning with formula-like characters (including after invisible whitespace) are prefixed with an apostrophe, and fields are quoted. This affects the downloaded text, not the in-app data; it is not a universal guarantee after spreadsheet save/reopen. Use verified raw source data for machine-to-machine processing.
- **No inferred race totals:** The `Votes` column shows only provider-published race totals. Positive candidate-level counts can mark a race as reporting while its race-wide total remains blank if unpublished. Candidate lists may omit write-ins or delayed entries; they are never summed to fabricate a total.

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
- Race identifiers are normalized to uppercase. Empty, whitespace-padded, or case-colliding identifiers invalidate a response rather than silently replacing a contest; the dashboard retains the last validated snapshot with an error warning. This protects local parsing integrity, not provider coverage or source accuracy.
- The map does not represent partisan winners or forecast outcomes. Source outages take precedence in its availability classification, even when last-known results remain visible.

## HTTP resilience

The process-shared `ElectionFeedClient` caches House and Senate separately. House and Senate HTTP requests use separate `requests.Session` instances, and all viewers share a bounded two-worker polling pool rather than creating two polling threads per viewer rerun. This bounds application-created polling threads; it does **not** cap Streamlit's own session threads or guarantee acceptable performance at 100–200 simultaneous users. The first viewer can still wait for a slow provider response. Conditional requests use ETags; HTTP 304 reuses the last validated body. Normal polling is 60 seconds when live, 10 minutes before results, and 15 minutes when counting but not live. Failures back off exponentially up to 10 minutes. On HTTP 429 (rate limited) and 503 (unavailable), valid provider `Retry-After` delays (seconds or HTTP dates) extend the wait up to the same 10-minute cap; invalid headers fall back to exponential backoff. Manual refresh cannot bypass backoff or the minimum 60-second request gap. This reduces unnecessary retries but does not guarantee adherence to provider rate limits longer than 10 minutes.

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
The deployment probe requires an exact `ok` response from `/_stcore/health`.
If Streamlit Community Cloud returns a transient HTTP 303 redirect (such as
during an app cold start), it makes one read-only request to the same origin's
home page and retries the health endpoint twice with short bounded delays.
Transient HTTP 502/503 responses are also retried. The health probe also
rejects redirects silently followed by Python's HTTP client, even when the
redirect destination returns HTTP 200 or the text `ok`; only a direct response
from `/_stcore/health` can pass. A persistent redirect, login page, or
unhealthy response still **fails** the monitor; a successful health response
verifies server readiness only, not dashboard rendering.
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

The **Data & methodology** tab now displays the same identifier reconciliation for
each office directly in the dashboard, including a warning when published keys do
not match tracked contests. When the latest request fails, the audit is explicitly
labeled as using the last validated snapshot; when no validated feed exists, the
audit is unavailable. Unmatched keys never get assigned to a tracked contest,
and the counts are not evidence of reported votes or complete provider coverage.

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

GitHub Actions runs compilation, unit tests, and Streamlit AppTest script execution on feature pushes and pull requests. AppTest exercises an empty-but-valid source, a provider outage, a **synthetic partial candidate return**, and an unmatched synthetic provider race identifier with deterministic fixtures. The partial-return scenario selects a state in the running Streamlit script, checks candidate vote details, and verifies that an unpublished race total remains blank and an uncalled leader is not presented as a winner. These execution tests detect UI regressions that a server health endpoint alone can miss. Mocked HTTP tests cover conditional requests, timeouts, backoff, recovery, isolated HTTP sessions, and 120 simultaneous synthetic viewer reruns sharing at most two polling workers. Pure tests cover registry completeness, map aggregation, state navigation, and candidate vote filtering. These checks **do not** establish live provider availability, actual election-night performance, visual responsiveness, or browser-level accessibility.

## Browser-level smoke tests

CI runs a separate real-Chromium job at **1280px desktop** and **390px mobile**
against a local synthetic **empty** 2026 House/Senate provider. It checks that
the app renders its map and state spotlight without Streamlit exceptions, the
spotlight has an accessible selector, the desktop tabs support keyboard
activation, and the mobile hero fits the viewport. CI retains desktop/mobile
screenshots and the server log as short-lived artifacts for inspection.

Run locally after installing Playwright and its Chromium browser:

```bash
python -m pip install "playwright>=1.55,<2"
python -m playwright install chromium
python scripts/browser_smoke.py
```

This is a smoke test, **not** a full WCAG audit, assistive-technology test,
mobile-device compatibility certification, live-provider test, or a 100–200
concurrent-user load test. The screenshots contain only synthetic empty feeds;
the script never requests real vote data.

## Responsible use and limitations

Attribute provider data to **official state election offices via Open America** and preserve timestamps. Open America does not provide complete national results coverage. Reporting 100% of precincts is not legal certification. Verify consequential claims with the responsible state election office or [USA.gov's election results guide](https://www.usa.gov/election-results). Contact the provider before repackaging its feed as a standalone commercial results service.

Next priorities: a complete WCAG/assistive-technology audit, mobile usability review, live source reconciliation, load testing, deployment monitoring, and external durable storage.
