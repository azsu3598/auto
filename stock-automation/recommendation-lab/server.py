"""Manual localhost research lab. Does not import or start the trading runtime."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets

from service import RecommendationService, SnapshotFileSource

WEB = Path(__file__).resolve().parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/styles.css": ("styles.css", "text/css; charset=utf-8")}


def handler_for(service, *, origin, csrf):
    expected_host = origin.removeprefix("http://")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # No query strings, request bodies or credentials in logs.

        def reply(self, status, content, mime="application/json; charset=utf-8"):
            data = content if isinstance(content, bytes) else json.dumps(content, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(data)

        def valid_host(self):
            return self.headers.get("Host") == expected_host

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {"status": "BLOCKED", "reason": "INVALID_HOST"})
            asset = STATIC.get(self.path)
            if asset is None:
                return self.reply(404, {"status": "BLOCKED", "reason": "NOT_FOUND"})
            name, mime = asset
            content = (WEB / name).read_bytes()
            if name == "index.html":
                content = content.replace(b"__CSRF_TOKEN__", csrf.encode("ascii"))
            self.reply(200, content, mime)

        def do_POST(self):
            if (not self.valid_host() or self.headers.get("Origin") != origin
                    or not secrets.compare_digest(self.headers.get("X-Recommendation-CSRF", ""), csrf)):
                return self.reply(403, {"status": "BLOCKED", "reason": "LOCAL_REQUEST_REQUIRED"})
            if self.path != "/api/recommendations":
                return self.reply(404, {"status": "BLOCKED", "reason": "NOT_FOUND"})
            if self.headers.get("Content-Type") != "application/json" or self.headers.get("Transfer-Encoding"):
                return self.reply(400, {"status": "BLOCKED", "reason": "INVALID_BODY"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 1 <= size <= 256:
                    raise ValueError
                self.connection.settimeout(3)
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or set(body) != {"request_id"}:
                    raise ValueError
            except (ValueError, OSError):
                return self.reply(400, {"status": "BLOCKED", "reason": "INVALID_BODY"})
            status, result = service.request(body["request_id"])
            self.reply(status, result)

        def do_OPTIONS(self):
            self.reply(405, {"status": "BLOCKED", "reason": "CROSS_ORIGIN_NOT_SUPPORTED"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Local research development module; not for public hosting")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--snapshot", type=Path, help="Trusted research JSON; never a broker/ledger file")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a non-privileged local port")
    source = SnapshotFileSource(args.snapshot) if args.snapshot else None
    origin = f"http://127.0.0.1:{args.port}"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(
        RecommendationService(source), origin=origin, csrf=secrets.token_hex(32)))
    server.daemon_threads = True
    print("RESEARCH LAB ONLY: " + origin + " / no broker, ledger, AWS or AI connection")
    print("Without --snapshot the analysis endpoint stays BLOCKED. Ctrl+C stops this lab only.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
