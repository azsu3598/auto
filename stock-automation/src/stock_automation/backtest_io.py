from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .backtest import ReplayBar, ReplayCase
from .io import snapshot_from_dict


def load_replay_cases(path: str | Path) -> tuple[ReplayCase, ...]:
    with Path(path).open(encoding="utf-8") as handle:
        raw = json.load(handle)
    rows = raw.get("cases", raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise ValueError("backtest input must be a list or {'cases': [...]} object")
    return tuple(replay_case_from_dict(item) for item in rows)


def replay_case_from_dict(item: dict) -> ReplayCase:
    snapshot = snapshot_from_dict(item["snapshot"])
    bars = tuple(
        ReplayBar(
            observed_at=_datetime(bar["observed_at"]),
            open=int(bar["open"]),
            high=int(bar["high"]),
            low=int(bar["low"]),
            close=int(bar["close"]),
            volume=int(bar.get("volume", 0)),
        )
        for bar in item.get("future_bars", [])
    )
    return ReplayCase(
        snapshot=snapshot,
        future_bars=bars,
        scheduled_exit_at=_datetime(item["scheduled_exit_at"]),
    )


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timezone offset is required: {value}")
    return parsed
