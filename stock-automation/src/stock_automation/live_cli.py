from __future__ import annotations

import json
import os
from hashlib import sha256
from datetime import datetime, timedelta, timezone
from typing import Any

from .live_broker import KiwoomLiveBroker
from .live_execution import (
    AccountGuard,
    DynamoLiveOrderStore,
    LiveOrderExecutor,
    LiveOrderSupervisor,
    LiveOrderState,
    apply_order_book,
    holding_mismatches,
)
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
    observed_at, reference_price = _current_quote(read, args.code)
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
    # One live execution at a time: cash, exposure and per-code checks below
    # must not race another order that has not been recorded yet.
    if not store.acquire_execution_lock(stored.intent.intent_id, acquired_at=now):
        raise RuntimeError("another live execution is in progress; no order was submitted")
    try:
        return _execute_locked(args, store, stored, account_alias, now)
    finally:
        store.release_execution_lock(stored.intent.intent_id)


def _execute_locked(args, store, stored, account_alias: str, now: datetime) -> int:
    guard = store.load_account_guard()
    if guard is None:
        raise RuntimeError("protected account baseline is missing")
    raw, read = _real_clients()
    observed_fingerprint = _verified_account_fingerprint(read, account_alias)
    if guard.account_alias != account_alias or guard.account_fingerprint != observed_fingerprint:
        raise RuntimeError("account guard does not match the active account")

    observed_at, current_price = _current_quote(read, stored.intent.code)
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
    program_positions = store.program_positions()
    # Exact whole-account reconciliation: every holding must equal the locked
    # baseline plus program quantity before any new order is allowed.
    mismatches = holding_mismatches(
        read_broker.holdings(exchange=args.exchange),
        guard.protected_holdings,
        program_positions,
    )
    risk_state = read_broker.account_risk_state(
        code=stored.intent.code,
        trading_date=now.strftime("%Y%m%d"),
        kill_switch_active=store.kill_switch_active(account_alias=account_alias),
        already_submitted_intent_ids=store.submitted_intent_ids(),
        exchange=args.exchange,
        observed_account_fingerprint=observed_fingerprint,
        protected_baseline_quantity=guard.protected_quantity(stored.intent.code),
        program_owned_quantity=program_positions.get(stored.intent.code, 0),
        holdings_reconciled=not mismatches,
        program_positions=program_positions,
    )
    risk_state = apply_order_book(
        risk_state,
        stored.intent,
        active=store.active_orders(),
        submitted=store.submitted_orders(),
        program_positions=program_positions,
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


def initialize_account_baseline(args) -> int:
    """Capture existing holdings once while the kill switch remains active."""
    if args.confirm != "PROTECT_EXISTING_HOLDINGS":
        raise RuntimeError(
            "baseline capture requires --confirm PROTECT_EXISTING_HOLDINGS"
        )
    now = datetime.now(KST)
    account_alias = _approved_account_alias(args.account_alias)
    store = _store(args.table)
    if not store.kill_switch_active(account_alias=account_alias):
        raise RuntimeError("turn the live kill switch ON before baseline capture")
    _raw, read = _real_clients()
    broker = KiwoomLiveBroker(read, account_alias=account_alias)
    guard = AccountGuard(
        account_alias=account_alias,
        account_fingerprint=_verified_account_fingerprint(read, account_alias),
        protected_holdings=broker.holdings(exchange=args.exchange),
        captured_at=now,
    )
    if not store.initialize_account_guard(guard):
        raise RuntimeError("account baseline is already locked; it was not overwritten")
    print(json.dumps({
        "status": "ACCOUNT_BASELINE_LOCKED",
        "account_alias": account_alias,
        "protected_symbol_count": len(guard.protected_holdings),
        "captured_at": now.isoformat(),
        "warning": "account number and quantities are intentionally not printed",
    }, ensure_ascii=False))
    return 0


def reconcile(args) -> int:
    """Poll one known broker order and apply only its new cumulative fill delta."""
    now = datetime.now(KST)
    store = _store(args.table)
    stored = store.load(args.intent_id)
    if stored is None or stored.broker_order is None:
        raise RuntimeError("acknowledged broker order was not found")
    account_alias = _approved_account_alias(stored.intent.account_alias)
    _raw, read = _real_clients()
    broker = KiwoomLiveBroker(read, account_alias=account_alias)
    status = broker.order_status(stored.broker_order, checked_at=now)
    if status.status_text == "NOT_FOUND_REQUIRES_MANUAL_RECONCILIATION":
        store.set_kill_switch(account_alias=account_alias, active=True, updated_at=now)
        raise RuntimeError("broker order was not found; kill switch turned ON")
    result = store.reconcile_fill(stored.broker_order, status)
    print(json.dumps({
        "status": result.state.value,
        "intent_id": result.intent_id,
        "broker_order_no": result.broker_order_no,
        "cumulative_filled_quantity": result.cumulative_filled_quantity,
        "new_fill_quantity": result.fill_delta,
        "program_quantity": result.program_quantity,
        "checked_at": result.checked_at.isoformat(),
    }, ensure_ascii=False))
    return 0


def supervise(args) -> int:
    """Run one explicitly confirmed safety cycle; this is not an always-on loop."""
    if args.confirm != "SUPERVISE_REAL_ORDERS":
        raise RuntimeError(
            "supervision may cancel stale orders; use --confirm SUPERVISE_REAL_ORDERS"
        )
    if os.getenv("LIVE_ORDER_ENABLED", "") != "1":
        raise RuntimeError("LIVE_ORDER_ENABLED must be exactly 1")
    now = datetime.now(KST)
    account_alias = _approved_account_alias(args.account_alias)
    store = _store(args.table)
    raw, read = _real_clients()
    # One raw client is intentional: a cancellation is a state-changing request
    # and must never inherit automatic retry behavior from the read client.
    broker = KiwoomLiveBroker(raw, account_alias=account_alias)
    try:
        observed_fingerprint = _verified_account_fingerprint(read, account_alias)
    except RuntimeError:
        # The supervisor turns the kill switch ON for an unverifiable account.
        observed_fingerprint = ""
    result = LiveOrderSupervisor(
        broker,
        store,
        account_alias=account_alias,
        max_unfilled_seconds=args.max_unfilled_seconds,
        exchange=args.exchange,
    ).run_once(
        checked_at=now,
        observed_account_fingerprint=observed_fingerprint,
    )
    print(json.dumps({
        "status": "KILL_SWITCH_ON" if result.kill_switch_activated else "SUPERVISION_OK",
        "checked_at": result.checked_at.isoformat(),
        "inspected_orders": result.inspected_orders,
        "actions": result.actions,
        "holding_mismatches": result.holding_mismatches,
    }, ensure_ascii=False))
    return 5 if result.kill_switch_activated else 0


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
        maximum_daily_buy_orders_per_code=int(
            os.getenv("LIVE_MAX_DAILY_BUY_ORDERS_PER_CODE", "1")
        ),
        expected_account_fingerprint=(
            os.getenv("LIVE_APPROVED_ACCOUNT_FINGERPRINT", "").strip() or None
        ),
    )


