"""Independent, read-only source-contract and optional deployment health checks.

This checks transport and schema health only. It does not claim election coverage,
call winners, or interpret missing races as zero. No vote data is logged.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from civicpulse_core import FeedValidationError, parse_feed
from civicpulse_source_audit import audit_feed_keys

DEFAULT_SOURCE = "https://openamerica.io/elections/results.json"
MAX_RESPONSE_BYTES = 8_000_000
TIMEOUT_SECONDS = 12


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # PASS, FAIL, SKIP
    detail: str


def _https_parts(url: str):
    parts = urlsplit(url)
    if (parts.scheme != "https" or not parts.hostname or
            parts.username is not None or parts.password is not None):
        raise ValueError("Expected an HTTPS URL without credentials")
    return parts


def _feed_url(source: str, office: str) -> str:
    parts = _https_parts(source)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params.update({"year": "2026", "office": office})
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(params), ""))


def _site_health_url(site: str) -> str:
    parts = _https_parts(site)
    return urlunsplit((parts.scheme, parts.netloc, "/_stcore/health", "", ""))


def _read(url: str, accept: str, opener) -> bytes:
    request = Request(url, headers={
        "Accept": accept,
        "User-Agent": "CivicPulse-health-monitor/1.0 (read-only status check)",
    })
    with opener(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise ValueError("Unexpected HTTP status")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Response exceeds size limit")
    return body


def check_feed(office: str, source: str, opener=urlopen) -> Check:
    """Check both transport and the real API-v1 contract, even before votes exist."""
    if office not in ("House", "Senate"):
        raise ValueError("Unsupported office")
    try:
        body = _read(_feed_url(source, office), "application/json", opener)
        payload = json.loads(body)
        feed = parse_feed(payload, office)
        detail = "API v1 valid; no race-coverage guarantee; " + audit_feed_keys(feed).detail
        if feed.stale:
            detail += "; provider marks data stale"
        return Check(office, "PASS", detail)
    except HTTPError as exc:
        return Check(office, "FAIL", f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError) as exc:
        return Check(office, "FAIL", f"Network failure ({type(exc).__name__})")
    except (ValueError, TypeError, UnicodeError, FeedValidationError):
        return Check(office, "FAIL", "Invalid endpoint, response or API contract")


def _wake_site(site: str, opener) -> None:
    """Best-effort read-only wake request on the configured HTTPS origin.

    Streamlit Community Cloud may redirect an idle app before its health
    endpoint becomes available. The root request is not a health success.
    """
    parts = _https_parts(site)
    root = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
    try:
        _read(root, "text/html", opener)
    except (HTTPError, URLError, TimeoutError, OSError,
            ValueError, TypeError, UnicodeError):
        pass


def check_site(site: str, opener=urlopen, sleeper=time.sleep) -> Check:
    """Require an actual 'ok' response, even after a cold-start retry.

    A redirect, gateway failure or HTML login page is never counted as PASS.
    Retry only 303/502/503 to avoid misclassifying transient cold starts as
    permanent outages. Inject sleeper in tests to keep them deterministic.
    """
    if not site.strip():
        return Check("Deployment", "SKIP", "CIVICPULSE_SITE_URL not configured")
    try:
        url = _site_health_url(site)
        for attempt in range(3):
            try:
                body = _read(url, "text/plain", opener)
                if body.strip().lower() != b"ok":
                    raise ValueError("Unexpected health response")
                detail = "Streamlit server health endpoint responded"
                if attempt:
                    detail += " after transient response retry"
                return Check("Deployment", "PASS", detail)
            except HTTPError as exc:
                if exc.code in (303, 502, 503) and attempt < 2:
                    if exc.code == 303 and attempt == 0:
                        _wake_site(site, opener)
                    sleeper(3 * (attempt + 1))
                    continue
                if exc.code == 303:
                    return Check(
                        "Deployment", "FAIL",
                        "HTTP 303 redirect persisted; app may be sleeping or access-gated",
                    )
                return Check("Deployment", "FAIL", f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError) as exc:
        return Check("Deployment", "FAIL", f"Network failure ({type(exc).__name__})")
    except (ValueError, TypeError, UnicodeError):
        return Check("Deployment", "FAIL", "Invalid URL or health response")
    return Check("Deployment", "FAIL", "Health endpoint did not respond")


def run_checks(source: str, site: str, opener=urlopen, *, scope: str = "all") -> list[Check]:
    """Run independent source/deployment probes without masking either result.

    Scope is explicit so CI can show provider-contract and app-readiness
    failures as separate jobs. The default preserves local combined checks.
    """
    if scope not in ("all", "source", "deployment"):
        raise ValueError("Monitor scope must be all, source, or deployment")
    checks = []
    if scope in ("all", "source"):
        checks.extend((
            check_feed("House", source, opener),
            check_feed("Senate", source, opener),
        ))
    if scope in ("all", "deployment"):
        checks.append(check_site(site, opener))
    return checks


def summary(checks: list[Check]) -> str:
    lines = [
        "# CivicPulse independent health monitor",
        "",
        "Checks API schema/transport and optional Streamlit readiness, not election results,",
        "candidate leads, actual race coverage, or end-to-end browser functionality.",
        "",
        "| Component | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in checks:
        lines.append(f"| {check.name} | {check.status} | {check.detail} |")
    lines += ["", "Failures require investigation; source availability can change independently of the app."]
    return "\n".join(lines) + "\n"


def main() -> int:
    checks = run_checks(
        os.getenv("ELECTION_RESULTS_URL") or DEFAULT_SOURCE,
        os.getenv("CIVICPULSE_SITE_URL") or "",
        scope=os.getenv("CIVICPULSE_MONITOR_SCOPE", "all").strip().lower(),
    )
    report = summary(checks)
    print(report)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as file:
            file.write(report)
    return 1 if any(check.status == "FAIL" for check in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
