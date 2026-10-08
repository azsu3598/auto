from __future__ import annotations

from dataclasses import dataclass
from math import floor

from .backtest import TradingCosts


@dataclass(frozen=True, slots=True)
class EntryCashFlow:
    principal: int
    buy_fee: int
    cash_debit: int


@dataclass(frozen=True, slots=True)
class ExitCashFlow:
    cost_basis: int
    gross_proceeds: int
    gross_pnl: int
    allocated_buy_fee: int
    sell_fee: int
    sell_tax: int
    total_costs: int
    net_proceeds: int
    net_pnl: int


def trading_cost(amount: int, basis_points: float) -> int:
    if amount < 0 or basis_points < 0:
        raise ValueError("amount and basis points must be non-negative")
    return floor(amount * basis_points / 10_000.0)


def entry_cash_flow(price: int, quantity: int, costs: TradingCosts) -> EntryCashFlow:
    if price <= 0 or quantity <= 0:
        raise ValueError("entry price and quantity must be positive")
    principal = price * quantity
    buy_fee = trading_cost(principal, costs.buy_fee_bps)
    return EntryCashFlow(principal, buy_fee, principal + buy_fee)


def exit_cash_flow(
    *, entry_price: int, exit_price: int, quantity: int, costs: TradingCosts
) -> ExitCashFlow:
    if min(entry_price, exit_price, quantity) <= 0:
        raise ValueError("exit cash-flow inputs must be positive")
    cost_basis = entry_price * quantity
    proceeds = exit_price * quantity
    buy_fee = trading_cost(cost_basis, costs.buy_fee_bps)
    sell_fee = trading_cost(proceeds, costs.sell_fee_bps)
    sell_tax = trading_cost(proceeds, costs.sell_tax_bps)
    total_costs = buy_fee + sell_fee + sell_tax
    return ExitCashFlow(
        cost_basis=cost_basis,
        gross_proceeds=proceeds,
        gross_pnl=proceeds - cost_basis,
        allocated_buy_fee=buy_fee,
        sell_fee=sell_fee,
        sell_tax=sell_tax,
        total_costs=total_costs,
        net_proceeds=proceeds - sell_fee - sell_tax,
        net_pnl=proceeds - cost_basis - total_costs,
    )
