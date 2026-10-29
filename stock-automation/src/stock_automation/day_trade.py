from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
from math import log10

from .risk import build_position_plan


KST = timezone(timedelta(hours=9))


class DayTradeDecisionType(StrEnum):
    BUY = "BUY"
    NO_TRADE = "NO_TRADE"


class DayTradeExitAction(StrEnum):
    HOLD = "HOLD"
    PARTIAL_PROFIT = "PARTIAL_PROFIT"
    FULL_EXIT = "FULL_EXIT"
    STOP_LOSS = "STOP_LOSS"


@dataclass(frozen=True, slots=True)
class DayTradeConfig:
    rule_version: str = "day-trade-v0.3"
    entry_start: time = time(9, 10)
    last_entry: time = time(14, 50)
    mandatory_exit: time = time(15, 10)
    maximum_quote_age_seconds: int = 90
    minimum_trading_value: int = 5_000_000_000
    minimum_five_min_volume_ratio: float = 1.30
    minimum_score: float = 65.0
    maximum_day_gain_pct: float = 12.0
    maximum_market_decline_pct: float = -3.0
    maximum_allocation_pct: float = 0.25
    maximum_position_loss: int = 8_000
    maximum_candidates: int = 3
    # Late-entry guard (day-trade-v0.3): distance above the VWAP, in percent.
    maximum_vwap_distance_pct: float = 3.0
    vwap_distance_penalty_start_pct: float = 2.0
    vwap_distance_penalty_per_pct: float = 3.0


@dataclass(frozen=True, slots=True)
class DayTradeQuote:
    code: str
    name: str
    observed_at: datetime
    market: str
    price: int
    high_price: int
    low_price: int
    trading_value: int
    day_change_pct: float
    five_min_ma20: float
    five_min_ma20_slope: float
    vwap: float
    five_min_volume_ratio: float
    support_price: int
    nxt_eligible: bool
    catalyst: str
    catalyst_verified: bool
    theme: str = ""
    breakout_holds: bool = False
    reclaimed_ma20: bool = False
    higher_lows: bool = False
    last_fifteen_min_return_pct: float = 0.0
    institution_net: int | None = None
    program_net: int | None = None
    best_ask: int | None = None
    warnings: tuple[str, ...] = ()

    @property
    def range_position(self) -> float:
        span = self.high_price - self.low_price
        if span <= 0:
            return 0.5
        return min(1.0, max(0.0, (self.price - self.low_price) / span))


@dataclass(frozen=True, slots=True)
class DayTradeSnapshot:
    captured_at: datetime
    kospi_change_pct: float
    kosdaq_change_pct: float
    quotes: tuple[DayTradeQuote, ...]
    source: str
    delayed: bool = False


@dataclass(frozen=True, slots=True)
class DayTradeCandidate:
    quote: DayTradeQuote
    score: float
    reasons: tuple[str, ...]
    risks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DayTradePosition:
    position_id: str
    code: str
    name: str
    entry_at: datetime
    entry_price: int
    quantity: int
    invested_amount: int
    remaining_cash: int
    stop_price: int
    emergency_stop: int
    target1: int
    target2: int
    strategy: str = "DAY_TRADE"
    status: str = "OPEN"


@dataclass(frozen=True, slots=True)
class DayTradeDecision:
    event_id: str
    idempotency_key: str
    decided_at: datetime
    decision: DayTradeDecisionType
    rule_version: str
    starting_cash: int
    remaining_cash: int
    position: DayTradePosition | None
    candidates: tuple[DayTradeCandidate, ...]
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["decided_at"] = self.decided_at.isoformat()
        payload["decision"] = self.decision.value
        if self.position:
            payload["position"]["entry_at"] = self.position.entry_at.isoformat()
        for row, candidate in zip(payload["candidates"], self.candidates):
            row["quote"]["observed_at"] = candidate.quote.observed_at.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class DayTradeObservation:
    observed_at: datetime
    price: int
    five_min_closed_below_stop: bool = False
    following_candle_reclaimed_stop: bool | None = None
    market_shock: bool = False
    catalyst_invalidated: bool = False


@dataclass(frozen=True, slots=True)
class DayTradeExitDecision:
    action: DayTradeExitAction
    decided_at: datetime
    execution_price: int | None
    execution_quantity: int
    remaining_quantity: int
    realized_pnl: int
    reason_codes: tuple[str, ...]


