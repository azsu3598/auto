from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
    def test_expected_egress_is_required_before_online_aws_credentials_are_used(self):
        factory = Mock()
        report = diagnose(environment=GOOD_ENV, online=True, aws=True, kiwoom_factory=factory)
        self.assertFalse(report.ok)
        factory.assert_not_called()

    def test_mismatched_egress_blocks_broker_and_storage_probes(self):
        factory = Mock()
        with patch('stock_automation.integration_checks.storage_probes') as storage:
            report = diagnose(environment={**GOOD_ENV, 'EXPECTED_EGRESS_IP': '203.0.113.1'},
                online=True, aws=True, egress_probe=lambda: '203.0.113.2',
                kiwoom_factory=factory, write_probes=True)
        self.assertFalse(report.ok)
        factory.assert_not_called()
        storage.assert_not_called()
        self.assertNotIn('203.0.113.', str(report.to_dict()))

    def test_matching_egress_and_read_probes_pass_without_logging_ip(self):
        report = diagnose(environment={**GOOD_ENV, 'EXPECTED_EGRESS_IP': '203.0.113.1'},
            online=True, aws=True, egress_probe=lambda: '203.0.113.1\n',
            kiwoom_factory=FakeKiwoom, dart_factory=lambda key: FakeDart())
        self.assertTrue(report.ok)
        self.assertNotIn('203.0.113.1', str(report.to_dict()))

    def test_probe_exception_or_invalid_egress_is_sanitized(self):
        def broken():
            raise RuntimeError('must-not-log-secret')
        for expected, probe in (('invalid', lambda: '203.0.113.1'), ('203.0.113.1', broken),
                                ('203.0.113.1', lambda: '<html>invalid</html>')):
            report = diagnose(environment={**GOOD_ENV, 'EXPECTED_EGRESS_IP': expected},
                online=True, aws=True, egress_probe=probe)
            self.assertFalse(report.ok)
            self.assertNotIn('must-not-log-secret', str(report.to_dict()))

    def test_live_flag_or_offline_mode_cannot_run_mutating_probes(self):
        for env, online in ((GOOD_ENV, False), ({**GOOD_ENV, 'LIVE_ORDER_ENABLED':'1'}, True)):
            with patch('stock_automation.integration_checks.storage_probes') as storage:
                report = diagnose(environment=env, online=online, write_probes=True,
                    kiwoom_factory=FakeKiwoom, dart_factory=lambda key: FakeDart())
                self.assertFalse(report.ok)
                storage.assert_not_called()

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
