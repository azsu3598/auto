from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from service import RecommendationService, SnapshotFileSource
from fixtures import NOW, snapshot


class Source:
    def __init__(self): self.calls = 0
    def load(self, deadline): self.calls += 1; return snapshot()


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.source = Source(); self.now = NOW; self.tick = 0
        self.service = RecommendationService(self.source, clock=lambda: self.now, monotonic=lambda: self.tick)

    def test_unconnected_source_is_blocked_without_fake_fallback(self):
        status, result = RecommendationService().request(str(uuid4()))
        self.assertEqual(status, 503); self.assertEqual(result["reason"], "DATA_SOURCE_NOT_CONNECTED")

    def test_invalid_request_ids_never_read_source(self):
        for value in [None, {}, "-" * 36, "", "00000000-0000-0000-0000-000000000000"]:
            self.assertEqual(self.service.request(value)[0], 400)
        self.assertEqual(self.source.calls, 0)

    def test_duplicate_id_uses_only_still_valid_result(self):
        request_id = str(uuid4())
        first = self.service.request(request_id); second = self.service.request(request_id)
        self.assertEqual(first, second); self.assertEqual(self.source.calls, 1)

    def test_expired_result_not_returned_as_current(self):
        request_id = str(uuid4()); self.service.request(request_id)
        self.now += timedelta(seconds=100); self.tick = 100
        status, result = self.service.request(request_id)
        self.assertEqual(status, 422); self.assertNotIn("candidates", result)

    def test_cooldown_and_busy_requests_do_not_read_source(self):
        self.service.request(str(uuid4()))
        self.assertEqual(self.service.request(str(uuid4()))[0], 429)
        self.assertEqual(self.source.calls, 1)
        self.service.lock.acquire()
        try: self.assertEqual(self.service.request(str(uuid4()))[0], 429)
        finally: self.service.lock.release()

    def test_provider_errors_are_sanitized_and_lock_released(self):
        def fail(deadline): raise RuntimeError("secret/private/account")
        self.source.load = fail
        status, result = self.service.request(str(uuid4()))
        self.assertEqual(status, 503); self.assertNotIn("secret", json.dumps(result))
        self.assertFalse(self.service.lock.locked())

    def test_provider_timeout_is_not_no_trade(self):
        def fail(deadline): raise TimeoutError
        self.source.load = fail
        status, result = self.service.request(str(uuid4()))
        self.assertEqual(status, 504); self.assertEqual(result["status"], "TIMEOUT")

    def test_over_budget_completion_is_discarded(self):
        def slow(deadline): self.tick = deadline + 1; return snapshot()
        self.source.load = slow
        self.assertEqual(self.service.request(str(uuid4()))[0], 504)

    def test_input_file_is_read_only_and_nonfinite_json_rejected(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fictional.json"
            original = json.dumps(snapshot()).encode(); path.write_bytes(original)
            self.assertTrue(SnapshotFileSource(path).load(time.monotonic() + 5)["is_sample"])
            self.assertEqual(path.read_bytes(), original)
            path.write_text('{"bad": NaN}', encoding="utf-8")
            with self.assertRaises(ValueError): SnapshotFileSource(path).load(time.monotonic() + 5)


if __name__ == "__main__": unittest.main()
