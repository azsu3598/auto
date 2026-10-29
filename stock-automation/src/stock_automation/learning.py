from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from itertools import product
from math import inf
from pathlib import Path
import json

from .backtest import BacktestSummary, ReplayCase, TradingCosts, run_backtest
from .config import StrategyConfig


@dataclass(frozen=True, slots=True)
class TunableParameters:
    minimum_score: float
    minimum_close_strength: float
    minimum_volume_ratio: float
    maximum_day_gain_pct: float
    maximum_ma5_distance_pct: float


@dataclass(frozen=True, slots=True)
class TuningPolicy:
    minimum_cases: int = 40
    validation_fraction: float = 0.30
    minimum_validation_trades: int = 5
    minimum_validation_score_improvement: float = 0.30
    maximum_drawdown_increase_pct: float = 0.50


@dataclass(frozen=True, slots=True)
class TuningResult:
    status: str
    promoted: bool
    reason: str
    base_parameters: TunableParameters
    challenger_parameters: TunableParameters | None
    training_cases: int
    validation_cases: int
    baseline_training_score: float | None
    challenger_training_score: float | None
    baseline_validation_score: float | None
    challenger_validation_score: float | None
    baseline_validation: BacktestSummary | None
    challenger_validation: BacktestSummary | None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.baseline_validation is not None:
            data["baseline_validation"] = self.baseline_validation.to_dict()
        if self.challenger_validation is not None:
            data["challenger_validation"] = self.challenger_validation.to_dict()
        return data


def tune_strategy(
    cases: tuple[ReplayCase, ...],
    *,
    starting_cash: int,
    costs: TradingCosts,
    base_config: StrategyConfig | None = None,
    policy: TuningPolicy | None = None,
    variants: tuple[TunableParameters, ...] | None = None,
) -> TuningResult:
    policy = policy or TuningPolicy()
    if not cases:
        base = base_config or StrategyConfig()
        return _insufficient(base, 0, 0, "학습 사례가 없음")
    ordered = tuple(sorted(cases, key=lambda case: case.snapshot.captured_at))
    sessions = {case.snapshot.session for case in ordered}
    if len(sessions) != 1:
        raise ValueError("strategy sessions must be tuned separately")
    base = base_config or StrategyConfig(session=ordered[0].snapshot.session)
    if base.session not in sessions:
        raise ValueError("base strategy session does not match replay cases")
    if len(ordered) < policy.minimum_cases:
        validation_count = max(1, int(len(ordered) * policy.validation_fraction))
        return _insufficient(
            base,
            len(ordered) - validation_count,
            validation_count,
            f"최소 {policy.minimum_cases}건 필요, 현재 {len(ordered)}건",
        )

    validation_count = max(1, int(len(ordered) * policy.validation_fraction))
    training = ordered[:-validation_count]
    validation = ordered[-validation_count:]
    baseline_training = run_backtest(training, starting_cash=starting_cash, costs=costs, config=base)
    baseline_training_score = objective_score(baseline_training, minimum_trades=1)

    candidates = variants or default_variants(base)
    best_params: TunableParameters | None = None
    best_training: BacktestSummary | None = None
    best_score = -inf
    for params in candidates:
        candidate_config = apply_parameters(base, params)
        summary = run_backtest(
            training,
            starting_cash=starting_cash,
            costs=costs,
            config=candidate_config,
        )
        score = objective_score(summary, minimum_trades=1)
        if score > best_score:
            best_score = score
            best_params = params
            best_training = summary

    if best_params is None or best_training is None:
        return _insufficient(base, len(training), len(validation), "평가 가능한 후보 규칙이 없음")

    baseline_validation = run_backtest(
        validation, starting_cash=starting_cash, costs=costs, config=base
    )
    challenger_config = apply_parameters(base, best_params)
    challenger_validation = run_backtest(
        validation, starting_cash=starting_cash, costs=costs, config=challenger_config
    )
    baseline_validation_score = objective_score(
        baseline_validation, minimum_trades=policy.minimum_validation_trades
    )
    challenger_validation_score = objective_score(
        challenger_validation, minimum_trades=policy.minimum_validation_trades
    )

    reasons = []
    if best_score <= baseline_training_score:
        reasons.append("TRAINING_NOT_BETTER")
    if challenger_validation.trades < policy.minimum_validation_trades:
        reasons.append("VALIDATION_TRADES_INSUFFICIENT")
    if challenger_validation_score < (
        baseline_validation_score + policy.minimum_validation_score_improvement
    ):
        reasons.append("VALIDATION_IMPROVEMENT_INSUFFICIENT")
    if challenger_validation.maximum_drawdown_pct > (
        baseline_validation.maximum_drawdown_pct + policy.maximum_drawdown_increase_pct
    ):
        reasons.append("DRAWDOWN_WORSE")
    if challenger_validation.net_pnl <= 0:
        reasons.append("VALIDATION_NET_PNL_NOT_POSITIVE")

    promoted = not reasons
    return TuningResult(
        status="PROMOTED_PAPER" if promoted else "REJECTED",
        promoted=promoted,
        reason="|".join(reasons) if reasons else "WALK_FORWARD_GATES_PASSED",
        base_parameters=parameters_from_config(base),
        challenger_parameters=best_params,
        training_cases=len(training),
        validation_cases=len(validation),
        baseline_training_score=baseline_training_score,
        challenger_training_score=best_score,
        baseline_validation_score=baseline_validation_score,
        challenger_validation_score=challenger_validation_score,
        baseline_validation=baseline_validation,
        challenger_validation=challenger_validation,
    )


