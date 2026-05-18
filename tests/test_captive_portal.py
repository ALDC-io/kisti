"""Tests for the KiSTI captive portal + gateway API.

Covers the iOS captive-portal probe detection logic and the HTTP handler's
response shapes. Uses a real HTTP server bound to a random local port —
no mocking of socket layer, since the responder is stdlib-only.
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "jetson"))

from captive_portal import (  # noqa: E402
    APPLE_SUCCESS_BODY,
    is_apple_captive_probe,
    make_server,
)


class TestCaptiveProbeDetection:
    """Pure-function tests for is_apple_captive_probe()."""

    def test_captive_apple_com_root_path(self):
        assert is_apple_captive_probe("captive.apple.com", "/")

    def test_captive_apple_com_hotspot_path(self):
        assert is_apple_captive_probe(
            "captive.apple.com", "/hotspot-detect.html"
        )

    def test_captive_apple_com_any_path(self):
        # Apple's real server returns success for any path on this host
        assert is_apple_captive_probe("captive.apple.com", "/anything")

    def test_host_header_with_port(self):
        # iOS sometimes appends :80
        assert is_apple_captive_probe("captive.apple.com:80", "/")

    def test_host_header_case_insensitive(self):
        assert is_apple_captive_probe("CAPTIVE.APPLE.COM", "/")

    def test_www_apple_only_success_path(self):
        assert is_apple_captive_probe(
            "www.apple.com", "/library/test/success.html"
        )

    def test_www_apple_other_paths_ignored(self):
        # Don't intercept legitimate www.apple.com traffic
        assert not is_apple_captive_probe("www.apple.com", "/")
        assert not is_apple_captive_probe("www.apple.com", "/iphone")

    def test_unrelated_host_ignored(self):
        assert not is_apple_captive_probe("zeus.aldc.io", "/")
        assert not is_apple_captive_probe("google.com", "/generate_204")

    def test_empty_host(self):
        assert not is_apple_captive_probe("", "/")
        assert not is_apple_captive_probe(None, "/")  # type: ignore[arg-type]


@pytest.fixture
def server():
    """Boot the captive portal on an ephemeral port; tear down after test."""
    srv = make_server(host="127.0.0.1", port=0)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=2)


def _get(url: str, host: str | None = None) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, method="GET")
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


class TestHTTPHandler:
    def test_health_endpoint(self, server):
        status, body, _ = _get(f"{server}/v1/health")
        assert status == 200
        payload = json.loads(body)
        assert payload == {"ok": True, "service": "kisti", "version": 1}

    def test_apple_captive_probe_returns_exact_body(self, server):
        # iOS sends Host: captive.apple.com when DNS rewrites it to us
        status, body, headers = _get(
            f"{server}/hotspot-detect.html", host="captive.apple.com"
        )
        assert status == 200
        assert body == APPLE_SUCCESS_BODY
        assert headers.get("Content-Type", "").startswith("text/html")

    def test_apple_captive_probe_root_path(self, server):
        status, body, _ = _get(f"{server}/", host="captive.apple.com")
        assert status == 200
        assert body == APPLE_SUCCESS_BODY

    def test_non_captive_request_no_apple_body(self, server):
        # Without the captive Host header, we serve our own banner
        status, body, _ = _get(f"{server}/")
        assert status == 200
        assert b"Success" not in body
        assert b"KiSTI" in body

    def test_query_stub_returns_501(self, server):
        status, body, _ = _get(f"{server}/v1/query?text=oil+temp")
        assert status == 501
        payload = json.loads(body)
        assert payload["ok"] is False
        assert payload["reason"] == "not_implemented"

    def test_query_post_stub(self, server):
        req = urllib.request.Request(
            f"{server}/v1/query",
            data=json.dumps({"text": "what's my oil temp"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
                body = resp.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read()
        assert status == 501
        assert json.loads(body)["reason"] == "not_implemented"
