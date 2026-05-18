"""KiSTI captive portal + gateway API.

Runs on the Jetson AP at 192.168.42.1:8080. Inbound HTTP traffic on
port 80 is redirected here by iptables (see kisti-ap-up.sh), so this
single server handles:

  1. iOS captive-portal probes hitting captive.apple.com (DNS-rewritten
     to 192.168.42.1 by dnsmasq). Returning the exact Apple success body
     keeps iOS from marking the network as "no internet" and dropping
     the association — even when the Jetson has no upstream uplink yet.

  2. /v1/health — for the iOS app to verify Bonjour discovery worked
     and the gateway is alive.

  3. /v1/query — placeholder. A follow-up PR wires this to the
     deterministic handlers in voice_manager._answer_from_sensors and
     _answer_from_timing so the iOS app can ask "what's my oil temp"
     and get a sub-100 ms local answer.

stdlib only — no Flask, no FastAPI. Runs anywhere Python 3 runs.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("kisti.captive")

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8080

# Exact body Apple's own server returns for captive.apple.com.
# iOS compares this byte-for-byte to decide if the network is open.
APPLE_SUCCESS_BODY = (
    b"<HTML><HEAD><TITLE>Success</TITLE></HEAD>"
    b"<BODY>Success</BODY></HTML>\n"
)

# Host header values iOS sends for its captive-portal probe.
APPLE_CAPTIVE_HOSTS = frozenset({
    "captive.apple.com",
    "www.apple.com",  # iOS sometimes uses the legacy probe path here
})


def is_apple_captive_probe(host: str, path: str) -> bool:
    """True if this request looks like an iOS captive-portal probe.

    iOS hits http://captive.apple.com/hotspot-detect.html (or just "/")
    on every WiFi join and periodically afterwards. We answer for any
    path on captive.apple.com — Apple's own server does the same.
    """
    host = (host or "").split(":")[0].lower().strip()
    if host not in APPLE_CAPTIVE_HOSTS:
        return False
    # captive.apple.com responds to any GET path; www.apple.com only
    # to the specific success-page path.
    if host == "captive.apple.com":
        return True
    return path.startswith("/library/test/success.html")


class KistiHandler(BaseHTTPRequestHandler):
    server_version = "kisti/1"

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:
        host = self.headers.get("Host", "")
        path = self.path

        if is_apple_captive_probe(host, path):
            self._send_apple_success()
            return

        if path == "/v1/health":
            self._send_json({"ok": True, "service": "kisti", "version": 1})
            return

        if path.startswith("/v1/query"):
            self._send_query_stub()
            return

        self._send_text("KiSTI gateway. See /v1/health.\n")

    def do_POST(self) -> None:
        if self.path.startswith("/v1/query"):
            self._send_query_stub()
            return
        self._send_text("not found\n", status=404)

    def _send_apple_success(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(APPLE_SUCCESS_BODY)))
        self.send_header("Cache-Control", "private, max-age=0, no-cache")
        self.end_headers()
        self.wfile.write(APPLE_SUCCESS_BODY)

    def _send_query_stub(self) -> None:
        self._send_json(
            {
                "ok": False,
                "reason": "not_implemented",
                "note": "wire to voice_manager handlers in follow-up PR",
            },
            status=501,
        )

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(host: str = LISTEN_HOST, port: int = LISTEN_PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), KistiHandler)
    server.daemon_threads = True
    return server


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    server = make_server()
    log.info("KiSTI gateway listening on %s:%d", LISTEN_HOST, LISTEN_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
