from __future__ import annotations

import unittest
from datetime import date

from stock_automation.calendar import TradingCalendar


class TradingCalendarTests(unittest.TestCase):
    def test_weekend_and_holiday_are_closed(self):
        calendar = TradingCalendar.from_dict({"year": 2026, "holidays": ["2026-10-09"]})
        self.assertTrue(calendar.is_trading_day(date(2026, 10, 8)))
        self.assertFalse(calendar.is_trading_day(date(2026, 10, 9)))
        self.assertFalse(calendar.is_trading_day(date(2026, 10, 10)))

    def test_unknown_year_fails_closed(self):
        calendar = TradingCalendar.from_dict({"year": 2026, "holidays": []})
        with self.assertRaisesRegex(ValueError, "does not cover"):
            calendar.is_trading_day(date(2027, 1, 4))

    def test_counts_trading_days_after_entry_date(self):
        calendar = TradingCalendar(
            year=2026,
            holidays=frozenset({date(2026, 10, 9)}),
        )
        self.assertEqual(
            2,
            calendar.trading_days_between(date(2026, 10, 7), date(2026, 10, 12)),
        )


if __name__ == "__main__":
    unittest.main()
