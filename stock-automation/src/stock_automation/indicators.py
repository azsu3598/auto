from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class TechnicalFeatures:
    ma5: float
    ma20: float
    ma60: float | None
    ma120: float | None
    rsi14: float
    atr14: float
    recent_resistance: float
    vwap: float
    five_min_ma20: float
    five_min_ma20_slope: float
    five_min_volume_ratio: float
    last_hour_return_pct: float
    higher_lows: bool
    breakout_level: float | None
    breakout_holds: bool


def sma(values: Sequence[float], period: int) -> float:
    if period <= 0 or len(values) < period:
        raise ValueError(f"at least {period} values are required")
    return fmean(values[-period:])


def rsi(values: Sequence[float], period: int = 14) -> float:
    if len(values) < period + 1:
        raise ValueError(f"at least {period + 1} values are required")
    changes = [new - old for old, new in zip(values[-period - 1 : -1], values[-period:])]
    gains = fmean(max(change, 0.0) for change in changes)
    losses = fmean(max(-change, 0.0) for change in changes)
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    relative_strength = gains / losses
    return 100.0 - 100.0 / (1.0 + relative_strength)


def atr(bars: Sequence[Bar], period: int = 14) -> float:
    if len(bars) < period + 1:
        raise ValueError(f"at least {period + 1} bars are required")
    sample = bars[-period - 1 :]
    true_ranges = []
    for previous, current in zip(sample[:-1], sample[1:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return fmean(true_ranges)


def session_vwap(bars: Sequence[Bar]) -> float:
    total_volume = sum(max(bar.volume, 0.0) for bar in bars)
    if total_volume <= 0:
        raise ValueError("positive intraday volume is required")
    value = sum(((bar.high + bar.low + bar.close) / 3.0) * bar.volume for bar in bars)
    return value / total_volume


def compute_features(daily_bars: Sequence[Bar], five_minute_bars: Sequence[Bar]) -> TechnicalFeatures:
    if len(daily_bars) < 21:
        raise ValueError("at least 21 daily bars are required")
    if len(five_minute_bars) < 25:
        raise ValueError("at least 25 five-minute bars are required")
    daily = sorted(daily_bars, key=lambda bar: bar.timestamp)
    intraday = sorted(five_minute_bars, key=lambda bar: bar.timestamp)
    daily_closes = [bar.close for bar in daily]
    minute_closes = [bar.close for bar in intraday]

    ma5 = sma(daily_closes, 5)
    ma20 = sma(daily_closes, 20)
    ma60 = sma(daily_closes, 60) if len(daily_closes) >= 60 else None
    ma120 = sma(daily_closes, 120) if len(daily_closes) >= 120 else None
    five_ma20 = sma(minute_closes, 20)
    prior_five_ma20 = sma(minute_closes[:-1], 20)

    prior_daily = daily[-21:-1]
    resistance_candidates = [bar.high for bar in prior_daily if bar.high > daily[-1].close]
    recent_resistance = min(resistance_candidates) if resistance_candidates else max(bar.high for bar in daily[-20:])

    recent = intraday[-4:]
    higher_lows = all(left.low <= right.low for left, right in zip(recent[:-1], recent[1:]))
    breakout_window = intraday[-23:-3]
    breakout_level = max((bar.high for bar in breakout_window), default=None)
    breakout_holds = bool(
        breakout_level
        and intraday[-1].close >= breakout_level
        and min(bar.low for bar in intraday[-3:]) >= breakout_level * 0.995
    )

    recent_volume = fmean(bar.volume for bar in intraday[-3:])
    baseline_bars = intraday[-13:-3]
    baseline_volume = fmean(bar.volume for bar in baseline_bars)
    volume_ratio = recent_volume / baseline_volume if baseline_volume > 0 else 0.0
    hour_start = intraday[-13].close if len(intraday) >= 13 else intraday[0].close
    last_hour_return = ((intraday[-1].close / hour_start) - 1.0) * 100 if hour_start > 0 else 0.0

    return TechnicalFeatures(
        ma5=ma5,
        ma20=ma20,
        ma60=ma60,
        ma120=ma120,
        rsi14=rsi(daily_closes),
        atr14=atr(daily),
        recent_resistance=recent_resistance,
        vwap=session_vwap(intraday),
        five_min_ma20=five_ma20,
        five_min_ma20_slope=five_ma20 - prior_five_ma20,
        five_min_volume_ratio=volume_ratio,
        last_hour_return_pct=last_hour_return,
        higher_lows=higher_lows,
        breakout_level=breakout_level,
        breakout_holds=breakout_holds,
    )
