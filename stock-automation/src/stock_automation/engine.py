from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from math import log10

from .config import StrategyConfig
from .models import (
    Candidate,
    Decision,
    DecisionType,
    MarketSnapshot,
    Position,
    Quote,
    StopMode,
)
from .risk import build_position_plan


def _age_seconds(newer: datetime, older: datetime) -> float:
    if newer.tzinfo is None or older.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return (newer.astimezone(timezone.utc) - older.astimezone(timezone.utc)).total_seconds()


class ClosingBetEngine:
    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()

    def evaluate(self, snapshot: MarketSnapshot, *, cash: int) -> Decision:
        self._validate_snapshot(snapshot)
        final = list(self.rank_candidates(snapshot))[: self.config.max_final_candidates]
        idempotency_key = (
            f"{snapshot.captured_at.date()}:{snapshot.session.value}:CLOSING_BET"
        )
        stable_suffix = sha256(idempotency_key.encode("utf-8")).hexdigest()[:10]
        event_id = f"SIM-{snapshot.captured_at:%Y%m%d}-{snapshot.session.value}-{stable_suffix}"

        if not final or final[0].score < self.config.minimum_score:
            reason = "MARKET_DATA_UNAVAILABLE" if not snapshot.quotes else "NO_QUALIFYING_CANDIDATE"
            return Decision(
                event_id=event_id,
                idempotency_key=idempotency_key,
                decided_at=snapshot.captured_at,
                decision=DecisionType.NO_TRADE,
                session=snapshot.session,
                rule_version=self.config.rule_version,
                starting_cash=cash,
                remaining_cash=cash,
                position=None,
                candidates=tuple(final),
                reason_codes=(reason,),
                notes="Selection threshold or mandatory risk filters were not satisfied.",
            )

        selected = final[0]
        entry = selected.quote.best_ask or selected.quote.price
        plan = build_position_plan(
            cash=cash,
            entry_price=entry,
            support_price=selected.quote.support_price,
            max_allocation_pct=self.config.max_allocation_pct,
            max_loss=self.config.max_daily_loss,
        )
        if plan is None:
            return Decision(
                event_id=event_id,
                idempotency_key=idempotency_key,
                decided_at=snapshot.captured_at,
                decision=DecisionType.NO_TRADE,
                session=snapshot.session,
                rule_version=self.config.rule_version,
                starting_cash=cash,
                remaining_cash=cash,
                position=None,
                candidates=tuple(final),
                reason_codes=("POSITION_SIZE_ZERO",),
                notes="Available cash and loss limit cannot support one share safely.",
            )

        stop_mode = (
            StopMode.IMMEDIATE
            if "NEWS_INVALIDATION" in selected.quote.warnings
            else StopMode.FIVE_MIN_CONFIRMED
        )
        position = Position(
            position_id=f"POS-{sha256((idempotency_key + selected.quote.code).encode('utf-8')).hexdigest()[:12]}",
            strategy="CLOSING_BET",
            session=snapshot.session,
            code=selected.quote.code,
            name=selected.quote.name,
            entry_at=snapshot.captured_at,
            entry_price=entry,
            quantity=plan.quantity,
            invested_amount=plan.invested_amount,
            stop_mode=stop_mode,
            stop_price=plan.stop_price,
            emergency_stop=plan.emergency_stop,
            target1=plan.target1,
            target2=plan.target2,
        )
        return Decision(
            event_id=event_id,
            idempotency_key=idempotency_key,
            decided_at=snapshot.captured_at,
            decision=DecisionType.BUY,
            session=snapshot.session,
            rule_version=self.config.rule_version,
            starting_cash=cash,
            remaining_cash=plan.remaining_cash,
            position=position,
            candidates=tuple(final),
            reason_codes=("TOP_SCORE_SELECTED", "PAPER_EXECUTION_ONLY"),
            notes=f"Planned risk {plan.risk_amount:,} KRW; no live order was submitted.",
        )

    def _validate_snapshot(self, snapshot: MarketSnapshot) -> None:
        if snapshot.session != self.config.session:
            raise ValueError("snapshot session does not match strategy configuration")
        if snapshot.delayed:
            raise ValueError("delayed market snapshot cannot produce a simulated fill")

    def rank_candidates(self, snapshot: MarketSnapshot) -> tuple[Candidate, ...]:
        """Return fully filtered and theme-diversified candidates without creating a fill."""
        self._validate_snapshot(snapshot)
        return tuple(self._diversify(self._rank(snapshot)))

    def _rank(self, snapshot: MarketSnapshot) -> list[Candidate]:
        results: list[Candidate] = []
        for quote in snapshot.quotes:
            candidate = self._score_quote(snapshot, quote)
            if candidate is not None:
                results.append(candidate)
        return sorted(results, key=lambda item: item.score, reverse=True)

    def _score_quote(self, snapshot: MarketSnapshot, q: Quote) -> Candidate | None:
        cfg = self.config
        age = _age_seconds(snapshot.captured_at, q.observed_at)
        if age < -5 or age > cfg.max_quote_age_seconds:
            return None
        if cfg.excludes_nxt and q.nxt_eligible:
            return None
        if q.price <= 0 or q.price > cfg.hard_max_price:
            return None
        if q.trading_value < cfg.minimum_trading_value:
            return None
        if q.volume_ratio < cfg.minimum_volume_ratio:
            return None
        if q.close_strength < cfg.minimum_close_strength:
            return None
        if q.day_change_pct > cfg.maximum_day_gain_pct or q.day_change_pct < -5.0:
            return None
        if q.price < q.five_min_ma20 or q.five_min_ma20_slope <= 0:
            return None
        if q.support_price <= 0 or q.support_price >= q.price:
            return None
        ma5_distance = ((q.price / q.ma5) - 1) * 100 if q.ma5 > 0 else 999
        if ma5_distance > cfg.maximum_ma5_distance_pct:
            return None

        vwap = q.vwap if q.vwap is not None else q.five_min_ma20
        if q.price < vwap:
            return None
        if q.rsi14 is not None and (q.rsi14 < 38.0 or q.rsi14 > 82.0):
            return None
        if not q.catalyst_verified or not q.catalyst.strip():
            return None

        # Normalized 100-point suitability score.  It is a rule-fit score, not
        # a probability of profit.
        score = min(15.0, max(0.0, (log10(max(q.trading_value, 1)) - 9.0) * 7.5))
        score += q.close_strength * 15.0
        score += min(7.0, max(0.0, (q.volume_ratio - 1.0) * 7.0))
        score += 4.0 if q.price >= q.ma20 else 0.0
        score += 3.0 if q.price >= q.ma5 else 0.0
        score += 8.0  # already verified above a rising 5-minute MA20
        score += 5.0  # already verified above same-session VWAP

        intraday_volume_ratio = q.five_min_volume_ratio or q.volume_ratio
        score += min(8.0, max(0.0, (intraday_volume_ratio - 1.0) * 8.0))
        if q.higher_lows is True:
            score += 4.0
        if q.breakout_holds is True:
            score += 6.0
        last_hour_return = q.last_hour_return_pct
        if last_hour_return is not None and 0.15 <= last_hour_return <= 4.0:
            score += 4.0
        elif last_hour_return is not None and last_hour_return < -0.5:
            score -= 6.0

        if q.rsi14 is not None and 52.0 <= q.rsi14 <= 72.0:
            score += 4.0
        elif q.rsi14 is not None and q.rsi14 > 76.0:
            score -= (q.rsi14 - 76.0) * 1.2

        if q.recent_resistance is not None and q.recent_resistance <= q.price and q.breakout_holds:
            score += 4.0
        elif q.recent_resistance is not None:
            resistance_room = ((q.recent_resistance / q.price) - 1.0) * 100.0
            if resistance_room >= 4.0:
                score += 4.0
            elif resistance_room < 1.2:
                score -= 8.0

        score += 4.0 + min(6.0, max(0.0, q.catalyst_score) * 6.0)
        if q.program_net is not None and q.program_net > 0:
            score += 1.5
        if q.institution_net is not None and q.institution_net > 0:
            score += 1.5
        if q.price > cfg.preferred_max_price:
            score -= 5.0
        if q.day_change_pct > 8.0:
            score -= (q.day_change_pct - 8.0) * 2.0
        if ma5_distance > 5.0:
            score -= (ma5_distance - 5.0) * 2.0
        if q.total_ask_size is not None and q.total_bid_size is not None:
            if q.total_ask_size > q.total_bid_size * 2:
                score -= 10.0

        reasons = [
            "HIGH_TRADING_VALUE",
            "STRONG_CLOSE",
            "VOLUME_EXPANSION",
            "ABOVE_5M_MA20",
            "ABOVE_VWAP",
        ]
        if q.higher_lows:
            reasons.append("FIVE_MIN_HIGHER_LOWS")
        if q.breakout_holds:
            reasons.append("BREAKOUT_HOLD")
        if q.rsi14 is not None and 52.0 <= q.rsi14 <= 72.0:
            reasons.append("RSI_HEALTHY_MOMENTUM")
        if q.catalyst.strip():
            reasons.append("CATALYST_CONFIRMED")
        risks: list[str] = list(q.warnings)
        if q.day_change_pct >= 8.0:
            risks.append("LATE_ENTRY_RISK")
        if q.total_ask_size is None or q.total_bid_size is None:
            risks.append("ORDERBOOK_UNKNOWN")
        if not q.catalyst.strip():
            risks.append("CATALYST_UNKNOWN")
        if q.rsi14 is not None and q.rsi14 > 76.0:
            risks.append("RSI_OVERHEATED")
        score = min(100.0, max(0.0, score))
        return Candidate(q, round(score, 4), tuple(reasons), tuple(dict.fromkeys(risks)))

    @staticmethod
    def _diversify(candidates: list[Candidate]) -> list[Candidate]:
        selected: list[Candidate] = []
        themes: set[str] = set()
        for candidate in candidates:
            theme = candidate.quote.theme.strip().lower() or "unknown"
            if theme in themes:
                continue
            themes.add(theme)
            selected.append(candidate)
        return selected
