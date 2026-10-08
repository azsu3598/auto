from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from stock_automation.medium_term import (
    MediumTermDecisionType,
    MediumTermEntryAction,
    MediumTermEngine,
    MediumTermExitAction,
    MediumTermQuote,
    MediumTermSnapshot,
    confirm_medium_term_entry,
    review_medium_term_position,
)

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 7, 17, 0, tzinfo=KST)


def quote(**changes) -> MediumTermQuote:
    base = MediumTermQuote(
        code="123456",
        name="중기테스트",
        observed_at=NOW,
        price=11_000,
        trading_value=8_000_000_000,
        market_cap=800_000_000_000,
        nxt_eligible=False,
        ma20=10_500,
        ma60=10_000,
        ma120=9_000,
        ma20_slope_5d=250,
        ma60_slope_10d=180,
        rsi14=58,
        atr14=500,
        volume_ratio20=1.4,
        return20_pct=10,
        return60_pct=20,
        support_price=10_000,
        resistance_price=13_000,
        per=12,
        pbr=1.5,
        roe=14,
        sales=12_000,
        operating_profit=1_100,
        net_income=800,
        fundamental_source="KIWOOM_KA10001",
        fundamental_observed_at=NOW,
        disclosure_checked=True,
        risk_flags=(),
        catalyst="수주 잔고와 실적 추세 유지",
    )
    return replace(base, **changes)


def snapshot(*quotes: MediumTermQuote) -> MediumTermSnapshot:
    return MediumTermSnapshot(
        captured_at=NOW,
        quotes=quotes or (quote(),),
        source="KIWOOM_REST+DART",
    )


