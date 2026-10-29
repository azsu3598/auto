from __future__ import annotations

import json
import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from stock_automation.config import StrategyConfig
from stock_automation.day_trade import DayTradeConfig, DayTradeEngine
from stock_automation.engine import ClosingBetEngine
from stock_automation.medium_term import MediumTermConfig, MediumTermEngine, confirm_medium_term_entry
from stock_automation.models import DecisionType, Session
from stock_automation.paper_wallet import is_current_wallet, stored_wallet_key, wallet_epoch, wallet_key
from test_day_trade import quote as day_trade_quote, snapshot as day_trade_snapshot
from test_engine import quote, snapshot
from test_medium_term import snapshot as medium_snapshot

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
EPOCH = "200K-20261103"
ORIGINAL_KEYS = {
    ("CLOSING_BET", Session.KRX_1520): "WALLET#CLOSING_BET#KRX_1520",
    ("CLOSING_BET", Session.NXT_1955): "WALLET#CLOSING_BET#NXT_1955",
    ("DAY_TRADE", None): "WALLET#DAY_TRADE",
    ("MEDIUM_TERM", None): "WALLET#MEDIUM_TERM",
}


class WalletKeyTests(unittest.TestCase):
    def test_without_epoch_every_key_is_the_original_one(self):
        with patch.dict(os.environ, {"PAPER_WALLET_EPOCH": ""}):
            for (strategy, session), key in ORIGINAL_KEYS.items():
                self.assertEqual(key, wallet_key(strategy, session))
                self.assertTrue(is_current_wallet(key))
        with patch.dict(os.environ):
            os.environ.pop("PAPER_WALLET_EPOCH", None)
            self.assertEqual("", wallet_epoch())
            self.assertEqual("WALLET#DAY_TRADE", wallet_key("DAY_TRADE"))
        # The dashboard Lambda packages paper_wallet.py alone, so it keeps its
        # own copy of the closing-bet session values.
        self.assertEqual(
            {"KRX_1520", "NXT_1955"},
            {key.split("#")[2] for key in ORIGINAL_KEYS.values() if "CLOSING_BET" in key},
        )
        self.assertEqual({"KRX_1520", "NXT_1955"}, {session.value for session in Session})

    def test_epoch_suffixes_every_paper_wallet_and_rejects_unsafe_values(self):
        with patch.dict(os.environ, {"PAPER_WALLET_EPOCH": EPOCH}):
            for (strategy, session), key in ORIGINAL_KEYS.items():
                self.assertEqual(key + "#" + EPOCH, wallet_key(strategy, session))
                self.assertTrue(is_current_wallet(key + "#" + EPOCH))
                self.assertFalse(is_current_wallet(key))
            # Rows that are not paper strategy wallets are not hidden by the epoch.
            self.assertTrue(is_current_wallet("WALLET#LIVE#CLOSING_BET"))
            self.assertTrue(is_current_wallet("WALLET#TEST"))
            self.assertFalse(is_current_wallet("OPEN#DAY_TRADE"))
        self.assertFalse(is_current_wallet("WALLET#DAY_TRADE#" + EPOCH, epoch=""))
        for value in ("200K 20261103", "a#b", "x" * 41):
            with self.assertRaises(ValueError):
                wallet_key("DAY_TRADE", epoch=value)
        with self.assertRaises(ValueError):
            wallet_key("SWING")
        with self.assertRaises(ValueError):
            wallet_key("CLOSING_BET", "KRX_1530")

    def test_open_position_keeps_the_wallet_it_was_paid_from(self):
        legacy = "WALLET#CLOSING_BET#KRX_1520"
        self.assertEqual(legacy, stored_wallet_key({}, legacy))
        self.assertEqual(legacy, stored_wallet_key({"wallet_key": {"S": " "}}, legacy))
        self.assertEqual(
            legacy + "#" + EPOCH,
            stored_wallet_key({"wallet_key": {"S": legacy + "#" + EPOCH}}, legacy),
        )


