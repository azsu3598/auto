from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .day_trade import DayTradeQuote, DayTradeSnapshot


def load_day_trade_snapshot(path: str | Path) -> DayTradeSnapshot:
    with Path(path).open(encoding="utf-8") as handle:
        raw = json.load(handle)
    quotes = []
    for source in raw["quotes"]:
        item = dict(source)
        item["observed_at"] = _datetime(item["observed_at"])
        item["warnings"] = tuple(item.get("warnings", ()))
        quotes.append(DayTradeQuote(**item))
    return DayTradeSnapshot(
        captured_at=_datetime(raw["captured_at"]),
        kospi_change_pct=float(raw["kospi_change_pct"]),
        kosdaq_change_pct=float(raw["kosdaq_change_pct"]),
        quotes=tuple(quotes),
        source=str(raw["source"]),
        delayed=bool(raw.get("delayed", False)),
    )


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timezone offset is required: {value}")
    return parsed
