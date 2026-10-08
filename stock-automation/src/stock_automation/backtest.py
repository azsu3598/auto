from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from math import floor
from typing import Iterable

from .config import StrategyConfig
from .engine import ClosingBetEngine
from .models import DecisionType, MarketSnapshot, Position, StopMode


class ReplayOutcome(StrEnum):
    NO_TRADE = "NO_TRADE"
    TARGET2 = "TARGET2"
    PARTIAL_THEN_SCHEDULED = "PARTIAL_THEN_SCHEDULED"
    SCHEDULED_EXIT = "SCHEDULED_EXIT"
    STOP_LOSS = "STOP_LOSS"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    OPEN_NO_0910_DATA = "OPEN_NO_0910_DATA"


@dataclass(frozen=True, slots=True)
class ReplayBar:
    observed_at: datetime
    open: int
    high: int
    low: int
    close: int
    volume: int = 0

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("replay bar timestamp must be timezone-aware")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("replay bar prices must be positive")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("invalid OHLC range")


@dataclass(frozen=True, slots=True)
class TradingCosts:
    buy_fee_bps: float
    sell_fee_bps: float
    sell_tax_bps: float

    def __post_init__(self) -> None:
        if min(self.buy_fee_bps, self.sell_fee_bps, self.sell_tax_bps) < 0:
            raise ValueError("trading costs cannot be negative")


@dataclass(frozen=True, slots=True)
class ReplayExit:
    observed_at: datetime
    price: int
    quantity: int
    reason: str


@dataclass(frozen=True, slots=True)
class ReplayResult:
    event_id: str
    decision: str
    stock_code: str | None
    stock_name: str | None
    entry_at: datetime | None
    entry_price: int | None
    entry_quantity: int
    exits: tuple[ReplayExit, ...]
    remaining_quantity: int
    gross_pnl: int
    total_costs: int
    net_pnl: int
    return_pct: float | None
    mfe_pct: float | None
    mae_pct: float | None
    outcome: ReplayOutcome
    ending_cash: int
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["outcome"] = self.outcome.value
        if self.entry_at is not None:
            data["entry_at"] = self.entry_at.isoformat()
        for item, original in zip(data["exits"], self.exits):
            item["observed_at"] = original.observed_at.isoformat()
        return data


