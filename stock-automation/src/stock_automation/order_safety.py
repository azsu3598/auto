from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class AuthorizationStatus(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class OrderIntent:
    intent_id: str
    event_id: str
    strategy: str
    side: OrderSide
    code: str
    name: str
    quantity: int
    limit_price: int
    reference_price: int
    reference_at: datetime
    created_at: datetime
    expires_at: datetime
    account_alias: str

    @property
    def order_amount(self) -> int:
        return self.limit_price * self.quantity

    def to_dict(self) -> dict:
        data = asdict(self)
        data["side"] = self.side.value
        for key in ("reference_at", "created_at", "expires_at"):
            data[key] = data[key].isoformat()
        return data


@dataclass(frozen=True, slots=True)
class UserApproval:
    intent_id: str
    challenge: str
    approved_at: datetime
    approved_by: str


@dataclass(frozen=True, slots=True)
class LiveOrderPolicy:
    live_order_enabled: bool = False
    maximum_order_amount: int = 300_000
    maximum_total_exposure: int = 600_000
    maximum_daily_loss: int = 10_000
    maximum_open_positions: int = 2
    maximum_quote_age_seconds: int = 60
    maximum_buy_slippage_pct: float = 0.5
    approval_ttl_seconds: int = 300
    maximum_daily_buy_orders_per_code: int = 1
    allowed_strategies: tuple[str, ...] = ("CLOSING_BET", "MEDIUM_TERM")
    expected_account_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class AccountRiskState:
    account_alias: str
    available_cash: int
    current_exposure: int
    realized_daily_pnl: int
    open_positions: int
    owned_quantity: int
    kill_switch_active: bool
    already_submitted_intent_ids: frozenset[str] = frozenset()
    observed_account_fingerprint: str | None = None
    protected_baseline_quantity: int = 0
    program_owned_quantity: int = 0
    holdings_reconciled: bool = False
    total_owned_quantity: int = 0
    # Submitted (not broker-rejected) buy orders for this code today.
    same_code_buy_orders_today: int = 0
    # Orders in SUBMITTING, CANCEL_SUBMITTING or UNCERTAIN need manual reconciliation.
    ambiguous_orders: int = 0

    @property
    def program_sellable_quantity(self) -> int:
        """Quantity that can be sold without touching the protected baseline."""
        quantity_above_baseline = max(0, self.owned_quantity - self.protected_baseline_quantity)
        return min(self.program_owned_quantity, quantity_above_baseline)


@dataclass(frozen=True, slots=True)
class OrderAuthorization:
    status: AuthorizationStatus
    checked_at: datetime
    intent_id: str
    reason_codes: tuple[str, ...]
    intent_challenge: str = ""

    @property
    def authorized(self) -> bool:
        return self.status == AuthorizationStatus.AUTHORIZED


def build_order_intent(
    *,
    event_id: str,
    strategy: str,
    side: OrderSide,
    code: str,
    name: str,
    quantity: int,
    limit_price: int,
    reference_price: int,
    reference_at: datetime,
    created_at: datetime,
    account_alias: str,
    ttl_seconds: int = 300,
) -> OrderIntent:
    if reference_at.tzinfo is None or created_at.tzinfo is None:
        raise ValueError("order timestamps must be timezone-aware")
    if min(quantity, limit_price, reference_price, ttl_seconds) <= 0:
        raise ValueError("order quantity, prices and TTL must be positive")
    identity = "|".join(
        (event_id, strategy, side.value, code, str(quantity), str(limit_price), account_alias)
    )
    return OrderIntent(
        intent_id=f"ORD-{sha256(identity.encode()).hexdigest()[:16]}",
        event_id=event_id,
        strategy=strategy,
        side=side,
        code=code,
        name=name,
        quantity=quantity,
        limit_price=limit_price,
        reference_price=reference_price,
        reference_at=reference_at,
        created_at=created_at,
        expires_at=created_at + timedelta(seconds=ttl_seconds),
        account_alias=account_alias,
    )


def approval_challenge(intent: OrderIntent) -> str:
    canonical = json.dumps(intent.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode()).hexdigest()


def authorize_live_order(
    intent: OrderIntent,
    *,
    approval: UserApproval | None,
    state: AccountRiskState,
    policy: LiveOrderPolicy,
    checked_at: datetime,
) -> OrderAuthorization:
    if checked_at.tzinfo is None:
        raise ValueError("authorization timestamp must be timezone-aware")
    reasons: list[str] = []
    if not policy.live_order_enabled:
        reasons.append("LIVE_ORDER_DISABLED")
    if state.kill_switch_active:
        reasons.append("KILL_SWITCH_ACTIVE")
    if state.account_alias != intent.account_alias:
        reasons.append("ACCOUNT_ALIAS_MISMATCH")
    expected_fingerprint = (policy.expected_account_fingerprint or "").strip()
    observed_fingerprint = (state.observed_account_fingerprint or "").strip()
    if not expected_fingerprint:
        reasons.append("ACCOUNT_FINGERPRINT_NOT_CONFIGURED")
    elif not observed_fingerprint or observed_fingerprint != expected_fingerprint:
        reasons.append("ACCOUNT_FINGERPRINT_MISMATCH")
    if not state.holdings_reconciled:
        reasons.append("HOLDINGS_NOT_RECONCILED")
    if state.ambiguous_orders > 0:
        reasons.append("AMBIGUOUS_ORDER_STATE")
    if intent.strategy not in policy.allowed_strategies:
        reasons.append("STRATEGY_NOT_ALLOWED")
    if intent.intent_id in state.already_submitted_intent_ids:
        reasons.append("DUPLICATE_ORDER_INTENT")
    if checked_at < intent.created_at or checked_at > intent.expires_at:
        reasons.append("ORDER_INTENT_EXPIRED")
    quote_age = (
        checked_at.astimezone(timezone.utc)
        - intent.reference_at.astimezone(timezone.utc)
    ).total_seconds()
    if quote_age < -5 or quote_age > policy.maximum_quote_age_seconds:
        reasons.append("REFERENCE_QUOTE_STALE")
    if intent.order_amount > policy.maximum_order_amount:
        reasons.append("ORDER_AMOUNT_LIMIT")
    if state.realized_daily_pnl <= -policy.maximum_daily_loss:
        reasons.append("DAILY_LOSS_LIMIT")

    if intent.side == OrderSide.BUY:
        slippage = (intent.limit_price / intent.reference_price - 1.0) * 100.0
        if slippage > policy.maximum_buy_slippage_pct:
            reasons.append("BUY_SLIPPAGE_LIMIT")
        if intent.order_amount > state.available_cash:
            reasons.append("INSUFFICIENT_CASH")
        if state.current_exposure + intent.order_amount > policy.maximum_total_exposure:
            reasons.append("TOTAL_EXPOSURE_LIMIT")
        if state.open_positions >= policy.maximum_open_positions:
            reasons.append("OPEN_POSITION_LIMIT")
        if state.same_code_buy_orders_today >= policy.maximum_daily_buy_orders_per_code:
            reasons.append("DAILY_CODE_ORDER_LIMIT")
    elif intent.quantity > state.program_sellable_quantity:
        reasons.append("SELL_QUANTITY_EXCEEDS_PROGRAM_HOLDING")

    if approval is None:
        reasons.append("USER_APPROVAL_REQUIRED")
    else:
        if approval.intent_id != intent.intent_id:
            reasons.append("APPROVAL_INTENT_MISMATCH")
        if approval.challenge != approval_challenge(intent):
            reasons.append("APPROVAL_CHALLENGE_MISMATCH")
        if approval.approved_at.tzinfo is None:
            reasons.append("APPROVAL_TIMESTAMP_INVALID")
        else:
            approval_age = (
                checked_at.astimezone(timezone.utc)
                - approval.approved_at.astimezone(timezone.utc)
            ).total_seconds()
            if approval_age < 0 or approval_age > policy.approval_ttl_seconds:
                reasons.append("APPROVAL_EXPIRED")
        if approval.approved_by.strip().upper() != "USER":
            reasons.append("APPROVAL_ACTOR_INVALID")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return OrderAuthorization(
        status=(
            AuthorizationStatus.AUTHORIZED
            if not unique_reasons
            else AuthorizationStatus.REJECTED
        ),
        checked_at=checked_at,
        intent_id=intent.intent_id,
        reason_codes=unique_reasons or ("ALL_LIVE_ORDER_GATES_PASSED",),
        intent_challenge=approval_challenge(intent),
    )
