from __future__ import annotations

import unittest
from types import SimpleNamespace

from stock_automation.doctor import diagnose


GOOD_ENV = {
    "KIWOOM_MODE": "demo",
    "APP_KEY_MOCK": "demo-key",
    "APP_SECRET_MOCK": "demo-secret",
    "DART_API_KEY": "d" * 40,
    "NOTIFICATION_CHANNEL": "telegram",
    "NOTIFICATION_SECRET_ARN": "arn:secret",
    "PAPER_BUCKET": "bucket",
    "PAPER_TABLE": "table",
    "TRADING_CALENDAR_KEY": "config/calendar/current.json",
    "STARTING_CASH": "600000",
    "BUY_FEE_BPS": "1",
    "SELL_FEE_BPS": "1",
    "SELL_TAX_BPS": "18",
}


class FakeKiwoom:
    def fetch_page(self, **kwargs):
        return SimpleNamespace(body={"return_code": 0, "list": [{"code": "005930"}]})


class FakeDart:
    def corporation_codes(self):
        return {"005930": "00126380"}


class DoctorTests(unittest.TestCase):
    def test_offline_aws_configuration_passes_without_exposing_values(self):
        report = diagnose(environment=GOOD_ENV, aws=True)
        self.assertTrue(report.ok)
        rendered = str(report.to_dict())
        self.assertNotIn("demo-secret", rendered)
        self.assertNotIn("d" * 40, rendered)

    def test_online_read_only_probes_pass(self):
        report = diagnose(
            environment=GOOD_ENV,
            online=True,
            kiwoom_factory=FakeKiwoom,
            dart_factory=lambda key: FakeDart(),
        )
        self.assertTrue(report.ok)

    def test_real_mode_or_order_gate_fails(self):
        env = {**GOOD_ENV, "KIWOOM_MODE": "real", "KIWOOM_MCP_ALLOW_ORDERS": "1"}
        report = diagnose(environment=env)
        self.assertFalse(report.ok)
        failed = {row.name for row in report.checks if not row.ok}
        self.assertEqual({"paper_mode", "order_gate_disabled"}, failed)

    def test_online_probe_failure_is_reported_without_secret(self):
        def broken():
            raise RuntimeError("network unavailable")

        report = diagnose(
            environment=GOOD_ENV,
            online=True,
            kiwoom_factory=broken,
            dart_factory=lambda key: FakeDart(),
        )
        self.assertFalse(report.ok)
        self.assertNotIn("demo-secret", str(report.to_dict()))


if __name__ == "__main__":
    unittest.main()