class DayTradeEngine:
    """Paper-only intraday engine, isolated from closing and medium-term state."""

    def __init__(self, config: DayTradeConfig | None = None) -> None:
        self.config = config or DayTradeConfig()

    def evaluate(self, snapshot: DayTradeSnapshot, *, cash: int) -> DayTradeDecision:
        self._validate_snapshot(snapshot)
        candidates = tuple(self._rank(snapshot)[: self.config.maximum_candidates])
        identity = f"{snapshot.captured_at.astimezone(KST):%Y%m%dT%H%M}:DAY_TRADE_SCAN"
        suffix = sha256(identity.encode()).hexdigest()[:10]
        event_id = f"DAY-{snapshot.captured_at.astimezone(KST):%Y%m%d%H%M}-{suffix}"
        if not candidates or candidates[0].score < self.config.minimum_score:
            return DayTradeDecision(
                event_id, identity, snapshot.captured_at, DayTradeDecisionType.NO_TRADE,
                self.config.rule_version, cash, cash, None, candidates,
                ("NO_QUALIFYING_DAY_TRADE_CANDIDATE",),
            )

        selected = candidates[0]
        entry = selected.quote.best_ask or selected.quote.price
        plan = build_position_plan(
            cash=cash,
            entry_price=entry,
            support_price=selected.quote.support_price,
            max_allocation_pct=self.config.maximum_allocation_pct,
            max_loss=self.config.maximum_position_loss,
        )
        if plan is None:
            return DayTradeDecision(
                event_id, identity, snapshot.captured_at, DayTradeDecisionType.NO_TRADE,
                self.config.rule_version, cash, cash, None, candidates,
                ("DAY_TRADE_POSITION_SIZE_ZERO",),
            )
        position = DayTradePosition(
            position_id=f"DTP-{sha256((identity + selected.quote.code).encode()).hexdigest()[:12]}",
            code=selected.quote.code,
            name=selected.quote.name,
            entry_at=snapshot.captured_at,
            entry_price=entry,
            quantity=plan.quantity,
            invested_amount=plan.invested_amount,
            remaining_cash=plan.remaining_cash,
            stop_price=plan.stop_price,
            emergency_stop=plan.emergency_stop,
            target1=plan.target1,
            target2=plan.target2,
        )
        return DayTradeDecision(
            event_id, identity, snapshot.captured_at, DayTradeDecisionType.BUY,
            self.config.rule_version, cash, plan.remaining_cash, position, candidates,
            ("TOP_INTRADAY_SCORE_SELECTED", "PAPER_EXECUTION_ONLY"),
        )

    def review(
        self,
        position: DayTradePosition,
        observation: DayTradeObservation,
        *,
        remaining_quantity: int | None = None,
    ) -> DayTradeExitDecision:
        quantity = position.quantity if remaining_quantity is None else remaining_quantity
        if quantity <= 0 or observation.price <= 0:
            raise ValueError("positive quantity and observation price are required")
        if observation.observed_at.tzinfo is None:
            raise ValueError("observation timestamp must be timezone-aware")
        if observation.observed_at < position.entry_at:
            raise ValueError("position cannot be reviewed before entry")
        hard_stop = (
            observation.price <= position.emergency_stop
            or observation.market_shock
            or observation.catalyst_invalidated
        )
        confirmed_stop = (
            observation.five_min_closed_below_stop
            and observation.following_candle_reclaimed_stop is False
        )
        if hard_stop or confirmed_stop:
            return self._exit(
                position, observation, quantity, DayTradeExitAction.STOP_LOSS,
                ("EMERGENCY_INVALIDATION",) if hard_stop else ("FIVE_MIN_STOP_CONFIRMED",),
            )
        observed_kst = observation.observed_at.astimezone(KST)
        entry_date = position.entry_at.astimezone(KST).date()
        if (
            observed_kst.date() > entry_date
            or observed_kst.time() >= self.config.mandatory_exit
        ):
            return self._exit(
                position, observation, quantity, DayTradeExitAction.FULL_EXIT,
                ("MANDATORY_SAME_DAY_EXIT",),
            )
        if observation.price >= position.target2:
            return self._exit(
                position, observation, quantity, DayTradeExitAction.FULL_EXIT,
                ("TARGET2_REACHED",),
            )
        if observation.price >= position.target1 and quantity == position.quantity and quantity >= 2:
            sell = max(1, quantity // 2)
            return DayTradeExitDecision(
                DayTradeExitAction.PARTIAL_PROFIT, observation.observed_at,
                observation.price, sell, quantity - sell,
                (observation.price - position.entry_price) * sell,
                ("TARGET1_REACHED",),
            )
        return DayTradeExitDecision(
            DayTradeExitAction.HOLD, observation.observed_at, None, 0, quantity, 0,
            ("NO_EXIT_TRIGGER",),
        )

    def _validate_snapshot(self, snapshot: DayTradeSnapshot) -> None:
        if snapshot.captured_at.tzinfo is None:
            raise ValueError("snapshot timestamp must be timezone-aware")
        if snapshot.delayed:
            raise ValueError("delayed day-trade snapshot cannot produce a paper fill")
        local_time = snapshot.captured_at.astimezone(KST).time()
        if not self.config.entry_start <= local_time <= self.config.last_entry:
            raise ValueError("day-trade entry scan is outside the approved window")

    def _rank(self, snapshot: DayTradeSnapshot) -> list[DayTradeCandidate]:
        rows = [self._score(snapshot, quote) for quote in snapshot.quotes]
        accepted = [row for row in rows if row is not None]
        accepted.sort(key=lambda row: row.score, reverse=True)
        selected: list[DayTradeCandidate] = []
        themes: set[str] = set()
        for row in accepted:
            theme = row.quote.theme.strip().lower() or f"code:{row.quote.code}"
            if theme in themes:
                continue
            themes.add(theme)
            selected.append(row)
        return selected

    def _score(
        self, snapshot: DayTradeSnapshot, quote: DayTradeQuote
    ) -> DayTradeCandidate | None:
        if quote.observed_at.tzinfo is None:
            return None
        age = (snapshot.captured_at.astimezone(timezone.utc) - quote.observed_at.astimezone(timezone.utc)).total_seconds()
        market_change = self._market_change(snapshot, quote.market)
        if (
            age < 0
            or age > self.config.maximum_quote_age_seconds
            or quote.nxt_eligible
            or quote.price <= 0
            or quote.price > 150_000
            or quote.trading_value < self.config.minimum_trading_value
            or not -3.0 <= quote.day_change_pct <= self.config.maximum_day_gain_pct
            or market_change <= self.config.maximum_market_decline_pct
            or quote.five_min_volume_ratio < self.config.minimum_five_min_volume_ratio
            or quote.price < quote.five_min_ma20
            or quote.five_min_ma20_slope <= 0
            or quote.vwap <= 0
            or quote.price < quote.vwap
            or (quote.price / quote.vwap - 1.0) * 100.0 > self.config.maximum_vwap_distance_pct
            or quote.support_price <= 0
            or quote.support_price >= quote.price
            or not (quote.breakout_holds or quote.reclaimed_ma20)
        ):
            return None

        score = min(15.0, max(0.0, (log10(quote.trading_value) - 9.0) * 7.5))
        score += min(15.0, (quote.five_min_volume_ratio - 1.0) * 12.0)
        score += quote.range_position * 10.0
        score += 15.0
        score += 15.0 if quote.breakout_holds else 10.0
        score += 8.0 if quote.higher_lows else 0.0
        if 0.1 <= quote.last_fifteen_min_return_pct <= 3.0:
            score += 5.0
        # The catalyst is scored, not required, so ranked candidates without a
        # verified same-day catalyst can still qualify on chart and flow alone.
        catalyst_confirmed = quote.catalyst_verified and bool(quote.catalyst.strip())
        score += 10.0 if catalyst_confirmed else 0.0
        score += 3.0 if (quote.institution_net or 0) > 0 else 0.0
        score += 3.0 if (quote.program_net or 0) > 0 else 0.0
        risks = list(quote.warnings)
        if not catalyst_confirmed:
            risks.append("CATALYST_UNKNOWN")
        if market_change < -1.0:
            score -= min(10.0, (-1.0 - market_change) * 5.0)
            risks.append("MARKET_WEAKNESS")
        if quote.day_change_pct > 8.0:
            score -= (quote.day_change_pct - 8.0) * 2.0
            risks.append("LATE_ENTRY_RISK")
        vwap_distance = (quote.price / quote.vwap - 1.0) * 100.0
        if vwap_distance > self.config.vwap_distance_penalty_start_pct:
            score -= (
                vwap_distance - self.config.vwap_distance_penalty_start_pct
            ) * self.config.vwap_distance_penalty_per_pct
            risks.append("LATE_ENTRY_RISK")
        reasons = ["ABOVE_5M_MA20", "ABOVE_VWAP", "INTRADAY_VOLUME_EXPANSION"]
        if catalyst_confirmed:
            reasons.append("CATALYST_CONFIRMED")
        reasons.append("BREAKOUT_HOLD" if quote.breakout_holds else "MA20_RECLAIM")
        if quote.higher_lows:
            reasons.append("FIVE_MIN_HIGHER_LOWS")
        return DayTradeCandidate(
            quote, round(min(100.0, max(0.0, score)), 4),
            tuple(reasons), tuple(dict.fromkeys(risks)),
        )

    @staticmethod
    def _market_change(snapshot: DayTradeSnapshot, market: str) -> float:
        normalized = market.strip().upper()
        if normalized == "KOSPI":
            return snapshot.kospi_change_pct
        if normalized == "KOSDAQ":
            return snapshot.kosdaq_change_pct
        return min(snapshot.kospi_change_pct, snapshot.kosdaq_change_pct)

    @staticmethod
    def _exit(
        position: DayTradePosition,
        observation: DayTradeObservation,
        quantity: int,
        action: DayTradeExitAction,
        reasons: tuple[str, ...],
    ) -> DayTradeExitDecision:
        return DayTradeExitDecision(
            action, observation.observed_at, observation.price, quantity, 0,
            (observation.price - position.entry_price) * quantity, reasons,
        )
