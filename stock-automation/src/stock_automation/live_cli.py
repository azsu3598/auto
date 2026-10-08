from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from .live_broker import KiwoomLiveBroker
from .live_execution import DynamoLiveOrderStore, LiveOrderExecutor, LiveOrderState
from .order_safety import (
    LiveOrderPolicy,
    OrderSide,
    UserApproval,
    approval_challenge,
    authorize_live_order,
    build_order_intent,
)
from .providers.reliable import KiwoomRetryPolicy, ReliableKiwoomClient

KST = timezone(timedelta(hours=9))


def prepare(args) -> int:
    now = datetime.now(KST)
    account_alias = _approved_account_alias(args.account_alias)
    raw, read = _real_clients()
    del raw
    observed_at, reference_price = _current_quote(read, args.code, now)
    event_id = args.event_id or f"LIVE-{now:%Y%m%d%H%M%S}-{args.code}"
    intent = build_order_intent(
        event_id=event_id,
        strategy=args.strategy,
        side=OrderSide(args.side),
        code=args.code,
        name=args.name,
        quantity=args.quantity,
        limit_price=args.limit_price,
        reference_price=reference_price,
        reference_at=observed_at,
        created_at=now,
        account_alias=account_alias,
        ttl_seconds=_policy().approval_ttl_seconds,
    )
    store = _store(args.table)
    inserted = store.create_pending(intent, created_at=now)
    result = {
        "status": "PENDING_APPROVAL" if inserted else "DUPLICATE_INTENT",
        "intent": intent.to_dict(),
        "approval_challenge": approval_challenge(intent),
        "warning": "REAL ORDER: approval and execution must occur before expires_at",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if inserted else 2


def approve(args) -> int:
    now = datetime.now(KST)
    store = _store(args.table)
    stored = store.load(args.intent_id)
    if stored is None:
        raise RuntimeError("live order intent was not found")
    if stored.state != LiveOrderState.PENDING_APPROVAL:
        raise RuntimeError(f"order is not pending approval: {stored.state.value}")
    if now > stored.intent.expires_at:
        raise RuntimeError("order intent expired; prepare a new order")
    expected = approval_challenge(stored.intent)
    if args.challenge != expected:
        raise RuntimeError("approval challenge does not match the exact order")
    approval = UserApproval(
        intent_id=stored.intent.intent_id,
        challenge=args.challenge,
        approved_at=now,
        approved_by="USER",
    )
    if not store.approve(stored.intent, approval, updated_at=now):
        raise RuntimeError("approval state changed concurrently; no order was submitted")
    print(json.dumps({
        "status": "READY",
        "intent_id": stored.intent.intent_id,
        "expires_at": stored.intent.expires_at.isoformat(),
    }, ensure_ascii=False))
    return 0


def execute(args) -> int:
    now = datetime.now(KST)
    if os.getenv("LIVE_ORDER_ENABLED", "") != "1":
        raise RuntimeError("LIVE_ORDER_ENABLED must be exactly 1")
    store = _store(args.table)
    stored = store.load(args.intent_id)
    if stored is None or stored.state != LiveOrderState.READY or stored.approval is None:
        raise RuntimeError("order is not in READY state with exact user approval")
    account_alias = _approved_account_alias(stored.intent.account_alias)
    if store.kill_switch_active(account_alias=account_alias):
        raise RuntimeError("live kill switch is active")

    raw, read = _real_clients()
    observed_at, current_price = _current_quote(read, stored.intent.code, now)
    if abs((now - observed_at).total_seconds()) > _policy().maximum_quote_age_seconds:
        raise RuntimeError("current quote is stale")
    # The exact approved limit cannot be changed. This current quote check only
    # confirms the market has not moved beyond the approved buy-slippage envelope.
    if stored.intent.side == OrderSide.BUY:
        current_slippage = (
            current_price / stored.intent.reference_price - 1.0
        ) * 100.0
        if current_slippage > _policy().maximum_buy_slippage_pct:
            raise RuntimeError("market moved beyond approved buy-slippage limit")

    read_broker = KiwoomLiveBroker(read, account_alias=account_alias)
    risk_state = read_broker.account_risk_state(
        code=stored.intent.code,
        trading_date=now.strftime("%Y%m%d"),
        kill_switch_active=False,
        already_submitted_intent_ids=store.submitted_intent_ids(),
        exchange=args.exchange,
    )
    authorization = authorize_live_order(
        stored.intent,
        approval=stored.approval,
        state=risk_state,
        policy=_policy(),
        checked_at=now,
    )
    if not authorization.authorized:
        print(json.dumps({
            "status": "REJECTED",
            "intent_id": stored.intent.intent_id,
            "reason_codes": authorization.reason_codes,
        }, ensure_ascii=False))
        return 3

    # Use the raw official client here: order requests are one-shot and must not
    # pass through the read retry wrapper.
    broker = KiwoomLiveBroker(raw, account_alias=account_alias)
    result = LiveOrderExecutor(broker, store).execute(
        stored.intent,
        authorization,
        submitted_at=now,
        exchange=args.exchange,
    )
    print(json.dumps({
        "status": result.state.value,
        "intent_id": result.intent_id,
        "broker_order_no": result.broker_order_no,
        "detail": result.detail,
    }, ensure_ascii=False))
    return 0 if result.state == LiveOrderState.ACKNOWLEDGED else 4


def set_kill_switch(args) -> int:
    now = datetime.now(KST)
    account_alias = _approved_account_alias(args.account_alias)
    active = args.state == "ON"
    if not active and args.confirm != "ENABLE_REAL_TRADING":
        raise RuntimeError("turning the kill switch OFF requires --confirm ENABLE_REAL_TRADING")
    _store(args.table).set_kill_switch(
        account_alias=account_alias,
        active=active,
        updated_at=now,
    )
    print(json.dumps({
        "status": "KILL_SWITCH_ON" if active else "KILL_SWITCH_OFF",
        "account_alias": account_alias,
        "updated_at": now.isoformat(),
    }, ensure_ascii=False))
    return 0


def _store(table_name: str | None) -> DynamoLiveOrderStore:
    import boto3

    resolved = table_name or os.getenv("LIVE_ORDER_TABLE", "")
    if not resolved:
        raise RuntimeError("LIVE_ORDER_TABLE or --table is required")
    return DynamoLiveOrderStore(boto3.client("dynamodb"), resolved)


def _real_clients():
    if os.getenv("KIWOOM_MODE", "") != "real":
        raise RuntimeError("KIWOOM_MODE=real is required for the live-order workflow")
    from kiwoom import get_client

    raw = get_client(mode="real", timeout_seconds=20)
    read = ReliableKiwoomClient(
        raw,
        KiwoomRetryPolicy(
            min_interval_seconds=float(os.getenv("KIWOOM_MIN_INTERVAL_SECONDS", "0.25")),
            max_attempts=int(os.getenv("KIWOOM_READ_MAX_ATTEMPTS", "4")),
        ),
    )
    return raw, read


def _approved_account_alias(value: str) -> str:
    value = value.strip()
    approved = os.getenv("LIVE_APPROVED_ACCOUNT_ALIAS", "").strip()
    if not value or not approved or value != approved:
        raise RuntimeError("account alias is missing or not explicitly approved")
    return value


def _policy() -> LiveOrderPolicy:
    return LiveOrderPolicy(
        live_order_enabled=os.getenv("LIVE_ORDER_ENABLED", "") == "1",
        maximum_order_amount=int(os.getenv("LIVE_MAX_ORDER_AMOUNT", "300000")),
        maximum_total_exposure=int(os.getenv("LIVE_MAX_TOTAL_EXPOSURE", "600000")),
        maximum_daily_loss=int(os.getenv("LIVE_MAX_DAILY_LOSS", "10000")),
        maximum_open_positions=int(os.getenv("LIVE_MAX_OPEN_POSITIONS", "2")),
        maximum_quote_age_seconds=int(os.getenv("LIVE_MAX_QUOTE_AGE_SECONDS", "60")),
        maximum_buy_slippage_pct=float(os.getenv("LIVE_MAX_BUY_SLIPPAGE_PCT", "0.5")),
        approval_ttl_seconds=int(os.getenv("LIVE_APPROVAL_TTL_SECONDS", "300")),
    )


def _current_quote(client: Any, code: str, fallback: datetime) -> tuple[datetime, int]:
    response = client.fetch_page(
        api_id="ka10007",
        path="/api/dostk/mrkcond",
        body={"stk_cd": code},
    )
    body = response.body
    if body.get("return_code") not in (None, 0, "0"):
        raise RuntimeError("Kiwoom quote request failed")
    price = abs(int(float(str(body.get("cur_prc", "0")).replace(",", ""))))
    if price <= 0:
        raise RuntimeError("verified current quote is unavailable")
    date_text = str(body.get("date", ""))
    time_text = str(body.get("tm", "")).zfill(6)
    observed_at = fallback
    if len(date_text) == 8 and len(time_text) == 6 and date_text.isdigit() and time_text.isdigit():
        observed_at = datetime.strptime(date_text + time_text, "%Y%m%d%H%M%S").replace(tzinfo=KST)
    return observed_at, price