def _account_fingerprint() -> str:
    account_number = os.getenv("KIWOOM_ACCOUNT_NUMBER", "").strip()
    salt = os.getenv("LIVE_ACCOUNT_FINGERPRINT_SALT", "").strip()
    if not account_number or len(salt) < 16:
        raise RuntimeError(
            "KIWOOM_ACCOUNT_NUMBER and a 16+ character LIVE_ACCOUNT_FINGERPRINT_SALT are required"
        )
    return sha256(f"{salt}|{account_number}".encode()).hexdigest()


def _verified_account_fingerprint(client: Any, account_alias: str) -> str:
    """Fingerprint the configured account only if the broker token uses exactly it."""
    configured = "".join(c for c in os.getenv("KIWOOM_ACCOUNT_NUMBER", "") if c.isdigit())
    numbers = KiwoomLiveBroker(client, account_alias=account_alias).account_numbers()
    # More than one account makes the order destination ambiguous.
    if not configured or numbers != (configured,):
        raise RuntimeError("broker account does not match the approved account")
    return _account_fingerprint()


def _current_quote(client: Any, code: str) -> tuple[datetime, int]:
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
    date_text = str(body.get("date", "")).strip()
    time_text = str(body.get("tm", "")).strip().zfill(6)
    # Without the broker's quote time the freshness check cannot be proven.
    if not (len(date_text) == 8 and len(time_text) == 6 and date_text.isdigit() and time_text.isdigit()):
        raise RuntimeError("quote time is missing; freshness cannot be verified")
    return datetime.strptime(date_text + time_text, "%Y%m%d%H%M%S").replace(tzinfo=KST), price
