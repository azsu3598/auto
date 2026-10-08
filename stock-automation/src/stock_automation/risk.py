from __future__ import annotations

from dataclasses import dataclass
from math import floor


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


def _tick_round(value: float) -> int:
    """Conservative KRW rounding for planning, not exchange order validation."""
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
    return int(round(value / tick) * tick)


def build_position_plan(
    *,
    cash: int,
    entry_price: int,
    support_price: int,
    max_allocation_pct: float,
    max_loss: int,
) -> PositionPlan | None:
    if cash <= 0 or entry_price <= 0 or support_price <= 0:
        return None

    soft_stop = _tick_round(min(support_price, entry_price * 0.975))
    emergency_stop = _tick_round(min(soft_stop * 0.985, entry_price * 0.955))
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
