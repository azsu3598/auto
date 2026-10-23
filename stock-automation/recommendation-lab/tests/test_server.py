import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import unittest
from uuid import uuid4

from server import handler_for
from service import RecommendationService


class LocalHttpTests(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(
            RecommendationService(), origin="http://127.0.0.1:1", csrf="test-csrf"))
        self.origin = "http://127.0.0.1:" + str(self.httpd.server_port)
        self.httpd.RequestHandlerClass = handler_for(RecommendationService(), origin=self.origin, csrf="test-csrf")
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True); self.thread.start()

    def tearDown(self):
        self.httpd.shutdown(); self.httpd.server_close(); self.thread.join(timeout=2)

    def call(self, method="POST", path="/api/recommendations", body=None, **overrides):
        client = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=3)
        headers = {"Content-Type": "application/json", "Origin": self.origin, "X-Recommendation-CSRF": "test-csrf"}
        headers.update(overrides)
        payload = json.dumps({"request_id": str(uuid4())} if body is None else body)
        client.request(method, path, payload if method == "POST" else None, headers)
        response = client.getresponse(); data = response.read(); result = (response.status, dict(response.getheaders()), data)
        client.close(); return result

    def test_missing_cross_origin_csrf_and_invalid_host_rejected(self):
        for headers in [{"Origin": "https://evil.invalid"}, {"X-Recommendation-CSRF": "wrong"}, {"Host": "evil.invalid"}]:
            self.assertEqual(self.call(**headers)[0], 403)

    def test_body_cannot_set_account_mode_path_or_order(self):
        for extra in [{"mode": "LIVE"}, {"account": "private"}, {"snapshot": "/other"}, {"order": True}]:
            self.assertEqual(self.call(body={"request_id": str(uuid4()), **extra})[0], 400)

    def test_unconnected_post_stays_blocked_and_no_cors_is_added(self):
        status, headers, data = self.call()
        self.assertEqual(status, 503); self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertIn(b"DATA_SOURCE_NOT_CONNECTED", data)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_static_allowlist_blocks_traversal_queries_and_execution_routes(self):
        for route in ["/../core.py", "/server.py", "/?token=private", "/api/orders", "/config.js"]:
            self.assertEqual(self.call("GET", route)[0], 404)

    def test_html_has_local_csrf_no_credentials_and_no_public_api_configuration(self):
        status, headers, data = self.call("GET", "/")
        self.assertEqual(status, 200); self.assertIn(b"test-csrf", data)
        self.assertNotIn(b"__CSRF_TOKEN__", data); self.assertNotIn(b"amazonaws.com", data)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_javascript_is_manual_and_uses_safe_dom_rendering(self):
        source = (Path(__file__).resolve().parents[1] / "web/app.js").read_text(encoding="utf-8")
        for forbidden in ["setInterval", "localStorage", "sessionStorage", "innerHTML"]:
            self.assertNotIn(forbidden, source)
        self.assertIn('el("run").addEventListener("click"', source)
        self.assertIn("AbortController", source); self.assertIn("expires_at", source)


if __name__ == "__main__": unittest.main()