class MediumTermEngineTests(unittest.TestCase):
    def test_creates_signal_not_same_day_fill(self):
        decision = MediumTermEngine().evaluate(snapshot(), cash=600_000)

        self.assertEqual(MediumTermDecisionType.SIGNAL, decision.decision)
        self.assertIsNotNone(decision.entry_plan)
        self.assertLessEqual(decision.entry_plan.indicative_amount, 180_000)
        self.assertLess(
            (decision.entry_plan.reference_price - decision.entry_plan.thesis_invalidation)
            * decision.entry_plan.suggested_quantity,
            20_001,
        )
        self.assertEqual(20, decision.entry_plan.review_after_trading_days)
        self.assertEqual(40, decision.entry_plan.maximum_holding_trading_days)
        self.assertTrue(decision.entry_plan.plan_id.startswith("MEDPLAN-"))
        self.assertIn("NEXT_SESSION_CONFIRMATION_REQUIRED", decision.reason_codes)

    def test_same_day_entry_confirmation_is_rejected(self):
        plan = MediumTermEngine().evaluate(snapshot(), cash=600_000).entry_plan
        with self.assertRaisesRegex(ValueError, "later trading date"):
            confirm_medium_term_entry(
                plan,
                observed_at=NOW + timedelta(hours=1),
                observed_price=11_100,
                cash=600_000,
            )

    def test_next_day_price_creates_real_paper_position(self):
        plan = MediumTermEngine().evaluate(snapshot(), cash=600_000).entry_plan
        next_day = NOW + timedelta(days=1, hours=-7, minutes=15)
        result = confirm_medium_term_entry(
            plan,
            observed_at=next_day,
            observed_price=11_100,
            cash=600_000,
        )

        self.assertEqual(MediumTermEntryAction.ENTER, result.action)
        self.assertEqual(next_day, result.position.entry_at)
        self.assertEqual(11_100, result.position.entry_price)
        self.assertLessEqual(result.position.invested_amount, 180_000)
        self.assertTrue(result.position.position_id.startswith("MEDPOS-"))

    def test_entry_is_cancelled_after_large_gap_or_new_disclosure_risk(self):
        plan = MediumTermEngine().evaluate(snapshot(), cash=600_000).entry_plan
        next_day = NOW + timedelta(days=1)
        gap = confirm_medium_term_entry(
            plan,
            observed_at=next_day,
            observed_price=plan.maximum_entry_price + 10,
            cash=600_000,
        )
        risk = confirm_medium_term_entry(
            plan,
            observed_at=next_day,
            observed_price=11_100,
            cash=600_000,
            risk_flags=("DILUTION_EVENT",),
        )

        self.assertEqual(MediumTermEntryAction.CANCEL, gap.action)
        self.assertIn("ENTRY_GAP_TOO_HIGH", gap.reason_codes)
        self.assertEqual(MediumTermEntryAction.CANCEL, risk.action)
        self.assertIn("DISCLOSURE_RISK_AFTER_SIGNAL", risk.reason_codes)

    def test_entry_window_expires_after_next_trading_day(self):
        plan = MediumTermEngine().evaluate(snapshot(), cash=600_000).entry_plan
        result = confirm_medium_term_entry(
            plan,
            observed_at=NOW + timedelta(days=2),
            observed_price=11_100,
            cash=600_000,
            trading_days_since_signal=2,
        )
        self.assertEqual(MediumTermEntryAction.CANCEL, result.action)
        self.assertIn("ENTRY_WINDOW_EXPIRED", result.reason_codes)

    def test_daily_review_stops_partial_takes_profit_and_exits_at_max_hold(self):
        plan = MediumTermEngine().evaluate(snapshot(), cash=600_000).entry_plan
        confirmation = confirm_medium_term_entry(
            plan,
            observed_at=NOW + timedelta(days=1),
            observed_price=11_100,
            cash=600_000,
        )
        position = confirmation.position
        stopped = review_medium_term_position(
            position,
            observed_at=NOW + timedelta(days=2),
            closing_price=position.thesis_invalidation,
            trading_days_held=1,
        )
        partial = review_medium_term_position(
            position,
            observed_at=NOW + timedelta(days=10),
            closing_price=position.target1,
            trading_days_held=7,
        )
        hold_after_partial = review_medium_term_position(
            position,
            observed_at=NOW + timedelta(days=11),
            closing_price=position.target1,
            trading_days_held=8,
            remaining_quantity=partial.remaining_quantity,
        )
        timed = review_medium_term_position(
            position,
            observed_at=NOW + timedelta(days=60),
            closing_price=position.entry_price,
            trading_days_held=40,
            remaining_quantity=partial.remaining_quantity,
        )

        self.assertEqual(MediumTermExitAction.THESIS_STOP, stopped.action)
        self.assertEqual(MediumTermExitAction.PARTIAL_PROFIT, partial.action)
        self.assertEqual(MediumTermExitAction.HOLD, hold_after_partial.action)
        self.assertEqual(MediumTermExitAction.MAX_HOLD_EXIT, timed.action)

    def test_nxt_stock_is_excluded_from_krx_medium_term_universe(self):
        decision = MediumTermEngine().evaluate(
            snapshot(quote(nxt_eligible=True)), cash=600_000
        )
        self.assertEqual(MediumTermDecisionType.NO_TRADE, decision.decision)

    def test_disclosure_check_is_mandatory(self):
        decision = MediumTermEngine().evaluate(
            snapshot(quote(disclosure_checked=False)), cash=600_000
        )
        self.assertEqual(MediumTermDecisionType.NO_TRADE, decision.decision)

    def test_dilution_or_audit_risk_blocks_entry(self):
        for flag in ("DILUTION_EVENT", "AUDIT_RISK"):
            with self.subTest(flag=flag):
                decision = MediumTermEngine().evaluate(
                    snapshot(quote(risk_flags=(flag,))), cash=600_000
                )
                self.assertEqual(MediumTermDecisionType.NO_TRADE, decision.decision)

    def test_overextended_daily_chart_is_rejected(self):
        decision = MediumTermEngine().evaluate(
            snapshot(quote(price=13_000, return20_pct=28)), cash=600_000
        )
        self.assertEqual(MediumTermDecisionType.NO_TRADE, decision.decision)

    def test_stale_fundamentals_fail_closed(self):
        stale = NOW - timedelta(days=15)
        decision = MediumTermEngine().evaluate(
            snapshot(quote(fundamental_observed_at=stale)), cash=600_000
        )
        self.assertEqual(MediumTermDecisionType.NO_TRADE, decision.decision)


if __name__ == "__main__":
    unittest.main()