def objective_score(summary: BacktestSummary, *, minimum_trades: int) -> float:
    if summary.trades < minimum_trades:
        return -1_000_000.0
    capital_return = summary.net_pnl / summary.starting_cash * 100.0
    return (
        capital_return
        - summary.maximum_drawdown_pct * 1.5
        + summary.win_rate_pct * 0.02
        + summary.average_return_pct * 0.25
    )


def default_variants(base: StrategyConfig) -> tuple[TunableParameters, ...]:
    score_values = _neighbors(base.minimum_score, (5.0, 0.0, -5.0), 50.0, 75.0)
    close_values = _neighbors(base.minimum_close_strength, (0.06, 0.0, -0.04), 0.55, 0.82)
    volume_values = _neighbors(base.minimum_volume_ratio, (0.20, 0.0, -0.10), 1.0, 1.8)
    gain_values = _neighbors(base.maximum_day_gain_pct, (-3.0, 0.0, 2.0), 8.0, 17.0)
    distance_values = _neighbors(base.maximum_ma5_distance_pct, (-2.0, 0.0, 1.0), 4.0, 9.0)
    return tuple(
        TunableParameters(*values)
        for values in product(score_values, close_values, volume_values, gain_values, distance_values)
    )


def apply_parameters(base: StrategyConfig, params: TunableParameters) -> StrategyConfig:
    return replace(
        base,
        minimum_score=params.minimum_score,
        minimum_close_strength=params.minimum_close_strength,
        minimum_volume_ratio=params.minimum_volume_ratio,
        maximum_day_gain_pct=params.maximum_day_gain_pct,
        maximum_ma5_distance_pct=params.maximum_ma5_distance_pct,
        rule_version=f"{base.rule_version}-challenger",
    )


def code_rule_version(session) -> str:
    """The rule version of the engine logic itself, ignoring any champion name."""
    return StrategyConfig(session=session).rule_version


def champion_matches_code(base: StrategyConfig, payload: dict) -> bool:
    """True when ``payload`` was tuned against the current engine logic.

    A champion from older logic (no ``base_rule_version``, or another one)
    must not run under the new logic with its old name.
    """
    return payload.get("base_rule_version") == code_rule_version(base.session)


def config_from_champion(base: StrategyConfig, payload: dict) -> StrategyConfig:
    if payload.get("mode") != "PAPER_ONLY":
        raise ValueError("learned rules may only be activated in paper mode")
    if payload.get("session") != base.session.value:
        raise ValueError("learned rule session mismatch")
    if not champion_matches_code(base, payload):
        raise ValueError("learned rule base version does not match the engine")
    raw = payload.get("parameters")
    if not isinstance(raw, dict):
        raise ValueError("learned rule parameters are missing")
    params = TunableParameters(
        minimum_score=float(raw["minimum_score"]),
        minimum_close_strength=float(raw["minimum_close_strength"]),
        minimum_volume_ratio=float(raw["minimum_volume_ratio"]),
        maximum_day_gain_pct=float(raw["maximum_day_gain_pct"]),
        maximum_ma5_distance_pct=float(raw["maximum_ma5_distance_pct"]),
    )
    bounds = (
        50.0 <= params.minimum_score <= 75.0,
        0.55 <= params.minimum_close_strength <= 0.82,
        1.0 <= params.minimum_volume_ratio <= 1.8,
        8.0 <= params.maximum_day_gain_pct <= 17.0,
        4.0 <= params.maximum_ma5_distance_pct <= 9.0,
    )
    if not all(bounds):
        raise ValueError("learned rule parameter is outside the safety envelope")
    version = str(payload.get("rule_version", "")).strip()
    if not version or len(version) > 80:
        raise ValueError("learned rule version is invalid")
    return replace(apply_parameters(base, params), rule_version=version)


def parameters_from_config(config: StrategyConfig) -> TunableParameters:
    return TunableParameters(
        minimum_score=config.minimum_score,
        minimum_close_strength=config.minimum_close_strength,
        minimum_volume_ratio=config.minimum_volume_ratio,
        maximum_day_gain_pct=config.maximum_day_gain_pct,
        maximum_ma5_distance_pct=config.maximum_ma5_distance_pct,
    )


def write_tuning_result(path: str | Path, result: TuningResult) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_paper_champion(
    path: str | Path,
    result: TuningResult,
    base: StrategyConfig,
    *,
    new_rule_version: str | None = None,
) -> None:
    if not result.promoted or result.challenger_parameters is None:
        raise ValueError("only a promoted challenger can become the paper champion")
    config = apply_parameters(base, result.challenger_parameters)
    if new_rule_version:
        config = replace(config, rule_version=new_rule_version)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "PAPER_ONLY",
        "rule_version": config.rule_version,
        "base_rule_version": code_rule_version(config.session),
        "session": config.session.value,
        "parameters": asdict(result.challenger_parameters),
        "evidence": {
            "training_cases": result.training_cases,
            "validation_cases": result.validation_cases,
            "baseline_validation_score": result.baseline_validation_score,
            "challenger_validation_score": result.challenger_validation_score,
            "reason": result.reason,
        },
    }
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _neighbors(value: float, offsets: tuple[float, ...], minimum: float, maximum: float) -> tuple[float, ...]:
    return tuple(sorted({round(min(maximum, max(minimum, value + offset)), 4) for offset in offsets}))


def _insufficient(base: StrategyConfig, training: int, validation: int, reason: str) -> TuningResult:
    return TuningResult(
        status="INSUFFICIENT_DATA",
        promoted=False,
        reason=reason,
        base_parameters=parameters_from_config(base),
        challenger_parameters=None,
        training_cases=training,
        validation_cases=validation,
        baseline_training_score=None,
        challenger_training_score=None,
        baseline_validation_score=None,
        challenger_validation_score=None,
        baseline_validation=None,
        challenger_validation=None,
    )