class TwoHundredThousandCapitalTests(unittest.TestCase):
    """One third of the earlier 600,000 KRW loss limits (2026-10-29)."""

    def test_loss_limits_are_one_third_and_allocations_unchanged(self):
        self.assertEqual((3_300, 0.40), (StrategyConfig().max_daily_loss, StrategyConfig().max_allocation_pct))
        self.assertEqual((2_700, 0.25), (DayTradeConfig().maximum_position_loss, DayTradeConfig().maximum_allocation_pct))
        self.assertEqual((6_700, 0.30), (MediumTermConfig().maximum_position_loss, MediumTermConfig().maximum_allocation_pct))

    def test_closing_bet_with_200k(self):
        decision = ClosingBetEngine().evaluate(snapshot(quote()), cash=200_000)
        self.assertEqual(DecisionType.BUY, decision.decision)
        position = decision.position
        self.assertLessEqual((position.entry_price - position.emergency_stop) * position.quantity, 3_300)
        self.assertLessEqual(position.invested_amount, 80_000)

    def test_day_trade_and_medium_term_with_200k(self):
        day = DayTradeEngine().evaluate(day_trade_snapshot(day_trade_quote()), cash=200_000).position
        self.assertIsNotNone(day)
        self.assertLessEqual((day.entry_price - day.emergency_stop) * day.quantity, 2_700)
        self.assertLessEqual(day.invested_amount, 50_000)

        signal = MediumTermEngine().evaluate(medium_snapshot(), cash=200_000)
        self.assertIsNotNone(signal.entry_plan)
        self.assertLessEqual(signal.entry_plan.indicative_amount, 60_000)
        entry = confirm_medium_term_entry(
            signal.entry_plan,
            observed_at=datetime(2026, 10, 8, 9, 15, tzinfo=KST),
            observed_price=11_100,
            cash=200_000,
        ).position
        self.assertIsNotNone(entry)
        self.assertLessEqual((entry.entry_price - entry.thesis_invalidation) * entry.quantity, 6_700)
        self.assertLessEqual(entry.invested_amount, 60_000)


class TemplateDefaultTests(unittest.TestCase):
    def test_starting_cash_defaults_are_200k_and_epoch_is_passed_to_the_worker(self):
        for name in ("paper-worker-verification", "paper-one-session-pilot", "paper-five-session-batch"):
            with self.subTest(template=name):
                template = json.loads((ROOT / "infra" / f"{name}.yaml").read_text(encoding="utf-8"))
                parameters = template["Parameters"]
                for cash in ("StartingCash", "MediumStartingCash", "DayTradeStartingCash"):
                    self.assertEqual("200000", parameters[cash]["Default"])
                self.assertEqual("", parameters["PaperWalletEpoch"]["Default"])
                tasks = [r for r in template["Resources"].values() if r["Type"] == "AWS::ECS::TaskDefinition"]
                self.assertEqual(1, len(tasks))
                environment = tasks[0]["Properties"]["ContainerDefinitions"][0]["Environment"]
                self.assertIn({"Name": "PAPER_WALLET_EPOCH", "Value": {"Ref": "PaperWalletEpoch"}}, environment)

        app = (ROOT / "infra" / "cloudformation.yaml").read_text(encoding="utf-8")
        for cash in ("StartingCash", "MediumStartingCash", "DayTradeStartingCash"):
            self.assertRegex(app, rf"\n  {cash}:\n    Type: Number\n    Default: 200000\n")
        self.assertRegex(app, r'\n  PaperWalletEpoch:\n    Type: String\n    Default: ""\n')
        self.assertIn("- Name: PAPER_WALLET_EPOCH\n              Value: !Ref PaperWalletEpoch", app)

        web = json.loads((ROOT / "infra" / "paper-web-dashboard.yaml").read_text(encoding="utf-8"))
        self.assertEqual("", web["Parameters"]["PaperWalletEpoch"]["Default"])
        variables = web["Resources"]["ApiFunction"]["Properties"]["Environment"]["Variables"]
        self.assertEqual({"Ref": "PaperWalletEpoch"}, variables["PAPER_WALLET_EPOCH"])

    def test_runtime_cash_defaults_are_200k(self):
        source = (ROOT / "src" / "stock_automation" / "aws_runtime.py").read_text(encoding="utf-8")
        defaults = re.findall(r'os\.getenv\("((?:MEDIUM_|DAY_TRADE_)?STARTING_CASH)", "(\d+)"\)', source)
        self.assertEqual(4, len(defaults))
        self.assertEqual({"200000"}, {value for _, value in defaults})


if __name__ == "__main__":
    unittest.main()
