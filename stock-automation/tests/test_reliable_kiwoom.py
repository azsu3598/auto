import unittest

from stock_automation.providers.reliable import KiwoomRetryPolicy, ReliableKiwoomClient


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class ApiFailure(Exception):
    def __init__(self, *, return_code=None, status_code=None):
        self.return_code = return_code
        self.status_code = status_code


class FakeClient:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def fetch_page(self, **kwargs):
        self.calls += 1
        value = self.results.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class ReliableKiwoomClientTests(unittest.TestCase):
    def demo_client(self, results, clock, **kwargs):
        return ReliableKiwoomClient(
            FakeClient(results),
            KiwoomRetryPolicy(per_api_min_interval_seconds=1, **kwargs),
            monotonic=clock.monotonic, sleep=clock.sleep,
        )

    def test_demo_pagination_spaces_same_tr_by_one_second(self):
        clock = FakeClock()
        client = self.demo_client(["page1", "page2"], clock)
        client.fetch_page(api_id="ka10099", path="/api/dostk/stkinfo")
        client.fetch_page(api_id="ka10099", path="/api/dostk/stkinfo", cont_yn="Y")
        self.assertEqual(clock.now, 1)

    def test_demo_distinct_trs_keep_global_pacing_without_extra_second(self):
        clock = FakeClock()
        client = self.demo_client([1, 2, 3], clock)
        for api in ("ka10001", "ka10080", "ka10001"):
            client.fetch_page(api_id=api)
        self.assertEqual(clock.sleeps, [0.25, 0.75])

    def test_demo_failed_attempt_is_also_counted_for_tr_limit(self):
        clock = FakeClock()
        client = self.demo_client([ApiFailure(status_code=429), "ok"], clock,
                                  initial_backoff_seconds=0)
        self.assertEqual(client.fetch_page(api_id="ka10099"), "ok")
        self.assertEqual(clock.now, 1)

    def test_already_slow_tr_response_does_not_add_unnecessary_wait(self):
        clock = FakeClock()
        client = self.demo_client([1, 2], clock)
        client.fetch_page(api_id="ka10099")
        clock.now += 2
        client.fetch_page(api_id="ka10099")
        self.assertEqual(clock.sleeps, [])

    def test_negative_per_tr_interval_is_invalid(self):
        with self.assertRaises(ValueError):
            KiwoomRetryPolicy(per_api_min_interval_seconds=-1)

    def test_non_finite_intervals_cannot_bypass_pacing(self):
        for value in (float("nan"), float("inf")):
            for field in ("min_interval_seconds", "per_api_min_interval_seconds",
                          "initial_backoff_seconds", "maximum_backoff_seconds"):
                with self.subTest(value=value, field=field), self.assertRaises(ValueError):
                    KiwoomRetryPolicy(**{field: value})

    def test_rate_limit_is_retried_with_bounded_backoff(self):
        clock = FakeClock()
        raw = FakeClient([ApiFailure(return_code=1700), ApiFailure(status_code=429), "ok"])
        client = ReliableKiwoomClient(
            raw,
            KiwoomRetryPolicy(min_interval_seconds=0.25, max_attempts=4, initial_backoff_seconds=1),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        self.assertEqual("ok", client.fetch_page(api_id="ka10099"))
        self.assertEqual(3, raw.calls)
        self.assertEqual([1, 2], clock.sleeps)

    def test_non_transient_business_error_fails_immediately(self):
        raw = FakeClient([ApiFailure(return_code=1501)])
        client = ReliableKiwoomClient(raw, KiwoomRetryPolicy(min_interval_seconds=0))
        with self.assertRaises(ApiFailure):
            client.fetch_page(api_id="ka10099")
        self.assertEqual(1, raw.calls)

    def test_successive_calls_are_paced(self):
        clock = FakeClock()
        raw = FakeClient(["first", "second"])
        client = ReliableKiwoomClient(
            raw,
            KiwoomRetryPolicy(min_interval_seconds=0.5),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )
        self.assertEqual("first", client.fetch_page())
        self.assertEqual("second", client.fetch_page())
        self.assertEqual([0.5], clock.sleeps)

    def test_read_retry_wrapper_refuses_order_endpoint(self):
        raw = FakeClient(["must-not-be-used"])
        client = ReliableKiwoomClient(raw)
        with self.assertRaisesRegex(RuntimeError, "read-only"):
            client.fetch_page(api_id="kt10000", path="/api/dostk/ordr", body={})
        self.assertEqual(0, raw.calls)


if __name__ == "__main__":
    unittest.main()
