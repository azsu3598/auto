from __future__ import annotations

import unittest

from stock_automation.backtest import TradingCosts
from stock_automation.portfolio import entry_cash_flow, exit_cash_flow


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.costs = TradingCosts(buy_fee_bps=1.5, sell_fee_bps=1.5, sell_tax_bps=18.0)

    def test_entry_debits_principal_and_buy_fee(self):
        flow = entry_cash_flow(10_000, 20, self.costs)
        self.assertEqual(200_000, flow.principal)
        self.assertEqual(30, flow.buy_fee)
        self.assertEqual(200_030, flow.cash_debit)

    def test_exit_credits_net_proceeds_and_reports_net_pnl(self):
        flow = exit_cash_flow(
            entry_price=10_000,
            exit_price=10_200,
            quantity=20,
            costs=self.costs,
        )
        self.assertEqual(4_000, flow.gross_pnl)
        self.assertEqual(30, flow.allocated_buy_fee)
        self.assertEqual(30, flow.sell_fee)
        self.assertEqual(367, flow.sell_tax)
        self.assertEqual(3_573, flow.net_pnl)
        self.assertEqual(203_603, flow.net_proceeds)


if __name__ == "__main__":
    unittest.main()
