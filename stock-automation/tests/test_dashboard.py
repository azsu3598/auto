from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from stock_automation.dashboard import (
    CombinedDashboardRepository,
    FixtureDashboardRepository,
    STATIC_DIR,
    _decode_item,
    dashboard_payload,
)

KST = timezone(timedelta(hours=9))


class DashboardTests(unittest.TestCase):
    def test_combines_paper_and_live_read_only_repositories(self):
        class Repository:
            def __init__(self, rows):
                self.rows = rows

            def items(self):
                return self.rows

        combined = CombinedDashboardRepository((
            Repository([{"pk": "WALLET#CLOSING_BET"}]),
            Repository([{"pk": "CONTROL#LIVE"}]),
        ))
        self.assertEqual(
            ["WALLET#CLOSING_BET", "CONTROL#LIVE"],
            [row["pk"] for row in combined.items()],
        )

    def test_static_console_assets_are_packaged_in_source_tree(self):
        self.assertTrue((STATIC_DIR / "index.html").is_file())
        self.assertTrue((STATIC_DIR / "styles.css").is_file())
        self.assertTrue((STATIC_DIR / "app.js").is_file())
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
        self.assertIn('id="safety-center"', html)
        self.assertIn('id="live-orders"', html)
        self.assertIn('class="mobile-nav"', html)
        self.assertIn(".live-order-card", css)

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
        self.assertTrue(result["strategy_modes"][0]["paper_selected"])
        self.assertFalse(result["strategy_modes"][0]["live_selected"])

    def test_paper_and_live_mode_selection_are_independent_not_exclusive(self):
        items = [{
            "pk": "CONTROL#STRATEGY_MODE#CLOSING_BET",
            "paper_enabled": True,
            "live_enabled": True,
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = dashboard_payload(items, now=datetime(2026, 10, 12, tzinfo=KST))
        closing = result["strategy_modes"][0]
        self.assertTrue(closing["paper_selected"])
        self.assertTrue(closing["live_selected"])
        self.assertFalse(closing["live_effective"])
        self.assertTrue(closing["controls_locked"])

    def test_daily_equity_history_is_sorted_and_separated_by_mode(self):
        items = [{
            "pk": "EQUITY#PAPER#2026-10-02",
            "mode": "PAPER",
            "recorded_at": "2026-10-02T15:30:00+09:00",
            "total_assets": 601_000,
        }, {
            "pk": "EQUITY#PAPER#2026-10-01",
            "mode": "PAPER",
            "recorded_at": "2026-10-01T15:30:00+09:00",
            "total_assets": 600_000,
        }, {
            "pk": "EQUITY#LIVE#2026-10-01",
            "mode": "LIVE",
            "recorded_at": "2026-10-01T15:30:00+09:00",
            "total_assets": 500_000,
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = dashboard_payload(items, now=datetime(2026, 10, 12, tzinfo=KST))
        self.assertEqual(
            [600_000, 601_000],
            [row["total_assets"] for row in result["equity_history"]["PAPER"]],
        )
        self.assertEqual(500_000, result["equity_history"]["LIVE"][0]["total_assets"])

    def test_trade_reasons_are_extracted_and_translated(self):
        payload = {
            "decision": "BUY",
            "position": {"code": "123456", "name": "이유테스트"},
            "reason_codes": ["TOP_SCORE_SELECTED", "PAPER_EXECUTION_ONLY"],
            "candidates": [{
                "code": "123456",
                "reasons": ["HIGH_TRADING_VALUE", "ABOVE_5M_MA20", "CATALYST_CONFIRMED"],
            }],
        }
        with patch.dict(os.environ, {}, clear=True):
            result = dashboard_payload([{
                "pk": "2026-10-12:KRX_1520:CLOSING_BET",
                "decided_at": "2026-10-12T15:20:00+09:00",
                "payload_json": json.dumps(payload),
            }], now=datetime(2026, 10, 12, 16, 0, tzinfo=KST))
        reasons = result["recent_events"][0]["reasons"]
        self.assertEqual(
            ["종가배팅 종합점수 1위", "거래대금 충분", "5분봉 20이평 위", "당일 촉매 확인"],
            reasons,
        )

    def test_no_trade_reasons_are_translated(self):
        with patch.dict(os.environ, {}, clear=True):
            result = dashboard_payload([{
                "pk": "2026-10-12:KRX_1520:CLOSING_BET",
                "decided_at": "2026-10-12T15:20:00+09:00",
                "decision": "NO_TRADE",
                "reason_codes": ["NO_QUALIFYING_CANDIDATE"],
                "payload_json": json.dumps({"decision": "NO_TRADE"}),
            }], now=datetime(2026, 10, 12, 16, 0, tzinfo=KST))
        self.assertEqual(
            ["종가배팅 기준 충족 종목 없음"],
            result["recent_events"][0]["reasons"],
        )

    def test_labels_day_trade_wallet_position_and_event_separately(self):
        items = [{
            "pk": "WALLET#DAY_TRADE",
            "available_cash": 600_000,
        }, {
            "pk": "OPEN#DAY_TRADE",
            "remaining_quantity": 3,
            "payload_json": json.dumps({
                "code": "123456", "name": "단타", "quantity": 3,
                "entry_price": 20_000,
            }),
        }, {
            "pk": "DAY#2026-10-12T1030#DAY_TRADE_SCAN",
            "decision": "BUY",
            "decided_at": "2026-10-12T10:30:00+09:00",
            "payload_json": json.dumps({"name": "단타", "entry_price": 20_000}),
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = dashboard_payload(items, now=datetime(2026, 10, 12, 11, 0, tzinfo=KST))
        self.assertEqual("장중 단타", result["wallets"][0]["strategy"])
        self.assertEqual("장중 단타", result["positions"][0]["strategy"])
        self.assertEqual("단타", result["recent_events"][0]["type"])

    def test_detects_live_environment_flag_as_a_warning(self):
        with patch.dict(os.environ, {"LIVE_ORDER_ENABLED": "1"}, clear=True):
            result = dashboard_payload([], now=datetime(2026, 10, 8, tzinfo=KST))

        self.assertEqual("LIVE_FLAG_DETECTED", result["mode"])
        self.assertTrue(any("실주문" in warning for warning in result["warnings"]))
        self.assertFalse(result["live_transition"]["allowed"])

    def test_builds_live_safety_center_without_exposing_account_identity(self):
        intent = {
            "strategy": "CLOSING_BET", "side": "BUY", "code": "123456",
            "name": "안전테스트", "quantity": 10, "limit_price": 20_000,
        }
        items = [{
            "pk": "CONTROL#LIVE", "status": "KILL_SWITCH_ON",
            "account_alias": "private-alias",
        }, {
            "pk": "CONTROL#ACCOUNT_GUARD", "account_alias": "private-alias",
            "account_fingerprint": "private-fingerprint",
            "protected_holdings_json": json.dumps({"005930": 10}),
        }, {
            "pk": "LIVE_ORDER#ORDER-1", "status": "PARTIALLY_FILLED",
            "intent_json": json.dumps(intent, ensure_ascii=False),
            "broker_order_no": "777", "last_filled_quantity": 6,
            "remaining_quantity": 4,
            "last_reconciled_at": "2026-10-12T14:50:00+09:00",
            "updated_at": "2026-10-12T14:50:00+09:00",
        }]
        with patch.dict(os.environ, {}, clear=True):
            result = dashboard_payload(
                items, now=datetime(2026, 10, 12, 15, 0, tzinfo=KST)
            )
        self.assertEqual("safe", result["live_safety"]["overall"])
        self.assertTrue(result["live_safety"]["kill_switch_active"])
        self.assertTrue(result["live_safety"]["account_guard_locked"])
        self.assertEqual(1, result["live_safety"]["active_orders"])
        self.assertEqual("부분체결", result["live_orders"][0]["state_label"])
        self.assertEqual(4, result["live_orders"][0]["remaining_quantity"])
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("private-alias", serialized)
        self.assertNotIn("private-fingerprint", serialized)

    def test_unknown_or_ambiguous_live_state_is_not_presented_as_safe(self):
        with patch.dict(os.environ, {}, clear=True):
            empty = dashboard_payload([], now=datetime(2026, 10, 12, tzinfo=KST))
            uncertain = dashboard_payload([{
                "pk": "LIVE_ORDER#ORDER-UNKNOWN", "status": "UNCERTAIN",
                "intent_json": json.dumps({
                    "strategy": "CLOSING_BET", "side": "BUY", "code": "123456",
                    "name": "확인필요", "quantity": 1, "limit_price": 10_000,
                }),
                "uncertainty_reason": "TimeoutError: do not retry",
                "updated_at": "2026-10-12T15:00:00+09:00",
            }], now=datetime(2026, 10, 12, 15, 1, tzinfo=KST))
        self.assertEqual("blocked", empty["live_safety"]["overall"])
        self.assertEqual("danger", uncertain["live_safety"]["overall"])
        self.assertEqual(1, uncertain["live_safety"]["ambiguous_orders"])
        self.assertTrue(any("실주문 상태" in row for row in uncertain["warnings"]))

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
