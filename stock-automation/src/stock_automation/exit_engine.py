from __future__ import annotations

from datetime import datetime

from .models import ExitAction, ExitDecision, ExitObservation, Position, StopMode


def review_position(
    position: Position,
    observation: ExitObservation,
    *,
    scheduled_exit_at: datetime,
    remaining_quantity: int | None = None,
) -> ExitDecision:
    """Review one open paper position without assuming fills between observations."""
    quantity = position.quantity if remaining_quantity is None else remaining_quantity
    if quantity <= 0:
        raise ValueError("remaining quantity must be positive")
    if observation.observed_at.tzinfo is None or scheduled_exit_at.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    if observation.price <= 0:
        raise ValueError("observation price must be positive")

    hard_stop = (
        observation.price <= position.emergency_stop
        or observation.market_shock
        or observation.catalyst_invalidated
    )
    immediate_stop = position.stop_mode == StopMode.IMMEDIATE and observation.price <= position.stop_price
    confirmed_stop = (
        position.stop_mode == StopMode.FIVE_MIN_CONFIRMED
        and observation.five_min_closed_below_stop
        and observation.following_candle_reclaimed_stop is False
    )
    if hard_stop or immediate_stop or confirmed_stop:
        reasons = ["STOP_LOSS"]
        if hard_stop:
            reasons.append("EMERGENCY_INVALIDATION")
        elif confirmed_stop:
            reasons.append("FIVE_MIN_CONFIRMATION")
        return _exit(position, observation, quantity, ExitAction.STOP_LOSS, tuple(reasons))

    # The product contract is to liquidate every remaining share at the first
    # verified quote at or after 09:10.  Scheduled liquidation therefore takes
    # precedence over profit-target classification at that timestamp.
    if observation.observed_at >= scheduled_exit_at:
        return _exit(
            position,
            observation,
            quantity,
            ExitAction.SCHEDULED_EXIT,
            ("NEXT_SESSION_0910",),
        )

    if observation.price >= position.target2:
        return _exit(position, observation, quantity, ExitAction.FULL_PROFIT, ("TARGET2_REACHED",))

    # A reduced remaining quantity proves that target 1 was already processed.
    # Do not repeatedly halve the position on subsequent observations.
    if observation.price >= position.target1 and quantity == position.quantity and quantity >= 2:
        sell_quantity = max(1, quantity // 2)
        pnl = (observation.price - position.entry_price) * sell_quantity
        return ExitDecision(
            action=ExitAction.PARTIAL_PROFIT,
            decided_at=observation.observed_at,
            execution_price=observation.price,
            execution_quantity=sell_quantity,
            remaining_quantity=quantity - sell_quantity,
            realized_pnl=pnl,
            reason_codes=("TARGET1_REACHED",),
        )

    return ExitDecision(
        action=ExitAction.HOLD,
        decided_at=observation.observed_at,
        execution_price=None,
        execution_quantity=0,
        remaining_quantity=quantity,
        realized_pnl=0,
        reason_codes=("NO_EXIT_TRIGGER",),
    )


def _exit(
    position: Position,
    observation: ExitObservation,
    quantity: int,
    action: ExitAction,
    reasons: tuple[str, ...],
) -> ExitDecision:
    return ExitDecision(
        action=action,
        decided_at=observation.observed_at,
        execution_price=observation.price,
        execution_quantity=quantity,
        remaining_quantity=0,
        realized_pnl=(observation.price - position.entry_price) * quantity,
        reason_codes=reasons,
    )
