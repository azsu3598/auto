from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_automation.backtest import ReplayBar, ReplayCase, TradingCosts
from stock_automation.config import StrategyConfig
from stock_automation.learning import (
    TunableParameters,
    TuningPolicy,
    config_from_champion,
    parameters_from_config,
    tune_strategy,
    write_paper_champion,
)
from stock_automation.models import MarketSnapshot, Session
from test_engine import quote

KST = timezone(timedelta(hours=9))


def cases(count: int) -> tuple[ReplayCase, ...]:
    result = []
    for index in range(count):
        day = 1 + index
        captured = datetime(2026, 9, day, 15, 20, 30, tzinfo=KST)
        q = quote(
            code=f"{index:06d}",
            observed_at=captured - timedelta(seconds=10),
            high_price=20_667,
            low_price=19_000,
        )
        snap = MarketSnapshot(
            captured_at=captured,
            session=Session.KRX_1520,
            kospi_change_pct=0.1,
            kosdaq_change_pct=0.2,
            quotes=(q,),
            source="learning-fixture",
        )
        exit_at = captured + timedelta(hours=17, minutes=50)
        result.append(
            ReplayCase(
                snapshot=snap,
                future_bars=(ReplayBar(exit_at, 20_100, 20_200, 20_000, 20_100),),
                scheduled_exit_at=exit_at,
            )
        )
    return tuple(result)


class LearningTests(unittest.TestCase):
    def test_insufficient_data_never_promotes(self):
        result = tune_strategy(
            cases(3),
            starting_cash=600_000,
            costs=TradingCosts(0, 0, 0),
            policy=TuningPolicy(minimum_cases=10),
        )
        self.assertFalse(result.promoted)
        self.assertEqual("INSUFFICIENT_DATA", result.status)

    def test_walk_forward_can_promote_only_validated_paper_rule(self):
        base = StrategyConfig()
        base_params = parameters_from_config(base)
        looser = replace(base_params, minimum_close_strength=0.58)
        result = tune_strategy(
            cases(10),
            starting_cash=600_000,
            costs=TradingCosts(0, 0, 0),
            base_config=base,
            policy=TuningPolicy(
                minimum_cases=10,
                validation_fraction=0.30,
                minimum_validation_trades=2,
                minimum_validation_score_improvement=0.1,
            ),
            variants=(base_params, looser),
        )
        self.assertTrue(result.promoted)
        self.assertEqual(looser, result.challenger_parameters)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "champion.json"
            write_paper_champion(path, result, base)
            text = path.read_text(encoding="utf-8")
            self.assertIn('"mode": "PAPER_ONLY"', text)
            self.assertIn('"minimum_close_strength": 0.58', text)
            # The champion names the engine logic it was tuned on and loads back.
            payload = json.loads(text)
            self.assertEqual("closing-v0.5", payload["base_rule_version"])
            self.assertEqual(0.58, config_from_champion(base, payload).minimum_close_strength)


if __name__ == "__main__":
    unittest.main()
