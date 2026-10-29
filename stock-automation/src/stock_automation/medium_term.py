from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from math import floor

from .risk import _tick_round


class MediumTermDecisionType(StrEnum):
    SIGNAL = "SIGNAL"
    NO_TRADE = "NO_TRADE"


class MediumTermEntryAction(StrEnum):
    ENTER = "ENTER"
    CANCEL = "CANCEL"


class MediumTermExitAction(StrEnum):
    HOLD = "HOLD"
    PARTIAL_PROFIT = "PARTIAL_PROFIT"
    FULL_PROFIT = "FULL_PROFIT"
    THESIS_STOP = "THESIS_STOP"
    MAX_HOLD_EXIT = "MAX_HOLD_EXIT"


@dataclass(frozen=True, slots=True)
class MediumTermConfig:
    rule_version: str = "medium-chart-v0.1"
    maximum_snapshot_age_seconds: int = 36 * 60 * 60
    minimum_trading_value: int = 2_000_000_000
    minimum_market_cap: int = 100_000_000_000
    minimum_score: float = 68.0
    maximum_rsi14: float = 72.0
    maximum_ma20_distance_pct: float = 10.0
    maximum_twenty_day_return_pct: float = 22.0
    maximum_invalidation_distance_pct: float = 12.0
    maximum_allocation_pct: float = 0.30
    maximum_position_loss: int = 6_700  # 200,000 KRW principal (2026-10-29)
    maximum_candidates: int = 3
    maximum_entry_gap_pct: float = 3.0


@dataclass(frozen=True, slots=True)
class MediumTermQuote:
    code: str
    name: str
    observed_at: datetime
    price: int
    trading_value: int
    market_cap: int
    nxt_eligible: bool
    ma20: float
    ma60: float
    ma120: float
    ma20_slope_5d: float
    ma60_slope_10d: float
    rsi14: float
    atr14: float
    volume_ratio20: float
    return20_pct: float
    return60_pct: float
    support_price: int
    resistance_price: int | None
    per: float
    pbr: float
    roe: float
    sales: int
    operating_profit: int
    net_income: int
    fundamental_source: str
    fundamental_observed_at: datetime
    disclosure_checked: bool
    risk_flags: tuple[str, ...] = ()
    catalyst: str = ""


@dataclass(frozen=True, slots=True)
class MediumTermSnapshot:
    captured_at: datetime
    quotes: tuple[MediumTermQuote, ...]
    source: str
    delayed: bool = False


@dataclass(frozen=True, slots=True)
class MediumTermCandidate:
    quote: MediumTermQuote
    score: float
    reasons: tuple[str, ...]
    risks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediumTermEntryPlan:
    plan_id: str
    code: str
    name: str
    signal_at: datetime
    reference_price: int
    suggested_quantity: int
    indicative_amount: int
    maximum_entry_price: int
    thesis_invalidation: int
    emergency_stop: int
    target1: int
    target2: int
    review_after_trading_days: int = 20
    maximum_holding_trading_days: int = 40


@dataclass(frozen=True, slots=True)
class MediumTermPosition:
    position_id: str
    plan_id: str
    code: str
    name: str
    signal_at: datetime
    reference_price: int
    entry_at: datetime
    entry_price: int
    quantity: int
    invested_amount: int
    remaining_cash: int
    thesis_invalidation: int
    emergency_stop: int
    target1: int
    target2: int
    review_after_trading_days: int = 20
    maximum_holding_trading_days: int = 40


@dataclass(frozen=True, slots=True)
class MediumTermEntryConfirmation:
    action: MediumTermEntryAction
    observed_at: datetime
    observed_price: int
    position: MediumTermPosition | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediumTermExitDecision:
    action: MediumTermExitAction
    decided_at: datetime
    execution_price: int | None
    execution_quantity: int
    remaining_quantity: int
    realized_pnl: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MediumTermDecision:
    event_id: str
    idempotency_key: str
    decided_at: datetime
    decision: MediumTermDecisionType
    rule_version: str
    starting_cash: int
    entry_plan: MediumTermEntryPlan | None
    candidates: tuple[MediumTermCandidate, ...]
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["decided_at"] = self.decided_at.isoformat()
        payload["decision"] = self.decision.value
        if self.entry_plan:
            payload["entry_plan"]["signal_at"] = self.entry_plan.signal_at.isoformat()
        for row, candidate in zip(payload["candidates"], self.candidates):
            row["quote"]["observed_at"] = candidate.quote.observed_at.isoformat()
            row["quote"]["fundamental_observed_at"] = (
                candidate.quote.fundamental_observed_at.isoformat()
            )
        return payload


