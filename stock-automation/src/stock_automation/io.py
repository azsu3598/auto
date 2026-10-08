from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import MarketSnapshot, Quote, Session


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timezone offset is required: {value}")
    return parsed


def load_snapshot(path: str | Path) -> MarketSnapshot:
    with Path(path).open(encoding="utf-8") as handle:
        raw: dict[str, Any] = json.load(handle)
    return snapshot_from_dict(raw)


def snapshot_from_dict(raw: dict[str, Any]) -> MarketSnapshot:
    quotes = []
    for item in raw["quotes"]:
        item = dict(item)
        item["observed_at"] = _parse_datetime(item["observed_at"])
        item["warnings"] = tuple(item.get("warnings", ()))
        quotes.append(Quote(**item))
    return MarketSnapshot(
        captured_at=_parse_datetime(raw["captured_at"]),
        session=Session(raw["session"]),
        kospi_change_pct=float(raw["kospi_change_pct"]),
        kosdaq_change_pct=float(raw["kosdaq_change_pct"]),
        quotes=tuple(quotes),
        source=raw["source"],
        delayed=bool(raw.get("delayed", False)),
    )
