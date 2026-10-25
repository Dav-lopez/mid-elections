"""Real Chromium smoke test using a synthetic empty 2026 provider.

This is an opt-in CI browser test, separate from unit tests. It never requests
actual election results and cannot establish provider availability or full WCAG
compliance. Screenshots contain only empty-fixture dashboard data.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "browser-smoke"


class EmptyElectionFeed(BaseHTTPRequestHandler):
    def do_GET(self):
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        office = query.get("office", [""])[0]
        if (parts.path != "/results.json" or
                query.get("year") != ["2026"] or office not in ("House", "Senate")):
            self.send_error(404)
            return
        payload = {
            "api": 1, "year": 2026, "office": office,
            "live": False, "stale": False, "counting": False, "final": False,
            "as_of": None, "source": "", "races": {},
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_health(port, process, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("Streamlit process exited before becoming healthy")
        try:
            with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as res:
                if res.status == 200 and res.read().strip().lower() == b"ok":
                    return
        except OSError:
            pass
        time.sleep(0.5)
    raise AssertionError("Streamlit health endpoint did not start within 60 seconds")


def inspect_page(browser, port, *, mobile):
    name = "mobile-390px" if mobile else "desktop-1280px"
    context = browser.new_context(
        viewport={"width": 390 if mobile else 1280, "height": 844 if mobile else 900},
        device_scale_factor=1,
        is_mobile=mobile,
        has_touch=mobile,
    )
    page = context.new_page()
    try:
        page.goto(f"http://127.0.0.1:{port}", wait_until="domcontentloaded",
                  timeout=45_000)
        page.locator(".hero h1").wait_for(state="visible", timeout=75_000)
        page.get_by_role("heading", name="U.S. results-data availability map").wait_for(
            state="visible", timeout=75_000
        )
        page.get_by_role("heading", name="State spotlight").wait_for(
            state="visible", timeout=30_000
        )
        assert page.locator('[data-testid="stException"]').count() == 0, (
            f"Streamlit script raised an exception at {name}"
        )
        assert "No forecasts, inferred winners, or fabricated vote totals" in (
            page.locator(".hero").inner_text()
        )
        # Streamlit mounts controls asynchronously after section headings appear.
        # A synchronous count() can race that mount and falsely fail CI even
        # though the labeled, keyboard-accessible selector appears moments later.
        spotlight_selector = page.get_by_role("combobox", name="Inspect state")
        spotlight_selector.wait_for(state="visible", timeout=30_000)
        assert spotlight_selector.count() == 1, (
            "State spotlight must have exactly one labeled selector"
        )

        if mobile:
            box = page.locator(".hero").bounding_box()
            assert box is not None, "Hero missing on mobile"
            assert box["x"] >= -2 and box["x"] + box["width"] <= 392, (
                f"Hero overflows 390px mobile viewport: {box}"
            )
        else:
            race_tab = page.get_by_role("tab", name="Race explorer")
            race_tab.click()
            expect(race_tab).to_have_attribute("aria-selected", "true", timeout=10_000)
            overview_tab = page.get_by_role("tab", name="Overview & map")
            overview_tab.focus()
            overview_tab.press("Enter")
            expect(overview_tab).to_have_attribute("aria-selected", "true", timeout=10_000)
        print(f"PASS {name}: dashboard rendered; controls and navigation checked")
    finally:
        try:
            ARTIFACTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(ARTIFACTS / f"{name}.png"),
                            full_page=True, timeout=15_000)
        except Exception as exc:
            print(f"Screenshot unavailable for {name}: {exc}", file=sys.stderr)
        context.close()


def main():
    fixture = ThreadingHTTPServer(("127.0.0.1", 0), EmptyElectionFeed)
    fixture_thread = threading.Thread(target=fixture.serve_forever, daemon=True)
    fixture_thread.start()
    port = unused_port()
    env = os.environ.copy()
    env.update({
        "ELECTION_RESULTS_URL": f"http://127.0.0.1:{fixture.server_port}/results.json",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    })
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        env["CIVICPULSE_CACHE_DIR"] = directory
        log_path = ARTIFACTS / "streamlit.log"
        with log_path.open("w", encoding="utf-8") as logfile:
            process = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                 "--server.headless=true", "--server.address=127.0.0.1",
                 f"--server.port={port}", "--server.fileWatcherType=none"],
                cwd=ROOT, env=env, stdout=logfile, stderr=subprocess.STDOUT,
            )
            try:
                wait_for_health(port, process)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    try:
                        inspect_page(browser, port, mobile=False)
                        inspect_page(browser, port, mobile=True)
                    finally:
                        browser.close()
            except Exception:
                print("Browser smoke failure; last Streamlit log lines:",
                      file=sys.stderr)
                print(log_path.read_text(encoding="utf-8")[-5000:],
                      file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                fixture.shutdown()
                fixture.server_close()


if __name__ == "__main__":
    main()