class MediumTermEngine:
    """Daily-chart-first, 20–40 trading-day paper strategy.

    This engine deliberately has no dependency on closing-bet models, capital or
    ledgers. A disclosure check is mandatory because a technically attractive chart
    is not enough for a multi-week holding period.
    """

    BLOCKING_RISKS = {
        "AUDIT_RISK",
        "CAPITAL_IMPAIRMENT",
        "DELISTING_RISK",
        "DILUTION_EVENT",
        "EARNINGS_INVALIDATED",
        "GOING_CONCERN",
        "TRADING_HALT_RISK",
    }

    def __init__(self, config: MediumTermConfig | None = None) -> None:
        self.config = config or MediumTermConfig()

    def evaluate(self, snapshot: MediumTermSnapshot, *, cash: int) -> MediumTermDecision:
        self._validate_snapshot(snapshot)
        candidates = tuple(self._rank(snapshot)[: self.config.maximum_candidates])
        identity = f"{snapshot.captured_at.date()}:MEDIUM_TERM"
        suffix = sha256(identity.encode()).hexdigest()[:10]
        event_id = f"MED-{snapshot.captured_at:%Y%m%d}-{suffix}"
        if not candidates or candidates[0].score < self.config.minimum_score:
            return MediumTermDecision(
                event_id=event_id,
                idempotency_key=identity,
                decided_at=snapshot.captured_at,
                decision=MediumTermDecisionType.NO_TRADE,
                rule_version=self.config.rule_version,
                starting_cash=cash,
                entry_plan=None,
                candidates=candidates,
                reason_codes=("NO_QUALIFYING_MEDIUM_TERM_CANDIDATE",),
            )

        selected = candidates[0]
        entry_plan = self._entry_plan(selected.quote, cash, identity)
        if entry_plan is None:
            return MediumTermDecision(
                event_id=event_id,
                idempotency_key=identity,
                decided_at=snapshot.captured_at,
                decision=MediumTermDecisionType.NO_TRADE,
                rule_version=self.config.rule_version,
                starting_cash=cash,
                entry_plan=None,
                candidates=candidates,
                reason_codes=("MEDIUM_TERM_POSITION_SIZE_ZERO",),
            )
        return MediumTermDecision(
            event_id=event_id,
            idempotency_key=identity,
            decided_at=snapshot.captured_at,
            decision=MediumTermDecisionType.SIGNAL,
            rule_version=self.config.rule_version,
            starting_cash=cash,
            entry_plan=entry_plan,
            candidates=candidates,
            reason_codes=("TOP_DAILY_CHART_SELECTED", "NEXT_SESSION_CONFIRMATION_REQUIRED"),
        )

    def _validate_snapshot(self, snapshot: MediumTermSnapshot) -> None:
        if snapshot.captured_at.tzinfo is None:
            raise ValueError("snapshot timestamp must be timezone-aware")
        if snapshot.delayed:
            raise ValueError("delayed medium-term snapshot is not executable")
        if not snapshot.quotes:
            raise ValueError("medium-term snapshot contains no quotes")

    def _rank(self, snapshot: MediumTermSnapshot) -> list[MediumTermCandidate]:
        rows = []
        for quote in snapshot.quotes:
            candidate = self._score(snapshot, quote)
            if candidate:
                rows.append(candidate)
        return sorted(rows, key=lambda row: row.score, reverse=True)

    def _score(
        self, snapshot: MediumTermSnapshot, q: MediumTermQuote
    ) -> MediumTermCandidate | None:
        cfg = self.config
        age = (
            snapshot.captured_at.astimezone(timezone.utc)
            - q.observed_at.astimezone(timezone.utc)
        ).total_seconds()
        fundamental_age = (
            snapshot.captured_at.astimezone(timezone.utc)
            - q.fundamental_observed_at.astimezone(timezone.utc)
        ).total_seconds()
        if age < -5 or age > cfg.maximum_snapshot_age_seconds:
            return None
        if fundamental_age < -5 or fundamental_age > 14 * 24 * 60 * 60:
            return None
        if q.nxt_eligible or not q.disclosure_checked:
            return None
        if self.BLOCKING_RISKS.intersection(q.risk_flags):
            return None
        if q.price <= 0 or q.trading_value < cfg.minimum_trading_value:
            return None
        if q.market_cap < cfg.minimum_market_cap:
            return None
        if min(q.ma20, q.ma60, q.ma120, q.atr14) <= 0:
            return None
        if q.price < q.ma60 * 0.97 or q.ma20_slope_5d <= 0 or q.ma60_slope_10d <= 0:
            return None
        if not (38.0 <= q.rsi14 <= cfg.maximum_rsi14):
            return None
        ma20_distance = (q.price / q.ma20 - 1.0) * 100.0
        if ma20_distance > cfg.maximum_ma20_distance_pct:
            return None
        if q.return20_pct > cfg.maximum_twenty_day_return_pct:
            return None
        if q.support_price <= 0 or q.support_price >= q.price:
            return None
        invalidation_distance = (q.price - q.support_price) / q.price * 100.0
        if invalidation_distance > cfg.maximum_invalidation_distance_pct:
            return None
        if q.operating_profit <= 0 or q.net_income <= 0 or q.sales <= 0 or q.roe <= 0:
            return None
        if q.per <= 0 or q.pbr <= 0:
            return None

        score = 0.0
        reasons: list[str] = []
        risks = list(q.risk_flags)
        if q.price >= q.ma20:
            score += 10
            reasons.append("ABOVE_MA20")
        if q.price >= q.ma60:
            score += 10
            reasons.append("ABOVE_MA60")
        if q.price >= q.ma120:
            score += 8
            reasons.append("ABOVE_MA120")
        if q.ma20 > q.ma60 > q.ma120:
            score += 15
            reasons.append("BULLISH_MA_ALIGNMENT")
        else:
            score += 5
        if 48 <= q.rsi14 <= 65:
            score += 8
            reasons.append("RSI_HEALTHY")
        if 1.0 <= q.volume_ratio20 <= 2.5:
            score += 7
            reasons.append("CONTROLLED_VOLUME_EXPANSION")
        elif q.volume_ratio20 > 4.0:
            risks.append("VOLUME_SPIKE")
        if 0 <= q.return20_pct <= 15:
            score += 8
            reasons.append("CONTROLLED_20D_MOMENTUM")
        if q.return60_pct > 0:
            score += 4
        reward_room = (
            ((q.resistance_price / q.price) - 1.0) * 100.0
            if q.resistance_price and q.resistance_price > q.price
            else None
        )
        if reward_room is None or reward_room >= invalidation_distance * 1.5:
            score += 8
            reasons.append("ACCEPTABLE_REWARD_RISK")
        else:
            score -= 8
            risks.append("NEAR_RESISTANCE")

        if 0 < q.per <= 20:
            score += 5
            reasons.append("PER_REASONABLE")
        elif q.per > 40:
            score -= 5
            risks.append("HIGH_PER")
        if 0 < q.pbr <= 2.5:
            score += 4
            reasons.append("PBR_REASONABLE")
        elif q.pbr > 5:
            score -= 4
            risks.append("HIGH_PBR")
        if q.roe >= 10:
            score += 6
            reasons.append("ROE_POSITIVE")
        else:
            score += 2
        if q.operating_profit > 0 and q.net_income > 0:
            score += 7
            reasons.append("PROFITABLE")
        if not q.catalyst.strip():
            risks.append("CATALYST_UNKNOWN")

        return MediumTermCandidate(
            quote=q,
            score=round(score, 4),
            reasons=tuple(reasons),
            risks=tuple(dict.fromkeys(risks)),
        )

    def _entry_plan(
        self, quote: MediumTermQuote, cash: int, identity: str
    ) -> MediumTermEntryPlan | None:
        if cash <= 0:
            return None
        stop = _tick_round(max(quote.support_price, quote.price - quote.atr14 * 2.0))
        if stop >= quote.price:
            return None
        emergency = _tick_round(min(stop * 0.97, quote.price - quote.atr14 * 3.0))
        per_share_risk = quote.price - stop
        allocation_cap = floor(cash * self.config.maximum_allocation_pct)
        quantity = min(
            allocation_cap // quote.price,
            self.config.maximum_position_loss // per_share_risk,
        )
        if quantity < 1:
            return None
        invested = quantity * quote.price
        first = quote.price + per_share_risk * 2.0
        if quote.resistance_price and quote.resistance_price > quote.price:
            first = min(first, quote.resistance_price)
        return MediumTermEntryPlan(
            plan_id=f"MEDPLAN-{sha256((identity + quote.code).encode()).hexdigest()[:12]}",
            code=quote.code,
            name=quote.name,
            signal_at=quote.observed_at,
            reference_price=quote.price,
            suggested_quantity=quantity,
            indicative_amount=invested,
            maximum_entry_price=_tick_round(
                quote.price * (1.0 + self.config.maximum_entry_gap_pct / 100.0)
            ),
            thesis_invalidation=stop,
            emergency_stop=emergency,
            target1=_tick_round(first),
            target2=_tick_round(quote.price + per_share_risk * 3.0),
        )


