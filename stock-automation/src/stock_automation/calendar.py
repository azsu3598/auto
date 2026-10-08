from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    year: int
    holidays: frozenset[date]

    @classmethod
    def from_dict(cls, data: dict) -> "TradingCalendar":
        year = int(data["year"])
        holidays = frozenset(date.fromisoformat(value) for value in data.get("holidays", []))
        if any(day.year != year for day in holidays):
            raise ValueError("calendar holiday year mismatch")
        return cls(year=year, holidays=holidays)

    def is_trading_day(self, day: date) -> bool:
        if day.year != self.year:
            raise ValueError("trading calendar does not cover requested year")
        return day.weekday() < 5 and day not in self.holidays

    def trading_days_between(self, start: date, end: date) -> int:
        """Count trading dates after start through end, failing outside this calendar."""
        if end < start:
            raise ValueError("end date cannot precede start date")
        if start.year != self.year or end.year != self.year:
            raise ValueError("trading calendar does not cover requested range")
        count = 0
        current = start + timedelta(days=1)
        while current <= end:
            count += int(self.is_trading_day(current))
            current += timedelta(days=1)
        return count
