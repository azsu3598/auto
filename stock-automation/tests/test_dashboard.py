from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from stock_automation.dashboard import (
    FixtureDashboardRepository,
    STATIC_DIR,
    _decode_item,
    dashboard_payload,
)

KST = timezone(timedelta(hours=9))


class DashboardTests(unittest.TestCase):
    def test_static_console_assets_are_packaged_in_source_tree(self):
        self.assertTrue((STATIC_DIR / "index.html").is_file())
        self.assertTrue((STATIC_DIR / "styles.css").is_file())
        self.assertTrue((STATIC_DIR / "app.js").is_file())

    def test_builds_safe_summary_from_paper_ledger(self):
        position = {
            "code": "123456",
            "name": "샘플",
            "entry_price": 10_000,
            "quantity": 10,
            "stop_price": 9_700,
            "target1": 10_450,
            "target2": 10_750,
            "entry_at": "2026-10-08T15:20:00+09:00",
        }
        items = [{
            "pk": "WALLET#CLOSING_BET#KRX_1520",
            "available_cash": 500_000,
            "invested_principal": 100_000,
            "realized_pnl": -1_200,
            "fees_taxes": 300,
        }, {
            "pk": "OPEN#CLOSING_BET#KRX_1520",
            "remaining_quantity": 8,
            "payload_json": json.dumps(position),
        }]

        with patch.dict(os.environ, {}, clear=True):
            result = dashboard_payload(
                items, now=datetime(2026, 10, 8, 16, 0, tzinfo=KST)
            )

        self.assertEqual("LIVE_LOCKED", result["mode"])
        self.assertFalse(result["live_transition"]["allowed"])
        self.assertEqual(500_000, result["metrics"]["available_cash"])
        self.assertEqual(-1_200, result["metrics"]["realized_pnl"])
        self.assertEqual(8, result["positions"][0]["remaining_quantity"])

    def test_detects_live_environment_flag_as_a_warning(self):
        with patch.dict(os.environ, {"LIVE_ORDER_ENABLED": "1"}, clear=True):
            result = dashboard_payload([], now=datetime(2026, 10, 8, tzinfo=KST))

        self.assertEqual("LIVE_FLAG_DETECTED", result["mode"])
        self.assertTrue(any("실주문" in warning for warning in result["warnings"]))
        self.assertFalse(result["live_transition"]["allowed"])

    def test_decodes_dynamodb_and_loads_fixture(self):
        decoded = _decode_item({
            "pk": {"S": "WALLET#TEST"},
            "available_cash": {"N": "600000"},
            "enabled": {"BOOL": True},
        })
        self.assertEqual(600_000, decoded["available_cash"])
        self.assertTrue(decoded["enabled"])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text('[{"pk":"WALLET#TEST"}]', encoding="utf-8")
            self.assertEqual("WALLET#TEST", FixtureDashboardRepository(path).items()[0]["pk"])


if __name__ == "__main__":
    unittest.main()
