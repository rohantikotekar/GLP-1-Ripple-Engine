"""Egress guardrail — a forward proxy that enforces the domain allowlist.

The autonomous loop is started with HTTP_PROXY/HTTPS_PROXY pointing here, so
every outbound request it makes is forced through this filter. Requests to a
domain on the allowlist are tunnelled to the real upstream; everything else is
refused with 403. This is the "guardrail on an autonomous book" (Pomerium role):
the agent physically cannot reach anything but its four approved data feeds.

Pure stdlib so the container stays tiny and auditable. Handles both HTTP CONNECT
(HTTPS tunnelling — the common case for httpx/requests) and plain HTTP proxying.
"""
import os
import select
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

LISTEN_PORT = int(os.environ.get("GUARDRAIL_PORT", "3128"))
ALLOWLIST_PATH = os.environ.get("ALLOWLIST_PATH", "/etc/guardrail/allowlist.txt")


def load_allowlist(path: str) -> set[str]:
    domains: set[str] = set()
    with open(path) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                domains.add(line.lower())
    return domains


ALLOWED = load_allowlist(ALLOWLIST_PATH)


def is_allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in ALLOWED)


def log(decision: str, host: str) -> None:
    # Single structured line per request so the decision stream is demo-visible.
    print(f"[guardrail] {decision:5} {host}", flush=True)


class GuardrailProxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _deny(self, host: str) -> None:
        log("DENY", host)
        body = f"Egress blocked by guardrail: {host} is not on the allowlist.\n".encode()
        self.send_response(403)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_CONNECT(self) -> None:  # HTTPS tunnelling
        host = self.path.split(":", 1)[0]
        if not is_allowed(host):
            self._deny(host)
            return
        port = int(self.path.split(":", 1)[1]) if ":" in self.path else 443
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError as exc:
            log("FAIL", f"{host} ({exc})")
            self.send_error(502)
            return
        log("ALLOW", host)
        self.send_response(200, "Connection Established")
        self.end_headers()
        self._tunnel(self.connection, upstream)

    def _proxy_plain(self) -> None:  # plain HTTP
        host = urlsplit(self.path).hostname or ""
        if not is_allowed(host):
            self._deny(host)
            return
        log("ALLOW", host)
        parts = urlsplit(self.path)
        port = parts.port or 80
        try:
            upstream = socket.create_connection((parts.hostname, port), timeout=10)
        except OSError:
            self.send_error(502)
            return
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        req = [f"{self.command} {path} HTTP/1.1"]
        for k, v in self.headers.items():
            if k.lower() != "proxy-connection":
                req.append(f"{k}: {v}")
        req.append("\r\n")
        upstream.sendall("\r\n".join(req).encode())
        self._tunnel(self.connection, upstream)

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_PATCH = _proxy_plain

    @staticmethod
    def _tunnel(a: socket.socket, b: socket.socket) -> None:
        socks = [a, b]
        try:
            while True:
                r, _, x = select.select(socks, [], socks, 30)
                if x or not r:
                    break
                for s in r:
                    data = s.recv(65536)
                    if not data:
                        return
                    (b if s is a else a).sendall(data)
        finally:
            for s in (a, b):
                try:
                    s.close()
                except OSError:
                    pass

    def log_message(self, *_args) -> None:  # silence default noisy logging
        pass


def main() -> None:
    print(f"[guardrail] allowlist ({len(ALLOWED)}): {sorted(ALLOWED)}", flush=True)
    print(f"[guardrail] listening on :{LISTEN_PORT} — default-deny egress proxy", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), GuardrailProxy)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
