from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from stock_automation.day_trade import (
    DayTradeDecisionType,
    DayTradeEngine,
    DayTradeExitAction,
    DayTradeObservation,
    DayTradeQuote,
    DayTradeSnapshot,
)


KST = timezone(timedelta(hours=9))


def quote(**overrides) -> DayTradeQuote:
    values = {
        "code": "123456",
        "name": "단타테스트",
        "observed_at": datetime(2026, 10, 12, 10, 30, tzinfo=KST),
        "market": "KOSDAQ",
        "price": 20_000,
        "high_price": 20_100,
        "low_price": 19_300,
        "trading_value": 30_000_000_000,
        "day_change_pct": 4.0,
        "five_min_ma20": 19_700,
        "five_min_ma20_slope": 25.0,
        "vwap": 19_750,
        "five_min_volume_ratio": 2.0,
        "support_price": 19_600,
        "nxt_eligible": False,
        "catalyst": "당일 공급계약 공시",
        "catalyst_verified": True,
        "theme": "robot",
        "breakout_holds": True,
        "higher_lows": True,
        "last_fifteen_min_return_pct": 0.8,
        "institution_net": 100_000_000,
        "program_net": 50_000_000,
        "best_ask": 20_010,
    }
    values.update(overrides)
    return DayTradeQuote(**values)


def snapshot(*quotes: DayTradeQuote, **overrides) -> DayTradeSnapshot:
    values = {
        "captured_at": datetime(2026, 10, 12, 10, 30, 30, tzinfo=KST),
        "kospi_change_pct": 0.2,
        "kosdaq_change_pct": 0.5,
        "quotes": tuple(quotes),
        "source": "fixture",
    }
    values.update(overrides)
    return DayTradeSnapshot(**values)


class DayTradeEngineTests(unittest.TestCase):
    def test_creates_isolated_paper_position(self):
        decision = DayTradeEngine().evaluate(snapshot(quote()), cash=600_000)
        self.assertEqual(DayTradeDecisionType.BUY, decision.decision)
        self.assertTrue(decision.position.position_id.startswith("DTP-"))
        self.assertLessEqual(decision.position.invested_amount, 150_000)
        self.assertLessEqual(
            (decision.position.entry_price - decision.position.emergency_stop)
            * decision.position.quantity,
            8_000,
        )
        self.assertEqual("day-trade-v0.2", decision.rule_version)

    def test_unverified_catalyst_is_scored_instead_of_rejected(self):
        engine = DayTradeEngine()
        confirmed = engine.evaluate(snapshot(quote()), cash=600_000).candidates[0]
        for overrides in (
            {"catalyst": "", "catalyst_verified": False},
            {"catalyst": "  ", "catalyst_verified": True},
        ):
            with self.subTest(overrides=overrides):
                decision = engine.evaluate(snapshot(quote(**overrides)), cash=600_000)
                self.assertEqual(DayTradeDecisionType.BUY, decision.decision)
                candidate = decision.candidates[0]
                self.assertAlmostEqual(confirmed.score - 10.0, candidate.score)
                self.assertIn("CATALYST_UNKNOWN", candidate.risks)
                self.assertNotIn("CATALYST_CONFIRMED", candidate.reasons)
        self.assertIn("CATALYST_CONFIRMED", confirmed.reasons)
        self.assertNotIn("CATALYST_UNKNOWN", confirmed.risks)

    def test_missing_catalyst_cannot_lift_a_weak_chart_over_the_minimum(self):
        weak = quote(
            catalyst="", catalyst_verified=False, breakout_holds=False,
            reclaimed_ma20=True, higher_lows=False, five_min_volume_ratio=1.4,
            institution_net=None, program_net=None,
        )
        decision = DayTradeEngine().evaluate(snapshot(weak), cash=600_000)
        self.assertEqual(DayTradeDecisionType.NO_TRADE, decision.decision)
        self.assertLess(decision.candidates[0].score, 65.0)

    def test_nxt_or_market_crash_is_no_trade(self):
        nxt = DayTradeEngine().evaluate(snapshot(quote(nxt_eligible=True)), cash=600_000)
        crash = DayTradeEngine().evaluate(
            snapshot(quote(), kosdaq_change_pct=-3.1), cash=600_000
        )
        self.assertEqual(DayTradeDecisionType.NO_TRADE, nxt.decision)
        self.assertEqual(DayTradeDecisionType.NO_TRADE, crash.decision)

    def test_entry_window_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "approved window"):
            DayTradeEngine().evaluate(
                snapshot(
                    quote(),
                    captured_at=datetime(2026, 10, 12, 15, 0, tzinfo=KST),
                ),
                cash=600_000,
            )

    def test_position_is_forced_out_same_day(self):
        position = DayTradeEngine().evaluate(snapshot(quote()), cash=600_000).position
        result = DayTradeEngine().review(
            position,
            DayTradeObservation(
                observed_at=datetime(2026, 10, 12, 15, 10, tzinfo=KST),
                price=20_100,
            ),
        )
        self.assertEqual(DayTradeExitAction.FULL_EXIT, result.action)
        self.assertEqual(("MANDATORY_SAME_DAY_EXIT",), result.reason_codes)

    def test_missed_close_exits_at_first_next_observation(self):
        position = DayTradeEngine().evaluate(snapshot(quote()), cash=600_000).position
        result = DayTradeEngine().review(
            position,
            DayTradeObservation(
                observed_at=datetime(2026, 10, 13, 9, 5, tzinfo=KST),
                price=19_900,
            ),
        )
        self.assertEqual(DayTradeExitAction.FULL_EXIT, result.action)
        self.assertEqual(("MANDATORY_SAME_DAY_EXIT",), result.reason_codes)

    def test_soft_stop_requires_two_candle_confirmation(self):
        position = DayTradeEngine().evaluate(snapshot(quote()), cash=600_000).position
        first = DayTradeEngine().review(
            position,
            DayTradeObservation(
                observed_at=datetime(2026, 10, 12, 11, 0, tzinfo=KST),
                price=position.stop_price - 10,
                five_min_closed_below_stop=True,
                following_candle_reclaimed_stop=None,
            ),
        )
        confirmed = DayTradeEngine().review(
            position,
            DayTradeObservation(
                observed_at=datetime(2026, 10, 12, 11, 5, tzinfo=KST),
                price=position.stop_price - 20,
                five_min_closed_below_stop=True,
                following_candle_reclaimed_stop=False,
            ),
        )
        self.assertEqual(DayTradeExitAction.HOLD, first.action)
        self.assertEqual(DayTradeExitAction.STOP_LOSS, confirmed.action)


if __name__ == "__main__":
    unittest.main()