@dataclass(frozen=True, slots=True)
class ReplayCase:
    snapshot: MarketSnapshot
    future_bars: tuple[ReplayBar, ...]
    scheduled_exit_at: datetime


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    rule_version: str
    starting_cash: int
    ending_cash: int
    cases: int
    trades: int
    no_trades: int
    pending: int
    wins: int
    losses: int
    win_rate_pct: float
    net_pnl: int
    average_trade_pnl: float
    average_return_pct: float
    maximum_drawdown_pct: float
    average_mfe_pct: float
    average_mae_pct: float
    results: tuple[ReplayResult, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["results"] = [result.to_dict() for result in self.results]
        return data


def replay_decision(
    *,
    engine: ClosingBetEngine,
    case: ReplayCase,
    cash: int,
    costs: TradingCosts,
) -> ReplayResult:
    decision = engine.evaluate(case.snapshot, cash=cash)
    if decision.decision == DecisionType.NO_TRADE or decision.position is None:
        return ReplayResult(
            event_id=decision.event_id,
            decision=decision.decision.value,
            stock_code=None,
            stock_name=None,
            entry_at=None,
            entry_price=None,
            entry_quantity=0,
            exits=(),
            remaining_quantity=0,
            gross_pnl=0,
            total_costs=0,
            net_pnl=0,
            return_pct=None,
            mfe_pct=None,
            mae_pct=None,
            outcome=ReplayOutcome.NO_TRADE,
            ending_cash=cash,
            reason_codes=decision.reason_codes,
        )
    return replay_position(
        decision.position,
        bars=case.future_bars,
        scheduled_exit_at=case.scheduled_exit_at,
        starting_cash=cash,
        costs=costs,
        event_id=decision.event_id,
    )


def replay_position(
    position: Position,
    *,
    bars: Iterable[ReplayBar],
    scheduled_exit_at: datetime,
    starting_cash: int,
    costs: TradingCosts,
    event_id: str,
) -> ReplayResult:
    if scheduled_exit_at.tzinfo is None:
        raise ValueError("scheduled exit must be timezone-aware")
    ordered = sorted((bar for bar in bars if bar.observed_at > position.entry_at), key=lambda b: b.observed_at)
    remaining = position.quantity
    exits: list[ReplayExit] = []
    soft_stop_pending = False
    target1_taken = False
    maximum_high = position.entry_price
    minimum_low = position.entry_price
    final_outcome = ReplayOutcome.OPEN_NO_0910_DATA

    for bar in ordered:
        if remaining <= 0:
            break
        maximum_high = max(maximum_high, bar.high)
        minimum_low = min(minimum_low, bar.low)

        if bar.low <= position.emergency_stop:
            price = bar.open if bar.open <= position.emergency_stop else position.emergency_stop
            exits.append(ReplayExit(bar.observed_at, price, remaining, "EMERGENCY_STOP"))
            remaining = 0
            final_outcome = ReplayOutcome.EMERGENCY_STOP
            break

        if position.stop_mode == StopMode.IMMEDIATE and bar.low <= position.stop_price:
            price = bar.open if bar.open <= position.stop_price else position.stop_price
            exits.append(ReplayExit(bar.observed_at, price, remaining, "IMMEDIATE_STOP"))
            remaining = 0
            final_outcome = ReplayOutcome.STOP_LOSS
            break

        if soft_stop_pending:
            if bar.close < position.stop_price:
                exits.append(ReplayExit(bar.observed_at, bar.close, remaining, "5M_CONFIRMED_STOP"))
                remaining = 0
                final_outcome = ReplayOutcome.STOP_LOSS
                break
            soft_stop_pending = False

        if bar.high >= position.target2:
            price = max(position.target2, bar.open) if bar.open >= position.target2 else position.target2
            exits.append(ReplayExit(bar.observed_at, price, remaining, "TARGET2"))
            remaining = 0
            final_outcome = ReplayOutcome.TARGET2
            break

        if not target1_taken and remaining >= 2 and bar.high >= position.target1:
            quantity = max(1, remaining // 2)
            price = max(position.target1, bar.open) if bar.open >= position.target1 else position.target1
            exits.append(ReplayExit(bar.observed_at, price, quantity, "TARGET1"))
            remaining -= quantity
            target1_taken = True

        if position.stop_mode == StopMode.FIVE_MIN_CONFIRMED and bar.close < position.stop_price:
            soft_stop_pending = True

        if bar.observed_at >= scheduled_exit_at and remaining > 0:
            exits.append(ReplayExit(bar.observed_at, bar.close, remaining, "SCHEDULED_0910"))
            remaining = 0
            final_outcome = (
                ReplayOutcome.PARTIAL_THEN_SCHEDULED if target1_taken else ReplayOutcome.SCHEDULED_EXIT
            )
            break

    sold_quantity = sum(exit.quantity for exit in exits)
    gross_proceeds = sum(exit.price * exit.quantity for exit in exits)
    sold_cost_basis = position.entry_price * sold_quantity
    gross_pnl = gross_proceeds - sold_cost_basis
    buy_fee = _cost(sold_cost_basis, costs.buy_fee_bps)
    sell_fee = sum(_cost(exit.price * exit.quantity, costs.sell_fee_bps) for exit in exits)
    sell_tax = sum(_cost(exit.price * exit.quantity, costs.sell_tax_bps) for exit in exits)
    total_costs = buy_fee + sell_fee + sell_tax
    net_pnl = gross_pnl - total_costs
    return_pct = (net_pnl / sold_cost_basis * 100.0) if sold_cost_basis else None
    mfe = (maximum_high / position.entry_price - 1.0) * 100.0
    mae = (minimum_low / position.entry_price - 1.0) * 100.0
    reason_codes = tuple(exit.reason for exit in exits) or ("MISSING_0910_DATA",)
    return ReplayResult(
        event_id=event_id,
        decision=DecisionType.BUY.value,
        stock_code=position.code,
        stock_name=position.name,
        entry_at=position.entry_at,
        entry_price=position.entry_price,
        entry_quantity=position.quantity,
        exits=tuple(exits),
        remaining_quantity=remaining,
        gross_pnl=gross_pnl,
        total_costs=total_costs,
        net_pnl=net_pnl,
        return_pct=return_pct,
        mfe_pct=mfe,
        mae_pct=mae,
        outcome=final_outcome,
        ending_cash=starting_cash + net_pnl,
        reason_codes=reason_codes,
    )


def run_backtest(
    cases: Iterable[ReplayCase],
    *,
    starting_cash: int,
    costs: TradingCosts,
    config: StrategyConfig | None = None,
) -> BacktestSummary:
    engine = ClosingBetEngine(config)
    cash = starting_cash
    equity_peak = float(starting_cash)
    maximum_drawdown = 0.0
    results: list[ReplayResult] = []
    for case in sorted(cases, key=lambda item: item.snapshot.captured_at):
        result = replay_decision(engine=engine, case=case, cash=cash, costs=costs)
        results.append(result)
        if result.outcome != ReplayOutcome.OPEN_NO_0910_DATA:
            cash = result.ending_cash
        equity_peak = max(equity_peak, float(cash))
        if equity_peak > 0:
            maximum_drawdown = max(maximum_drawdown, (equity_peak - cash) / equity_peak * 100.0)

    closed = [
        result for result in results
        if result.outcome not in {ReplayOutcome.NO_TRADE, ReplayOutcome.OPEN_NO_0910_DATA}
    ]
    returns = [result.return_pct for result in closed if result.return_pct is not None]
    mfe_values = [result.mfe_pct for result in closed if result.mfe_pct is not None]
    mae_values = [result.mae_pct for result in closed if result.mae_pct is not None]
    wins = sum(result.net_pnl > 0 for result in closed)
    losses = sum(result.net_pnl < 0 for result in closed)
    return BacktestSummary(
        rule_version=engine.config.rule_version,
        starting_cash=starting_cash,
        ending_cash=cash,
        cases=len(results),
        trades=len(closed),
        no_trades=sum(result.outcome == ReplayOutcome.NO_TRADE for result in results),
        pending=sum(result.outcome == ReplayOutcome.OPEN_NO_0910_DATA for result in results),
        wins=wins,
        losses=losses,
        win_rate_pct=(wins / len(closed) * 100.0) if closed else 0.0,
        net_pnl=cash - starting_cash,
        average_trade_pnl=(sum(result.net_pnl for result in closed) / len(closed)) if closed else 0.0,
        average_return_pct=(sum(returns) / len(returns)) if returns else 0.0,
        maximum_drawdown_pct=maximum_drawdown,
        average_mfe_pct=(sum(mfe_values) / len(mfe_values)) if mfe_values else 0.0,
        average_mae_pct=(sum(mae_values) / len(mae_values)) if mae_values else 0.0,
        results=tuple(results),
    )


def _cost(amount: int, basis_points: float) -> int:
    return floor(amount * basis_points / 10_000.0)