def confirm_medium_term_entry(
    plan: MediumTermEntryPlan,
    *,
    observed_at: datetime,
    observed_price: int,
    cash: int,
    risk_flags: tuple[str, ...] = (),
    disclosure_checked: bool = True,
    trading_days_since_signal: int = 1,
    config: MediumTermConfig | None = None,
) -> MediumTermEntryConfirmation:
    """Confirm a prior after-close signal at the first verifiable next-session price."""
    cfg = config or MediumTermConfig()
    if observed_at.tzinfo is None or plan.signal_at.tzinfo is None:
        raise ValueError("entry timestamps must be timezone-aware")
    if observed_at.date() <= plan.signal_at.date():
        raise ValueError("entry confirmation must occur on a later trading date")
    if trading_days_since_signal != 1:
        return _cancel_entry(observed_at, observed_price, "ENTRY_WINDOW_EXPIRED")
    if observed_price <= 0 or cash <= 0:
        return _cancel_entry(observed_at, observed_price, "INVALID_ENTRY_INPUT")
    if not disclosure_checked:
        return _cancel_entry(observed_at, observed_price, "DISCLOSURE_NOT_REVERIFIED")
    if MediumTermEngine.BLOCKING_RISKS.intersection(risk_flags):
        return _cancel_entry(observed_at, observed_price, "DISCLOSURE_RISK_AFTER_SIGNAL")
    if observed_price > plan.maximum_entry_price:
        return _cancel_entry(observed_at, observed_price, "ENTRY_GAP_TOO_HIGH")
    if observed_price <= plan.thesis_invalidation:
        return _cancel_entry(observed_at, observed_price, "THESIS_INVALID_BEFORE_ENTRY")

    per_share_risk = observed_price - plan.thesis_invalidation
    reward = plan.target1 - observed_price
    if per_share_risk <= 0 or reward <= 0 or reward / per_share_risk < 1.2:
        return _cancel_entry(observed_at, observed_price, "ENTRY_REWARD_RISK_DAMAGED")
    quantity = min(
        floor(cash * cfg.maximum_allocation_pct) // observed_price,
        cfg.maximum_position_loss // per_share_risk,
    )
    if quantity < 1:
        return _cancel_entry(observed_at, observed_price, "ENTRY_POSITION_SIZE_ZERO")
    invested = observed_price * quantity
    position_id = f"MEDPOS-{sha256((plan.plan_id + observed_at.isoformat()).encode()).hexdigest()[:12]}"
    position = MediumTermPosition(
        position_id=position_id,
        plan_id=plan.plan_id,
        code=plan.code,
        name=plan.name,
        signal_at=plan.signal_at,
        reference_price=plan.reference_price,
        entry_at=observed_at,
        entry_price=observed_price,
        quantity=quantity,
        invested_amount=invested,
        remaining_cash=cash - invested,
        thesis_invalidation=plan.thesis_invalidation,
        emergency_stop=plan.emergency_stop,
        target1=plan.target1,
        target2=max(plan.target2, _tick_round(observed_price + per_share_risk * 2.5)),
        review_after_trading_days=plan.review_after_trading_days,
        maximum_holding_trading_days=plan.maximum_holding_trading_days,
    )
    return MediumTermEntryConfirmation(
        action=MediumTermEntryAction.ENTER,
        observed_at=observed_at,
        observed_price=observed_price,
        position=position,
        reason_codes=("NEXT_SESSION_PRICE_CONFIRMED", "PAPER_EXECUTION_ONLY"),
    )


