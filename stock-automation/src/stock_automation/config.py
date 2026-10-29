from __future__ import annotations

from dataclasses import dataclass

from .models import Session
from .risk import AtrStopPolicy


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    session: Session = Session.KRX_1520
    rule_version: str = "closing-v0.5"
    max_quote_age_seconds: int = 180
    minimum_trading_value: int = 10_000_000_000
    minimum_volume_ratio: float = 1.10
    minimum_close_strength: float = 0.62
    minimum_score: float = 60.0
    preferred_max_price: int = 50_000
    hard_max_price: int = 150_000
    maximum_day_gain_pct: float = 15.0
    maximum_ma5_distance_pct: float = 8.0
    market_weakness_start_pct: float = -1.0
    market_weakness_penalty_per_pct: float = 5.0
    maximum_market_decline_pct: float = -3.0
    max_final_candidates: int = 3
    max_positions: int = 1
    max_allocation_pct: float = 0.40
    max_daily_loss: int = 10_000
    default_stop_mode: str = "5M_CONFIRMED"
    # ATR stops (closing-v0.4). Fixed by the user's work order, not tuned by
    # learning.py; percentages are of the entry price.
    soft_atr_mult: float = 0.5
    hard_atr_mult: float = 0.5
    min_stop_pct: float = 1.5
    max_stop_pct: float = 5.0
    max_hard_stop_pct: float = 7.0
    # Conditional tier (closing-v0.5). Fixed by the user's work order, not
    # tuned by learning.py.
    conditional_score_margin: float = 10.0  # = the most a verified catalyst can add
    conditional_risk_fraction: float = 0.5

    @property
    def atr_stop_policy(self) -> AtrStopPolicy:
        return AtrStopPolicy(
            soft_atr_mult=self.soft_atr_mult,
            hard_atr_mult=self.hard_atr_mult,
            min_stop_pct=self.min_stop_pct,
            max_stop_pct=self.max_stop_pct,
            max_hard_stop_pct=self.max_hard_stop_pct,
        )

    @property
    def excludes_nxt(self) -> bool:
        return self.session == Session.KRX_1520
