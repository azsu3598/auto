from __future__ import annotations

from dataclasses import dataclass
from math import floor


STOP_TOO_WIDE = "STOP_TOO_WIDE"
ATR_UNAVAILABLE = "ATR_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class PositionPlan:
    quantity: int
    invested_amount: int
    remaining_cash: int
    stop_price: int
    emergency_stop: int
    target1: int
    target2: int
    risk_amount: int


@dataclass(frozen=True, slots=True)
class AtrStopPolicy:
    """Volatility-based stop distances; percentages are of the entry price."""

    soft_atr_mult: float
    hard_atr_mult: float
    min_stop_pct: float
    max_stop_pct: float
    max_hard_stop_pct: float


def _tick_size(value: float) -> int:
    if value < 2_000:
        tick = 1
    elif value < 5_000:
        tick = 5
    elif value < 20_000:
        tick = 10
    elif value < 50_000:
        tick = 50
    elif value < 200_000:
        tick = 100
    elif value < 500_000:
        tick = 500
    else:
        tick = 1_000
    return tick


def _tick_round(value: float) -> int:
    """Conservative KRW rounding for planning, not exchange order validation."""
    tick = _tick_size(value)
    return int(round(value / tick) * tick)


def _tick_floor(value: float) -> int:
    """Round down to the tick so a stop never ends up above its computed level."""
    tick = _tick_size(value)
    # round() strips float noise such as 9749.999999 before flooring.
    return int(floor(round(value / tick, 9)) * tick)


def _atr_stops(
    entry_price: int, support_price: int, atr14: float | None, policy: AtrStopPolicy
) -> tuple[int, int] | str:
    """Return (soft_stop, emergency_stop) or the reason no plan is allowed."""
    if atr14 is None or not atr14 > 0:
        return ATR_UNAVAILABLE
    soft_distance = max(
        entry_price - support_price,
        policy.soft_atr_mult * atr14,
        entry_price * policy.min_stop_pct / 100,
    )
    soft_stop = _tick_floor(entry_price - soft_distance)
    if entry_price - soft_stop > entry_price * policy.max_stop_pct / 100:
        return STOP_TOO_WIDE
    emergency_stop = _tick_floor(soft_stop - policy.hard_atr_mult * atr14)
    if entry_price - emergency_stop > entry_price * policy.max_hard_stop_pct / 100:
        return STOP_TOO_WIDE
    return soft_stop, emergency_stop


def atr_stop_rejection(
    *, entry_price: int, support_price: int, atr14: float | None, policy: AtrStopPolicy
) -> str | None:
    """Name why ATR stops forbid a plan (``STOP_TOO_WIDE``/``ATR_UNAVAILABLE``)."""
    stops = _atr_stops(entry_price, support_price, atr14, policy)
    return stops if isinstance(stops, str) else None


def build_position_plan(
    *,
    cash: int,
    entry_price: int,
    support_price: int,
    max_allocation_pct: float,
    max_loss: int,
    atr14: float | None = None,
    atr_policy: AtrStopPolicy | None = None,
) -> PositionPlan | None:
    """Size a paper position from its emergency stop.

    Without ``atr_policy`` the stops are the fixed-ratio ones the day-trade
    engine uses. With it, stops follow the daily ATR and are rounded down to
    the tick; a stop wider than the policy allows, or a missing ATR, yields
    no plan (see ``atr_stop_rejection`` for the reason).
    """
    if cash <= 0 or entry_price <= 0 or support_price <= 0:
        return None

    if atr_policy is None:
        soft_stop = _tick_round(min(support_price, entry_price * 0.975))
        emergency_stop = _tick_round(min(soft_stop * 0.985, entry_price * 0.955))
    else:
        stops = _atr_stops(entry_price, support_price, atr14, atr_policy)
        if isinstance(stops, str):
            return None
        soft_stop, emergency_stop = stops
    soft_risk_per_share = entry_price - soft_stop
    hard_risk_per_share = entry_price - emergency_stop
    if soft_risk_per_share <= 0 or hard_risk_per_share <= 0:
        return None

    allocation_cap = floor(cash * max_allocation_pct)
    by_allocation = allocation_cap // entry_price
    # Size from the emergency floor, not the softer confirmation stop.  This
    # keeps the planned worst-case loss inside the daily budget before gap
    # slippage and trading costs.
    by_risk = max_loss // hard_risk_per_share
    quantity = min(by_allocation, by_risk)
    if quantity < 1:
        return None

    invested = entry_price * quantity
    risk = hard_risk_per_share * quantity
    target1 = _tick_round(entry_price + soft_risk_per_share * 1.5)
    target2 = _tick_round(entry_price + soft_risk_per_share * 2.5)
    return PositionPlan(
        quantity=quantity,
        invested_amount=invested,
        remaining_cash=cash - invested,
        stop_price=soft_stop,
        emergency_stop=emergency_stop,
        target1=target1,
        target2=target2,
        risk_amount=risk,
    )
