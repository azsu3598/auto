from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    year: int
    holidays: frozenset[date]
    automatic_schedule_eligible: bool = False
    reviewed_through: date | None = None
    special_sessions: frozenset[date] = frozenset()

    @classmethod
    def from_dict(cls, data: dict) -> "TradingCalendar":
        year = int(data["year"])
        holidays = frozenset(date.fromisoformat(value) for value in data.get("holidays", []))
        if any(day.year != year for day in holidays):
            raise ValueError("calendar holiday year mismatch")
        eligible = data.get("automatic_schedule_eligible", False)
        if not isinstance(eligible, bool):
            raise ValueError("automatic schedule eligibility must be boolean")
        reviewed = data.get("reviewed_through")
        reviewed = date.fromisoformat(reviewed) if reviewed else None
        special = frozenset(date.fromisoformat(value) for value in data.get("special_session_review_dates", []))
        if any(day.year != year for day in special) or (reviewed and reviewed.year != year):
            raise ValueError("calendar review year mismatch")
        return cls(year=year, holidays=holidays, automatic_schedule_eligible=eligible,
                   reviewed_through=reviewed, special_sessions=special)

    def require_automatic_session(self, day: date, *, check_next_session: bool = False) -> None:
        if not self.automatic_schedule_eligible or self.reviewed_through is None or day > self.reviewed_through:
            raise ValueError("CALENDAR_NOT_APPROVED")
        if not self.is_trading_day(day) or day in self.special_sessions:
            raise ValueError("NONSTANDARD_OR_CLOSED_SESSION")
        if check_next_session:
            following = day + timedelta(days=1)
            while not self.is_trading_day(following):
                following += timedelta(days=1)
            if following in self.special_sessions or following > self.reviewed_through:
                raise ValueError("NEXT_SESSION_NOT_APPROVED")

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