def review_medium_term_position(
    position: MediumTermPosition,
    *,
    observed_at: datetime,
    closing_price: int,
    trading_days_held: int,
    risk_flags: tuple[str, ...] = (),
    remaining_quantity: int | None = None,
) -> MediumTermExitDecision:
    """Review a medium-term paper position using a verified daily close."""
    if observed_at.tzinfo is None or position.entry_at.tzinfo is None:
        raise ValueError("review timestamps must be timezone-aware")
    if observed_at < position.entry_at:
        raise ValueError("position cannot be reviewed before entry")
    if closing_price <= 0 or trading_days_held < 0:
        raise ValueError("invalid medium-term review input")
    quantity = position.quantity if remaining_quantity is None else remaining_quantity
    if quantity <= 0 or quantity > position.quantity:
        raise ValueError("invalid remaining quantity")

    if MediumTermEngine.BLOCKING_RISKS.intersection(risk_flags):
        return _medium_exit(
            position, observed_at, closing_price, quantity,
            MediumTermExitAction.THESIS_STOP, ("DISCLOSURE_THESIS_INVALIDATED",),
        )
    if closing_price <= position.emergency_stop:
        return _medium_exit(
            position, observed_at, closing_price, quantity,
            MediumTermExitAction.THESIS_STOP, ("EMERGENCY_STOP_CLOSE",),
        )
    if closing_price <= position.thesis_invalidation:
        return _medium_exit(
            position, observed_at, closing_price, quantity,
            MediumTermExitAction.THESIS_STOP, ("DAILY_CLOSE_BELOW_THESIS",),
        )
    if closing_price >= position.target2:
        return _medium_exit(
            position, observed_at, closing_price, quantity,
            MediumTermExitAction.FULL_PROFIT, ("TARGET2_REACHED",),
        )
    if closing_price >= position.target1 and quantity == position.quantity and quantity >= 2:
        sell_quantity = max(1, quantity // 2)
        return MediumTermExitDecision(
            action=MediumTermExitAction.PARTIAL_PROFIT,
            decided_at=observed_at,
            execution_price=closing_price,
            execution_quantity=sell_quantity,
            remaining_quantity=quantity - sell_quantity,
            realized_pnl=(closing_price - position.entry_price) * sell_quantity,
            reason_codes=("TARGET1_REACHED",),
        )
    if trading_days_held >= position.maximum_holding_trading_days:
        return _medium_exit(
            position, observed_at, closing_price, quantity,
            MediumTermExitAction.MAX_HOLD_EXIT, ("MAXIMUM_HOLDING_PERIOD",),
        )
    reasons = (
        "SCHEDULED_20D_REVIEW"
        if trading_days_held >= position.review_after_trading_days
        else "THESIS_STILL_VALID"
    )
    return MediumTermExitDecision(
        action=MediumTermExitAction.HOLD,
        decided_at=observed_at,
        execution_price=None,
        execution_quantity=0,
        remaining_quantity=quantity,
        realized_pnl=0,
        reason_codes=(reasons,),
    )


def _cancel_entry(
    observed_at: datetime, observed_price: int, reason: str
) -> MediumTermEntryConfirmation:
    return MediumTermEntryConfirmation(
        action=MediumTermEntryAction.CANCEL,
        observed_at=observed_at,
        observed_price=observed_price,
        position=None,
        reason_codes=(reason,),
    )


def _medium_exit(
    position: MediumTermPosition,
    observed_at: datetime,
    price: int,
    quantity: int,
    action: MediumTermExitAction,
    reasons: tuple[str, ...],
) -> MediumTermExitDecision:
    return MediumTermExitDecision(
        action=action,
        decided_at=observed_at,
        execution_price=price,
        execution_quantity=quantity,
        remaining_quantity=0,
        realized_pnl=(price - position.entry_price) * quantity,
        reason_codes=reasons,
    )
