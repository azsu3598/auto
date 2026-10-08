from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from stock_automation.exit_engine import review_position
from stock_automation.models import (
    ExitAction,
    ExitObservation,
    Position,
    Session,
    StopMode,
)

KST = timezone(timedelta(hours=9))


def position(stop_mode: StopMode = StopMode.FIVE_MIN_CONFIRMED) -> Position:
    return Position(
        position_id="POS-1",
        strategy="CLOSING_BET",
        session=Session.KRX_1520,
        code="123456",
        name="테스트",
        entry_at=datetime(2026, 10, 6, 15, 20, tzinfo=KST),
        entry_price=10_000,
        quantity=20,
        invested_amount=200_000,
        stop_mode=stop_mode,
        stop_price=9_700,
        emergency_stop=9_500,
        target1=10_450,
        target2=10_750,
    )


class ExitEngineTests(unittest.TestCase):
    def test_single_tick_below_soft_stop_does_not_exit(self):
        result = review_position(
            position(),
            ExitObservation(datetime(2026, 10, 7, 9, 5, tzinfo=KST), 9_680),
            scheduled_exit_at=datetime(2026, 10, 7, 9, 10, tzinfo=KST),
        )
        self.assertEqual(ExitAction.HOLD, result.action)

    def test_confirmed_stop_uses_first_observed_price(self):
        result = review_position(
            position(),
            ExitObservation(
                datetime(2026, 10, 7, 9, 7, tzinfo=KST),
                9_620,
                five_min_closed_below_stop=True,
                following_candle_reclaimed_stop=False,
            ),
            scheduled_exit_at=datetime(2026, 10, 7, 9, 10, tzinfo=KST),
        )
        self.assertEqual(ExitAction.STOP_LOSS, result.action)
        self.assertEqual(9_620, result.execution_price)

    def test_emergency_floor_exits_without_confirmation(self):
        result = review_position(
            position(),
            ExitObservation(datetime(2026, 10, 7, 9, 2, tzinfo=KST), 9_400),
            scheduled_exit_at=datetime(2026, 10, 7, 9, 10, tzinfo=KST),
        )
        self.assertEqual(ExitAction.STOP_LOSS, result.action)
        self.assertIn("EMERGENCY_INVALIDATION", result.reason_codes)

    def test_exits_at_verified_0910_price(self):
        result = review_position(
            position(),
            ExitObservation(datetime(2026, 10, 7, 9, 10, 5, tzinfo=KST), 10_200),
            scheduled_exit_at=datetime(2026, 10, 7, 9, 10, tzinfo=KST),
        )
        self.assertEqual(ExitAction.SCHEDULED_EXIT, result.action)
        self.assertEqual(4_000, result.realized_pnl)

    def test_0910_liquidation_precedes_partial_profit(self):
        result = review_position(
            position(),
            ExitObservation(datetime(2026, 10, 7, 9, 10, 5, tzinfo=KST), 10_500),
            scheduled_exit_at=datetime(2026, 10, 7, 9, 10, tzinfo=KST),
        )
        self.assertEqual(ExitAction.SCHEDULED_EXIT, result.action)
        self.assertEqual(20, result.execution_quantity)
        self.assertEqual(0, result.remaining_quantity)

    def test_target1_can_only_be_taken_once(self):
        result = review_position(
            position(),
            ExitObservation(datetime(2026, 10, 7, 9, 7, tzinfo=KST), 10_500),
            scheduled_exit_at=datetime(2026, 10, 7, 9, 10, tzinfo=KST),
            remaining_quantity=10,
        )
        self.assertEqual(ExitAction.HOLD, result.action)
        self.assertEqual(10, result.remaining_quantity)


if __name__ == "__main__":
    unittest.main()
