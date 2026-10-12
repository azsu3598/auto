from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from stock_automation.order_safety import (
    AccountRiskState,
    AuthorizationStatus,
    LiveOrderPolicy,
    OrderSide,
    UserApproval,
    approval_challenge,
    authorize_live_order,
    build_order_intent,
)

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 7, 15, 20, tzinfo=KST)


def intent(**changes):
    values = {
        "event_id": "EVENT-1",
        "strategy": "CLOSING_BET",
        "side": OrderSide.BUY,
        "code": "123456",
        "name": "테스트",
        "quantity": 10,
        "limit_price": 10_000,
        "reference_price": 10_000,
        "reference_at": NOW,
        "created_at": NOW,
        "account_alias": "main",
    }
    values.update(changes)
    return build_order_intent(**values)


def state(**changes):
    values = {
        "account_alias": "main",
        "available_cash": 600_000,
        "current_exposure": 0,
        "realized_daily_pnl": 0,
        "open_positions": 0,
        "owned_quantity": 0,
        "kill_switch_active": False,
        "observed_account_fingerprint": "fingerprint-main",
        "holdings_reconciled": True,
    }
    values.update(changes)
    return AccountRiskState(**values)


def approval(order):
    return UserApproval(
        intent_id=order.intent_id,
        challenge=approval_challenge(order),
        approved_at=NOW,
        approved_by="USER",
    )


def live_policy(**changes):
    values = {
        "live_order_enabled": True,
        "expected_account_fingerprint": "fingerprint-main",
    }
    values.update(changes)
    return LiveOrderPolicy(**values)


class OrderSafetyTests(unittest.TestCase):
    def test_live_order_is_disabled_by_default_even_with_approval(self):
        order = intent()
        result = authorize_live_order(
            order,
            approval=approval(order),
            state=state(),
            policy=LiveOrderPolicy(),
            checked_at=NOW,
        )
        self.assertEqual(AuthorizationStatus.REJECTED, result.status)
        self.assertIn("LIVE_ORDER_DISABLED", result.reason_codes)

    def test_exact_user_approval_is_required(self):
        order = intent()
        result = authorize_live_order(
            order,
            approval=None,
            state=state(),
            policy=live_policy(),
            checked_at=NOW,
        )
        self.assertIn("USER_APPROVAL_REQUIRED", result.reason_codes)

    def test_changed_price_invalidates_prior_approval(self):
        original = intent()
        changed = intent(limit_price=10_050)
        result = authorize_live_order(
            changed,
            approval=approval(original),
            state=state(),
            policy=live_policy(),
            checked_at=NOW,
        )
        self.assertIn("APPROVAL_INTENT_MISMATCH", result.reason_codes)
        self.assertIn("APPROVAL_CHALLENGE_MISMATCH", result.reason_codes)

    def test_authorizes_only_when_all_gates_pass(self):
        order = intent()
        result = authorize_live_order(
            order,
            approval=approval(order),
            state=state(),
            policy=live_policy(),
            checked_at=NOW + timedelta(seconds=10),
        )
        self.assertTrue(result.authorized)
        self.assertEqual(("ALL_LIVE_ORDER_GATES_PASSED",), result.reason_codes)

    def test_kill_switch_loss_limit_duplicate_and_stale_quote_all_reject(self):
        order = intent()
        risky = state(
            kill_switch_active=True,
            realized_daily_pnl=-10_000,
            already_submitted_intent_ids=frozenset({order.intent_id}),
        )
        result = authorize_live_order(
            order,
            approval=approval(order),
            state=risky,
            policy=live_policy(),
            checked_at=NOW + timedelta(seconds=61),
        )
        self.assertTrue({
            "KILL_SWITCH_ACTIVE",
            "DAILY_LOSS_LIMIT",
            "DUPLICATE_ORDER_INTENT",
            "REFERENCE_QUOTE_STALE",
        }.issubset(result.reason_codes))

    def test_sell_cannot_exceed_verified_holding(self):
        order = intent(side=OrderSide.SELL, quantity=20)
        result = authorize_live_order(
            order,
            approval=approval(order),
            state=state(owned_quantity=10),
            policy=live_policy(),
            checked_at=NOW,
        )
        self.assertIn("SELL_QUANTITY_EXCEEDS_PROGRAM_HOLDING", result.reason_codes)

    def test_account_fingerprint_and_reconciliation_are_mandatory(self):
        order = intent()
        result = authorize_live_order(
            order,
            approval=approval(order),
            state=state(observed_account_fingerprint="wrong", holdings_reconciled=False),
            policy=live_policy(),
            checked_at=NOW,
        )
        self.assertIn("ACCOUNT_FINGERPRINT_MISMATCH", result.reason_codes)
        self.assertIn("HOLDINGS_NOT_RECONCILED", result.reason_codes)

    def test_sell_is_limited_to_program_quantity_above_protected_baseline(self):
        order = intent(side=OrderSide.SELL, quantity=6)
        safe = state(
            owned_quantity=18,
            protected_baseline_quantity=10,
            program_owned_quantity=8,
        )
        result = authorize_live_order(
            order,
            approval=approval(order),
            state=safe,
            policy=live_policy(),
            checked_at=NOW,
        )
        self.assertTrue(result.authorized)

        reduced = authorize_live_order(
            intent(side=OrderSide.SELL, quantity=9),
            approval=approval(intent(side=OrderSide.SELL, quantity=9)),
            state=safe,
            policy=live_policy(),
            checked_at=NOW,
        )
        self.assertIn("SELL_QUANTITY_EXCEEDS_PROGRAM_HOLDING", reduced.reason_codes)


if __name__ == "__main__":
    unittest.main()
