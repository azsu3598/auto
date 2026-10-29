from __future__ import annotations

import unittest

from stock_automation.config import StrategyConfig
from stock_automation.risk import (
    ATR_UNAVAILABLE,
    STOP_TOO_WIDE,
    _tick_size,
    atr_stop_rejection,
    build_position_plan,
)

POLICY = StrategyConfig().atr_stop_policy


def plan(entry: int, support: int, atr14: float | None, cash: int = 600_000):
    return build_position_plan(
        cash=cash,
        entry_price=entry,
        support_price=support,
        max_allocation_pct=0.40,
        max_loss=10_000,
        atr14=atr14,
        atr_policy=POLICY,
    )


class AtrStopPlanTests(unittest.TestCase):
    def test_closing_config_carries_the_work_order_values(self):
        self.assertEqual(
            (0.5, 0.5, 1.5, 5.0, 7.0),
            (
                POLICY.soft_atr_mult,
                POLICY.hard_atr_mult,
                POLICY.min_stop_pct,
                POLICY.max_stop_pct,
                POLICY.max_hard_stop_pct,
            ),
        )
        self.assertEqual("closing-v0.4", StrategyConfig().rule_version)

    def test_small_atr_uses_the_minimum_stop_distance(self):
        result = plan(20_000, 19_900, 200.0)
        # max(100 support, 0.5*200 ATR, 1.5% = 300) -> 300.
        self.assertEqual(19_700, result.stop_price)
        self.assertEqual(19_600, result.emergency_stop)
        self.assertEqual(12, result.quantity)  # 40% allocation caps before risk
        self.assertLessEqual(result.risk_amount, 10_000)

    def test_large_atr_widens_the_stop_and_shrinks_the_quantity(self):
        small = plan(20_000, 19_900, 200.0)
        result = plan(20_000, 19_900, 1_200.0)
        # 0.5 * ATR = 600 > support distance and 1.5%.
        self.assertEqual(20_000 - 600, result.stop_price)
        self.assertEqual(19_400 - 600, result.emergency_stop)
        self.assertEqual(10_000 // 1_200, result.quantity)
        self.assertLess(result.quantity, small.quantity)
        self.assertLessEqual(result.risk_amount, 10_000)
        self.assertEqual(20_900, result.target1)  # entry + 600 * 1.5
        self.assertEqual(21_500, result.target2)  # entry + 600 * 2.5

    def test_stop_wider_than_five_percent_is_refused(self):
        # Support 6% below the entry.
        self.assertEqual(
            STOP_TOO_WIDE,
            atr_stop_rejection(entry_price=20_000, support_price=18_800, atr14=200.0, policy=POLICY),
        )
        self.assertIsNone(plan(20_000, 18_800, 200.0))

    def test_emergency_stop_wider_than_seven_percent_is_refused(self):
        # Soft stop 4% below, emergency another 0.5 * 1,600 = 8% below the entry.
        self.assertEqual(
            STOP_TOO_WIDE,
            atr_stop_rejection(entry_price=20_000, support_price=19_200, atr14=1_600.0, policy=POLICY),
        )
        self.assertIsNone(plan(20_000, 19_200, 1_600.0))

    def test_missing_atr_is_refused(self):
        for atr14 in (None, 0.0, -5.0, float("nan")):
            self.assertEqual(
                ATR_UNAVAILABLE,
                atr_stop_rejection(entry_price=20_000, support_price=19_900, atr14=atr14, policy=POLICY),
            )
            self.assertIsNone(plan(20_000, 19_900, atr14))

    def test_stops_round_down_to_the_tick_near_tick_boundaries(self):
        for entry in (2_010, 5_020, 20_100, 50_200):
            atr14 = entry * 0.01  # the 1.5% minimum decides the distance
            computed = entry - entry * POLICY.min_stop_pct / 100
            result = plan(entry, entry - 1, atr14, cash=10_000_000)
            # Rounding to nearest would lift each of these stops above `computed`.
            self.assertLessEqual(result.stop_price, computed)
            self.assertEqual(0, result.stop_price % _tick_size(result.stop_price))
            self.assertLessEqual(
                result.emergency_stop, result.stop_price - POLICY.hard_atr_mult * atr14
            )
            self.assertEqual(0, result.emergency_stop % _tick_size(result.emergency_stop))
            self.assertLessEqual(result.risk_amount, 10_000)

    def test_risk_never_exceeds_the_daily_loss_budget(self):
        for entry, support, atr14 in (
            (4_980, 4_900, 150.0),
            (10_000, 9_950, 500.0),
            (30_000, 29_800, 1_000.0),
            (148_000, 146_000, 3_000.0),
        ):
            result = plan(entry, support, atr14)
            if result is not None:
                self.assertLessEqual(result.risk_amount, 10_000)
                self.assertLessEqual(result.invested_amount, 240_000)

    def test_without_a_policy_the_fixed_ratio_stops_are_unchanged(self):
        # The day-trade engine calls without atr_policy; these are the pre-v0.4 values.
        for entry, support, expected in (
            (10_000, 9_950, (9_750, 9_550, 10_380, 10_620, 22)),
            (30_000, 29_800, (29_250, 28_650, 31_100, 31_900, 7)),
            (4_980, 4_900, (4_855, 4_755, 5_170, 5_290, 44)),
            (10_000, 9_000, (9_000, 8_860, 11_500, 12_500, 8)),
        ):
            result = build_position_plan(
                cash=600_000,
                entry_price=entry,
                support_price=support,
                max_allocation_pct=0.40,
                max_loss=10_000,
            )
            self.assertEqual(
                expected,
                (result.stop_price, result.emergency_stop, result.target1, result.target2, result.quantity),
            )


if __name__ == "__main__":
    unittest.main()
