from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from math import log10

from .config import StrategyConfig
from .dart import BLOCKING_RISK_FLAGS
from .models import (
    Candidate,
    Decision,
    DecisionType,
    MarketSnapshot,
    Position,
    Quote,
    StopMode,
)
from .risk import ATR_UNAVAILABLE, STOP_TOO_WIDE, atr_stop_rejection, build_position_plan

TIER_FULL = "FULL"
TIER_CONDITIONAL = "CONDITIONAL"
_TIER_ORDER = {TIER_FULL: 0, TIER_CONDITIONAL: 1}


def _age_seconds(newer: datetime, older: datetime) -> float:
    if newer.tzinfo is None or older.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return (newer.astimezone(timezone.utc) - older.astimezone(timezone.utc)).total_seconds()


class ClosingBetEngine:
    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()

    def evaluate(
        self,
        snapshot: MarketSnapshot,
        *,
        cash: int,
        prior_screen_empty: bool = False,
    ) -> Decision:
        self._validate_snapshot(snapshot)
        final = list(self.rank_candidates(snapshot))[: self.config.max_final_candidates]
        idempotency_key = (
            f"{snapshot.captured_at.date()}:{snapshot.session.value}:CLOSING_BET"
        )
        stable_suffix = sha256(idempotency_key.encode("utf-8")).hexdigest()[:10]
        event_id = f"SIM-{snapshot.captured_at:%Y%m%d}-{snapshot.session.value}-{stable_suffix}"

        # Ranking puts FULL first, then CONDITIONAL, then untiered candidates.
        if not final or not final[0].tier:
            no_quotes = not snapshot.quotes
            reason = (
                "NO_QUALIFYING_CANDIDATE"
                if not no_quotes or prior_screen_empty
                else "MARKET_DATA_UNAVAILABLE"
            )
            if no_quotes and prior_screen_empty:
                notes = "앞선 후보 선별은 완료됐지만 통과한 종목이 없어 모의매수를 진행하지 않았습니다."
            elif no_quotes:
                notes = "검증 가능한 시세 자료가 없어 모의매수를 진행하지 않았습니다."
            else:
                notes = "수신 시세가 필수 선별·위험 기준을 통과하지 못해 모의매수를 진행하지 않았습니다."
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
                notes=notes,
            )

        selected = final[0]
        conditional = selected.tier == TIER_CONDITIONAL
        fraction = self.config.conditional_risk_fraction if conditional else 1.0
        max_loss = int(self.config.max_daily_loss * fraction)
        max_allocation_pct = self.config.max_allocation_pct * fraction
        entry = selected.quote.best_ask or selected.quote.price
        policy = self.config.atr_stop_policy
        stop_rejection = atr_stop_rejection(
            entry_price=entry,
            support_price=selected.quote.support_price,
            atr14=selected.quote.atr14,
            policy=policy,
        )
        if stop_rejection is not None:
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
                reason_codes=(stop_rejection,),
                notes="The ATR stop for the top candidate is wider than the allowed limit.",
            )
        plan = build_position_plan(
            cash=cash,
            entry_price=entry,
            support_price=selected.quote.support_price,
            max_allocation_pct=max_allocation_pct,
            max_loss=max_loss,
            atr14=selected.quote.atr14,
            atr_policy=policy,
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
            reason_codes=(
                "TOP_SCORE_SELECTED",
                f"TIER_{selected.tier}",
                "PAPER_EXECUTION_ONLY",
            ),
            notes=(
                f"Tier {selected.tier}"
                + (f" ({', '.join(selected.tier_reasons)})" if selected.tier_reasons else "")
                + f"; max loss {max_loss:,} KRW, allocation {max_allocation_pct:.0%}; "
                f"planned risk {plan.risk_amount:,} KRW; no live order was submitted."
            ),
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
        return sorted(
            results,
            key=lambda item: (_TIER_ORDER.get(item.tier, len(_TIER_ORDER)), -item.score),
        )

    def rejection_reason(self, snapshot: MarketSnapshot, q: Quote) -> str | None:
        """Return the first hard filter that rejects ``q``, or None when it passes.

        The check order is the scoring gate order, so the code names the first
        condition a stock failed rather than every condition it failed.
        """
        cfg = self.config
        age = _age_seconds(snapshot.captured_at, q.observed_at)
        if age < -5 or age > cfg.max_quote_age_seconds:
            return "STALE_QUOTE"
        if cfg.excludes_nxt and q.nxt_eligible:
            return "NXT_ELIGIBLE_EXCLUDED"
        if q.price <= 0 or q.price > cfg.hard_max_price:
            return "PRICE_OUT_OF_RANGE"
        if q.trading_value < cfg.minimum_trading_value:
            return "LOW_TRADING_VALUE"
        if q.volume_ratio < cfg.minimum_volume_ratio:
            return "LOW_VOLUME_RATIO"
        if q.close_strength < cfg.minimum_close_strength:
            return "WEAK_CLOSE_STRENGTH"
        if q.day_change_pct > cfg.maximum_day_gain_pct or q.day_change_pct < -5.0:
            return "DAY_CHANGE_OUT_OF_RANGE"
        if q.price < q.five_min_ma20 or q.five_min_ma20_slope <= 0:
            return "BELOW_5M_MA20_OR_FALLING"
        if q.support_price <= 0 or q.support_price >= q.price:
            return "INVALID_SUPPORT"
        ma5_distance = ((q.price / q.ma5) - 1) * 100 if q.ma5 > 0 else 999
        if ma5_distance > cfg.maximum_ma5_distance_pct:
            return "EXTENDED_FROM_MA5"
        vwap = q.vwap if q.vwap is not None else q.five_min_ma20
        if q.price < vwap:
            return "BELOW_VWAP"
        if q.rsi14 is not None and (q.rsi14 < 38.0 or q.rsi14 > 82.0):
            return "RSI_OUT_OF_RANGE"
        # A verified catalyst is scored, not required; see _score_quote.
        # A same-day risk disclosure (OpenDART) is never scored away: it blocks.
        if any(w.startswith("DART_") and w[5:] in BLOCKING_RISK_FLAGS for w in q.warnings):
            return "DART_RISK_DISCLOSURE"
        # 15:20 marks a quote whose same-day DART check is missing; unknown risk blocks.
        if "DART_NOT_CHECKED" in q.warnings:
            return "DART_NOT_CHECKED"
        # closing-v0.4 sizes stops from the daily ATR; without it there is no plan.
        if q.atr14 is None or not q.atr14 > 0:
            return ATR_UNAVAILABLE
        # Drop a too-wide stop before ranking so the next candidate can be chosen.
        if atr_stop_rejection(
            entry_price=q.best_ask or q.price,
            support_price=q.support_price,
            atr14=q.atr14,
            policy=cfg.atr_stop_policy,
        ) is not None:
            return STOP_TOO_WIDE
        if self._market_change(snapshot, q) <= cfg.maximum_market_decline_pct:
            return "MARKET_DECLINE_GATE"
        return None

    def rejection_reasons(self, snapshot: MarketSnapshot) -> dict[str, str]:
        """Map each rejected stock code to its first failed hard filter."""
        self._validate_snapshot(snapshot)
        reasons: dict[str, str] = {}
        for quote in snapshot.quotes:
            reason = self.rejection_reason(snapshot, quote)
            if reason is not None:
                reasons[quote.code] = reason
        return reasons

    def _score_quote(self, snapshot: MarketSnapshot, q: Quote) -> Candidate | None:
        cfg = self.config
        if self.rejection_reason(snapshot, q) is not None:
            return None
        ma5_distance = ((q.price / q.ma5) - 1) * 100 if q.ma5 > 0 else 999
        market_change = self._market_change(snapshot, q)

        # Normalized 100-point suitability score.  It is a rule-fit score, not
        # a probability of profit.
        risks: list[str] = list(q.warnings)
        score = min(15.0, max(0.0, (log10(max(q.trading_value, 1)) - 9.0) * 7.5))
        score += q.close_strength * 15.0
        score += min(7.0, max(0.0, (q.volume_ratio - 1.0) * 7.0))
        score += 4.0 if q.price >= q.ma20 else 0.0
        score += 3.0 if q.price >= q.ma5 else 0.0
        score += 8.0  # already verified above a rising 5-minute MA20
        # Without a VWAP the hard filter checked the 5-minute MA20 instead.
        if q.vwap is not None:
            score += 5.0
        else:
            risks.append("VWAP_UNKNOWN")

        # The daily volume ratio is scored above; never count it twice.
        if q.five_min_volume_ratio is not None:
            score += min(8.0, max(0.0, (q.five_min_volume_ratio - 1.0) * 8.0))
        else:
            risks.append("INTRADAY_VOLUME_UNKNOWN")
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

        catalyst_confirmed = q.catalyst_verified and bool(q.catalyst.strip())
        # Unverified theme strength (e.g. Kiwoom ka90001) is context, not points.
        if catalyst_confirmed:
            score += min(6.0, max(0.0, q.catalyst_score) * 6.0)
            score += 4.0
        if q.program_net is not None and q.program_net > 0:
            score += 1.5
        if q.institution_net is not None and q.institution_net > 0:
            score += 1.5
        if market_change < cfg.market_weakness_start_pct:
            market_penalty = min(
                10.0,
                (cfg.market_weakness_start_pct - market_change)
                * cfg.market_weakness_penalty_per_pct,
            )
            score -= market_penalty
            risks.append("MARKET_WEAKNESS")
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
        ]
        if q.vwap is not None:
            reasons.append("ABOVE_VWAP")
        if q.higher_lows:
            reasons.append("FIVE_MIN_HIGHER_LOWS")
        if q.breakout_holds:
            reasons.append("BREAKOUT_HOLD")
        if q.rsi14 is not None and 52.0 <= q.rsi14 <= 72.0:
            reasons.append("RSI_HEALTHY_MOMENTUM")
        if catalyst_confirmed:
            reasons.append("CATALYST_CONFIRMED")
        if q.day_change_pct >= 8.0:
            risks.append("LATE_ENTRY_RISK")
        if q.total_ask_size is None or q.total_bid_size is None:
            risks.append("ORDERBOOK_UNKNOWN")
        if not catalyst_confirmed:
            risks.append("CATALYST_UNKNOWN")
        if q.rsi14 is not None and q.rsi14 > 76.0:
            risks.append("RSI_OVERHEATED")
        score = round(min(100.0, max(0.0, score)), 4)
        tier, tier_reasons = self._tier(score, catalyst_confirmed, market_change)
        return Candidate(
            q,
            score,
            tuple(reasons),
            tuple(dict.fromkeys(risks)),
            tier=tier,
            tier_reasons=tier_reasons,
        )

    def _tier(
        self, score: float, catalyst_confirmed: bool, market_change: float
    ) -> tuple[str, tuple[str, ...]]:
        """closing-v0.5 tier: FULL needs all three conditions; CONDITIONAL is half size."""
        cfg = self.config
        missed: list[str] = []
        if not catalyst_confirmed:
            missed.append("CATALYST_UNKNOWN")
        if market_change <= cfg.market_weakness_start_pct:
            missed.append("MARKET_WEAKNESS")
        if score < cfg.minimum_score:
            missed.append("SCORE_BELOW_MINIMUM")
        if not missed:
            return TIER_FULL, ()
        if score >= cfg.minimum_score - cfg.conditional_score_margin:
            return TIER_CONDITIONAL, tuple(missed)
        return "", ()

    @staticmethod
    def _market_change(snapshot: MarketSnapshot, quote: Quote) -> float:
        market = quote.market.strip().upper()
        if market in {"KOSPI", "KS", "0", "001", "P00101"}:
            return snapshot.kospi_change_pct
        if market in {"KOSDAQ", "KQ", "10", "101", "P10102"}:
            return snapshot.kosdaq_change_pct
        # Legacy/manual snapshots may not have a market field.  Use the weaker
        # index so missing classification cannot bypass the risk-off gate.
        return min(snapshot.kospi_change_pct, snapshot.kosdaq_change_pct)

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
