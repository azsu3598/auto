from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .medium_term import MediumTermQuote, MediumTermSnapshot


def load_medium_term_snapshot(path: str | Path) -> MediumTermSnapshot:
    with Path(path).open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return medium_term_snapshot_from_dict(raw)


def medium_term_snapshot_from_dict(raw: dict[str, Any]) -> MediumTermSnapshot:
    quotes = []
    for source in raw["quotes"]:
        item = dict(source)
        item["observed_at"] = _datetime(item["observed_at"])
        item["fundamental_observed_at"] = _datetime(item["fundamental_observed_at"])
        item["risk_flags"] = tuple(item.get("risk_flags", ()))
        quotes.append(MediumTermQuote(**item))
    return MediumTermSnapshot(
        captured_at=_datetime(raw["captured_at"]),
        quotes=tuple(quotes),
        source=str(raw["source"]),
        delayed=bool(raw.get("delayed", False)),
    )


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timezone offset is required: {value}")
    return parsed
