from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Session(StrEnum):
    KRX_1520 = "KRX_1520"
    NXT_1955 = "NXT_1955"


class DecisionType(StrEnum):
    BUY = "BUY"
    NO_TRADE = "NO_TRADE"


class StopMode(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    FIVE_MIN_CONFIRMED = "5M_CONFIRMED"


class ExitAction(StrEnum):
    HOLD = "HOLD"
    PARTIAL_PROFIT = "PARTIAL_PROFIT"
    FULL_PROFIT = "FULL_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    SCHEDULED_EXIT = "SCHEDULED_EXIT"


@dataclass(frozen=True, slots=True)
class Quote:
    code: str
    name: str
    observed_at: datetime
    price: int
    open_price: int
    high_price: int
    low_price: int
    volume: int
    trading_value: int
    previous_volume: int
    day_change_pct: float
    ma5: float
    ma20: float
    ma120: float | None
    five_min_ma20: float
    five_min_ma20_slope: float
    support_price: int
    nxt_eligible: bool
    theme: str
    catalyst: str
    catalyst_score: float
    catalyst_verified: bool = False
    market: str = ""
    institution_net: int | None = None
    program_net: int | None = None
    best_ask: int | None = None
    best_bid: int | None = None
    total_ask_size: int | None = None
    total_bid_size: int | None = None
    warnings: tuple[str, ...] = ()
    ma60: float | None = None
    rsi14: float | None = None
    atr14: float | None = None
    recent_resistance: float | None = None
    vwap: float | None = None
    five_min_volume_ratio: float | None = None
    last_hour_return_pct: float | None = None
    last_fifteen_min_return_pct: float | None = None
    higher_lows: bool | None = None
    reclaimed_five_min_ma20: bool | None = None
    breakout_level: float | None = None
    breakout_holds: bool | None = None

    @property
    def close_strength(self) -> float:
        span = self.high_price - self.low_price
        if span <= 0:
            return 0.5
        return min(1.0, max(0.0, (self.price - self.low_price) / span))

    @property
    def volume_ratio(self) -> float:
        if self.previous_volume <= 0:
            return 0.0
        return self.volume / self.previous_volume


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    captured_at: datetime
    session: Session
    kospi_change_pct: float
    kosdaq_change_pct: float
    quotes: tuple[Quote, ...]
    source: str
    delayed: bool = False


@dataclass(frozen=True, slots=True)
class Candidate:
    quote: Quote
    score: float
    reasons: tuple[str, ...]
    risks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Position:
    position_id: str
    strategy: str
    session: Session
    code: str
    name: str
    entry_at: datetime
    entry_price: int
    quantity: int
    invested_amount: int
    stop_mode: StopMode
    stop_price: int
    emergency_stop: int
    target1: int
    target2: int
    status: str = "OPEN"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["session"] = self.session.value
        data["stop_mode"] = self.stop_mode.value
        data["entry_at"] = self.entry_at.isoformat()
        return data


@dataclass(frozen=True, slots=True)
class Decision:
    event_id: str
    idempotency_key: str
    decided_at: datetime
    decision: DecisionType
    session: Session
    rule_version: str
    starting_cash: int
    remaining_cash: int
    position: Position | None
    candidates: tuple[Candidate, ...] = ()
    reason_codes: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "idempotency_key": self.idempotency_key,
            "decided_at": self.decided_at.isoformat(),
            "decision": self.decision.value,
            "session": self.session.value,
            "rule_version": self.rule_version,
            "starting_cash": self.starting_cash,
            "remaining_cash": self.remaining_cash,
            "position": self.position.to_dict() if self.position else None,
            "candidates": [
                {
                    "code": c.quote.code,
                    "name": c.quote.name,
                    "reference_price": c.quote.price,
                    "score": round(c.score, 2),
                    "theme": c.quote.theme,
                    "catalyst": c.quote.catalyst,
                    "catalyst_verified": c.quote.catalyst_verified,
                    "market": c.quote.market,
                    "institution_net": c.quote.institution_net,
                    "program_net": c.quote.program_net,
                    "reasons": list(c.reasons),
                    "risks": list(c.risks),
                    "technical": {
                        "close_strength": round(c.quote.close_strength, 4),
                        "volume_ratio": round(c.quote.volume_ratio, 4),
                        "ma5": c.quote.ma5,
                        "ma20": c.quote.ma20,
                        "ma60": c.quote.ma60,
                        "ma120": c.quote.ma120,
                        "five_min_ma20": c.quote.five_min_ma20,
                        "five_min_ma20_slope": c.quote.five_min_ma20_slope,
                        "vwap": c.quote.vwap,
                        "rsi14": c.quote.rsi14,
                        "atr14": c.quote.atr14,
                        "five_min_volume_ratio": c.quote.five_min_volume_ratio,
                        "last_hour_return_pct": c.quote.last_hour_return_pct,
                        "last_fifteen_min_return_pct": c.quote.last_fifteen_min_return_pct,
                        "higher_lows": c.quote.higher_lows,
                        "reclaimed_five_min_ma20": c.quote.reclaimed_five_min_ma20,
                        "breakout_level": c.quote.breakout_level,
                        "breakout_holds": c.quote.breakout_holds,
                        "recent_resistance": c.quote.recent_resistance,
                    },
                }
                for c in self.candidates
            ],
            "reason_codes": list(self.reason_codes),
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ExitObservation:
    observed_at: datetime
    price: int
    five_min_closed_below_stop: bool = False
    following_candle_reclaimed_stop: bool | None = None
    market_shock: bool = False
    catalyst_invalidated: bool = False


@dataclass(frozen=True, slots=True)
class ExitDecision:
    action: ExitAction
    decided_at: datetime
    execution_price: int | None
    execution_quantity: int
    remaining_quantity: int
    realized_pnl: int
    reason_codes: tuple[str, ...]
