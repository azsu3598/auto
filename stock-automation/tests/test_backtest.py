from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from stock_automation.backtest import (
    ReplayBar,
    ReplayCase,
    ReplayOutcome,
    TradingCosts,
    replay_decision,
    run_backtest,
)
from stock_automation.engine import ClosingBetEngine
from test_engine import quote, snapshot

KST = timezone(timedelta(hours=9))


def at(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=KST)


class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.engine = ClosingBetEngine()
        self.costs = TradingCosts(0, 0, 0)

    def test_partial_target_then_0910_exit(self):
        case = ReplayCase(
            snapshot=snapshot(quote()),
            future_bars=(
                ReplayBar(at(6, 15, 25), 20_050, 20_950, 19_950, 20_800),
                ReplayBar(at(7, 9, 10), 20_400, 20_600, 20_300, 20_500),
            ),
            scheduled_exit_at=at(7, 9, 10),
        )
        result = replay_decision(engine=self.engine, case=case, cash=600_000, costs=self.costs)
        self.assertEqual(ReplayOutcome.PARTIAL_THEN_SCHEDULED, result.outcome)
        self.assertEqual(2, len(result.exits))
        # 3 shares under the 3,300 KRW closing-bet loss limit (2026-10-29).
        self.assertEqual(1_900, result.net_pnl)

    def test_gap_below_emergency_uses_observed_open(self):
        case = ReplayCase(
            snapshot=snapshot(quote()),
            future_bars=(ReplayBar(at(7, 9, 5), 19_000, 19_100, 18_900, 19_000),),
            scheduled_exit_at=at(7, 9, 10),
        )
        result = replay_decision(engine=self.engine, case=case, cash=600_000, costs=self.costs)
        self.assertEqual(ReplayOutcome.EMERGENCY_STOP, result.outcome)
        self.assertEqual(19_000, result.exits[0].price)
        # The planned emergency-floor risk is bounded, but a gap can execute
        # below that floor at the first observable price.
        self.assertEqual(-3_000, result.net_pnl)

    def test_five_minute_stop_requires_following_failed_reclaim(self):
        case = ReplayCase(
            snapshot=snapshot(quote()),
            future_bars=(
                ReplayBar(at(6, 15, 25), 19_500, 19_550, 19_200, 19_350),
                ReplayBar(at(6, 15, 30), 19_360, 19_390, 19_250, 19_300),
            ),
            scheduled_exit_at=at(7, 9, 10),
        )
        result = replay_decision(engine=self.engine, case=case, cash=600_000, costs=self.costs)
        self.assertEqual(ReplayOutcome.STOP_LOSS, result.outcome)
        self.assertEqual(19_300, result.exits[0].price)

    def test_costs_are_deducted_from_replay(self):
        case = ReplayCase(
            snapshot=snapshot(quote()),
            future_bars=(ReplayBar(at(7, 9, 10), 20_100, 20_200, 20_000, 20_100),),
            scheduled_exit_at=at(7, 9, 10),
        )
        zero = replay_decision(engine=self.engine, case=case, cash=600_000, costs=self.costs)
        paid = replay_decision(
            engine=self.engine,
            case=case,
            cash=600_000,
            costs=TradingCosts(1.5, 1.5, 15.0),
        )
        self.assertLess(paid.net_pnl, zero.net_pnl)
        self.assertGreater(paid.total_costs, 0)

    def test_summary_tracks_drawdown_and_no_trade(self):
        winning = ReplayCase(
            snapshot=snapshot(quote()),
            future_bars=(ReplayBar(at(7, 9, 10), 20_100, 20_200, 20_000, 20_100),),
            scheduled_exit_at=at(7, 9, 10),
        )
        no_trade_snapshot = snapshot(quote(code="654321", nxt_eligible=True))
        no_trade = ReplayCase(no_trade_snapshot, (), at(7, 9, 10))
        summary = run_backtest(
            (winning, no_trade), starting_cash=600_000, costs=self.costs
        )
        self.assertEqual(2, summary.cases)
        self.assertEqual(1, summary.trades)
        self.assertEqual(1, summary.no_trades)
        self.assertGreater(summary.ending_cash, summary.starting_cash)


if __name__ == "__main__":
    unittest.main()
