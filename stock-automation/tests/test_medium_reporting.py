from __future__ import annotations

import unittest
from datetime import timedelta

from stock_automation.medium_reporting import (
    render_entry_report,
    render_review_report,
    render_signal_report,
)
from stock_automation.medium_term import (
    MediumTermEngine,
    confirm_medium_term_entry,
    review_medium_term_position,
)
from test_medium_term import NOW, snapshot


class MediumReportingTests(unittest.TestCase):
    def test_signal_entry_and_review_reports_are_human_readable(self):
        source = snapshot()
        decision = MediumTermEngine().evaluate(source, cash=600_000)
        signal = render_signal_report(source, decision)
        self.assertIn("익일 최대 진입가", signal)
        self.assertIn("중기테스트", signal)

        confirmation = confirm_medium_term_entry(
            decision.entry_plan,
            observed_at=NOW + timedelta(days=1),
            observed_price=11_100,
            cash=600_000,
        )
        entry = render_entry_report(confirmation)
        self.assertIn("모의 진입가/수량", entry)

        review = review_medium_term_position(
            confirmation.position,
            observed_at=NOW + timedelta(days=2),
            closing_price=11_200,
            trading_days_held=1,
        )
        rendered = render_review_report(
            confirmation.position,
            review,
            trading_days_held=1,
            net_pnl=None,
            total_costs=None,
        )
        self.assertIn("결정: HOLD", rendered)


if __name__ == "__main__":
    unittest.main()
