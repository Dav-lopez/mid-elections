"""Offline regression tests for independent production health monitoring."""
import json
import unittest
from urllib.error import HTTPError

from scripts.monitor_deployment import (
    MAX_RESPONSE_BYTES, check_feed, check_site, run_checks, summary,
)


def payload(office="House", **updates):
    value = {
        "api": 1, "year": 2026, "office": office,
        "live": False, "stale": False, "counting": False, "final": False,
        "as_of": None, "source": "", "races": {},
    }
    value.update(updates)
    return value


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    def read(self, limit):
        return self.data[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Opener:
    def __init__(self, *items):
        self.items = list(items)
        self.calls = []

    def __call__(self, request, *, timeout):
        self.calls.append((request.full_url, timeout))
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def json_response(value):
    return Response(json.dumps(value).encode("utf-8"))


class HealthMonitorTests(unittest.TestCase):
    def test_empty_pre_election_feed_is_valid_not_zero(self):
        opener = Opener(json_response(payload()))
        check = check_feed("House", "https://provider.example/results.json", opener)
        self.assertEqual(check.status, "PASS")
        self.assertIn("no race-coverage guarantee", check.detail)
        self.assertIn("year=2026", opener.calls[0][0])
        self.assertIn("office=House", opener.calls[0][0])

    def test_wrong_office_fails_even_if_http_200(self):
        check = check_feed(
            "House", "https://provider.example/results.json",
            Opener(json_response(payload("Senate"))),
        )
        self.assertEqual(check.status, "FAIL")

    def test_malformed_json_and_contract_fail(self):
        for body in (b"{bad", json.dumps(payload(api=2)).encode()):
            with self.subTest(body=body[:20]):
                check = check_feed(
                    "House", "https://provider.example/results.json",
                    Opener(Response(body)),
                )
                self.assertEqual(check.status, "FAIL")

    def test_provider_stale_flag_is_reported_without_fabricating_freshness(self):
        check = check_feed(
            "Senate", "https://provider.example/results.json",
            Opener(json_response(payload("Senate", stale=True))),
        )
        self.assertEqual(check.status, "PASS")
        self.assertIn("provider marks data stale", check.detail)

    def test_http_503_is_reported(self):
        error = HTTPError("https://provider.example", 503, "unavailable", None, None)
        check = check_feed(
            "House", "https://provider.example/results.json", Opener(error),
        )
        self.assertEqual(check.status, "FAIL")
        self.assertEqual(check.detail, "HTTP 503")

    def test_response_size_bound(self):
        check = check_feed(
            "House", "https://provider.example/results.json",
            Opener(Response(b" " * (MAX_RESPONSE_BYTES + 1))),
        )
        self.assertEqual(check.status, "FAIL")

    def test_missing_deployment_url_is_skipped(self):
        opener = Opener()
        check = check_site("", opener)
        self.assertEqual(check.status, "SKIP")
        self.assertEqual(opener.calls, [])

    def test_deployment_health_checks_only_streamlit_server(self):
        opener = Opener(Response(b"ok\n"))
        check = check_site("https://example.streamlit.app/something?token=abc", opener)
        self.assertEqual(check.status, "PASS")
        self.assertEqual(opener.calls[0][0], "https://example.streamlit.app/_stcore/health")
        self.assertIn("server health", check.detail)

    def test_sleeping_streamlit_redirect_wakes_then_returns_real_ok(self):
        redirect = HTTPError("https://example.streamlit.app/_stcore/health",
                             303, "See Other", None, None)
        opener = Opener(redirect, Response(b"<html>Starting app</html>"),
                        Response(b"ok\n"))
        delays = []
        check = check_site("https://example.streamlit.app", opener,
                           sleeper=delays.append)
        self.assertEqual(check.status, "PASS")
        self.assertIn("after transient response retry", check.detail)
        self.assertEqual(delays, [3])
        self.assertEqual(
            [url for url, _ in opener.calls],
            ["https://example.streamlit.app/_stcore/health",
             "https://example.streamlit.app/",
             "https://example.streamlit.app/_stcore/health"],
        )

    def test_persistent_redirect_never_counts_as_healthy(self):
        def redirect():
            return HTTPError("https://example.streamlit.app/_stcore/health",
                             303, "See Other", None, None)
        opener = Opener(redirect(), Response(b"<html>Login</html>"),
                        redirect(), redirect())
        delays = []
        check = check_site("https://example.streamlit.app", opener,
                           sleeper=delays.append)
        self.assertEqual(check.status, "FAIL")
        self.assertIn("HTTP 303", check.detail)
        self.assertEqual(delays, [3, 6])
        self.assertEqual(len(opener.calls), 4)

    def test_transient_gateway_failure_recovers_without_wake_request(self):
        gateway = HTTPError("https://example.streamlit.app/_stcore/health",
                            503, "Unavailable", None, None)
        opener = Opener(gateway, Response(b"ok"))
        delays = []
        check = check_site("https://example.streamlit.app", opener,
                           sleeper=delays.append)
        self.assertEqual(check.status, "PASS")
        self.assertEqual(delays, [3])
        self.assertEqual(len(opener.calls), 2)

    def test_login_html_cannot_pass_health_probe(self):
        opener = Opener(Response(b"<html>Sign in</html>"))
        check = check_site("https://example.streamlit.app", opener,
                           sleeper=lambda _: self.fail("Unexpected retry"))
        self.assertEqual(check.status, "FAIL")
        self.assertEqual(len(opener.calls), 1)

    def test_bad_deployment_health_and_insecure_url_fail(self):
        for url, opener in (
            ("https://example.streamlit.app", Opener(Response(b"not ok"))),
            ("http://example.streamlit.app", Opener()),
        ):
            with self.subTest(url=url):
                self.assertEqual(check_site(url, opener).status, "FAIL")

    def test_checks_are_independent_and_summary_contains_no_vote_data(self):
        opener = Opener(
            Response(b"{invalid"),
            json_response(payload("Senate")),
            Response(b"ok"),
        )
        checks = run_checks(
            "https://provider.example/results.json",
            "https://example.streamlit.app", opener,
        )
        self.assertEqual([check.status for check in checks], ["FAIL", "PASS", "PASS"])
        report = summary(checks)
        self.assertIn("| House | FAIL |", report)
        self.assertIn("| Senate | PASS |", report)
        self.assertNotIn("vote totals", report.lower())


if __name__ == "__main__":
    unittest.main()
