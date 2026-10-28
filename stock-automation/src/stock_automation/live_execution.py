from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Protocol

from .live_broker import BrokerCancellation, BrokerOrder, BrokerOrderStatus, KiwoomLiveBroker
from .order_safety import (
    AccountRiskState,
    AuthorizationStatus,
    OrderAuthorization,
    OrderIntent,
    OrderSide,
    UserApproval,
    approval_challenge,
)


class LiveOrderState(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    READY = "READY"
    SUBMITTING = "SUBMITTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCEL_SUBMITTING = "CANCEL_SUBMITTING"
    CANCEL_ACKNOWLEDGED = "CANCEL_ACKNOWLEDGED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


ACTIVE_STATES = frozenset({
    LiveOrderState.SUBMITTING.value,
    LiveOrderState.ACKNOWLEDGED.value,
    LiveOrderState.PARTIALLY_FILLED.value,
    LiveOrderState.CANCEL_SUBMITTING.value,
    LiveOrderState.CANCEL_ACKNOWLEDGED.value,
    LiveOrderState.UNCERTAIN.value,
})
SUBMITTED_STATES = ACTIVE_STATES | {
    LiveOrderState.FILLED.value,
    LiveOrderState.CANCELLED.value,
    LiveOrderState.REJECTED.value,
}
AMBIGUOUS_STATES = frozenset({
    LiveOrderState.SUBMITTING,
    LiveOrderState.CANCEL_SUBMITTING,
    LiveOrderState.UNCERTAIN,
})
EXECUTION_LOCK_PK = "CONTROL#LIVE_EXECUTION_LOCK"
KST = timezone(timedelta(hours=9))


@dataclass(frozen=True, slots=True)
class StoredLiveOrder:
    intent: OrderIntent
    state: LiveOrderState
    approval: UserApproval | None = None
    broker_order: BrokerOrder | None = None
    uncertainty_reason: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class LiveExecutionResult:
    intent_id: str
    state: LiveOrderState
    broker_order_no: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class FillReconciliation:
    intent_id: str
    broker_order_no: str
    state: LiveOrderState
    cumulative_filled_quantity: int
    remaining_quantity: int
    fill_delta: int
    program_quantity: int
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class AccountGuard:
    account_alias: str
    account_fingerprint: str
    protected_holdings: dict[str, int]
    captured_at: datetime

    def protected_quantity(self, code: str) -> int:
        return max(0, int(self.protected_holdings.get(code, 0)))


@dataclass(frozen=True, slots=True)
class SupervisionResult:
    checked_at: datetime
    inspected_orders: int
    actions: tuple[str, ...]
    holding_mismatches: dict[str, tuple[int, int]]
    kill_switch_activated: bool


class LiveOrderStore(Protocol):
    def claim(self, intent_id: str, *, claimed_at: datetime) -> bool: ...
    def acknowledge(self, order: BrokerOrder, *, updated_at: datetime) -> None: ...
    def mark_uncertain(self, intent_id: str, *, reason: str, updated_at: datetime) -> None: ...


class LiveOrderExecutor:
    """Exactly-once-attempt coordinator.

    The broker itself cannot offer application idempotency. The store changes a
    READY order to SUBMITTING before the network call. Any exception after that
    call becomes UNCERTAIN and is never retried automatically.
    """

    def __init__(self, broker: KiwoomLiveBroker, store: LiveOrderStore) -> None:
        self.broker = broker
        self.store = store

    def execute(
        self,
        intent: OrderIntent,
        authorization: OrderAuthorization,
        *,
        submitted_at: datetime,
        exchange: str = "KRX",
    ) -> LiveExecutionResult:
        if authorization.status != AuthorizationStatus.AUTHORIZED:
            raise PermissionError("order authorization did not pass every safety gate")
        if authorization.intent_id != intent.intent_id:
            raise PermissionError("authorization intent mismatch")
        if authorization.intent_challenge != approval_challenge(intent):
            raise PermissionError("authorization is not bound to the exact order intent")
        if submitted_at.tzinfo is None or authorization.checked_at.tzinfo is None:
            raise ValueError("live execution timestamps must be timezone-aware")
        if submitted_at < authorization.checked_at or submitted_at > intent.expires_at:
            raise PermissionError("authorization or order intent expired before submission")
        if not self.store.claim(intent.intent_id, claimed_at=submitted_at):
            return LiveExecutionResult(
                intent_id=intent.intent_id,
                state=LiveOrderState.SUBMITTING,
                broker_order_no=None,
                detail="DUPLICATE_OR_NON_READY_ORDER_BLOCKED",
            )
        try:
            order = self.broker.submit_limit_order(
                intent,
                authorization,
                submitted_at=submitted_at,
                exchange=exchange,
            )
        except Exception as exc:
            reason = f"{type(exc).__name__}: broker result unknown; reconcile before retry"
            self.store.mark_uncertain(
                intent.intent_id, reason=reason, updated_at=submitted_at
            )
            return LiveExecutionResult(
                intent_id=intent.intent_id,
                state=LiveOrderState.UNCERTAIN,
                broker_order_no=None,
                detail=reason,
            )
        self.store.acknowledge(order, updated_at=submitted_at)
        return LiveExecutionResult(
            intent_id=intent.intent_id,
            state=LiveOrderState.ACKNOWLEDGED,
            broker_order_no=order.broker_order_no,
            detail="BROKER_ORDER_NUMBER_RECORDED",
        )


class DynamoLiveOrderStore:
    def __init__(self, ddb: Any, table_name: str) -> None:
        self.ddb = ddb
        self.table_name = table_name

    def create_pending(self, intent: OrderIntent, *, created_at: datetime) -> bool:
        item = {
            "pk": {"S": _pk(intent.intent_id)},
            "status": {"S": LiveOrderState.PENDING_APPROVAL.value},
            "intent_json": {"S": json.dumps(intent.to_dict(), ensure_ascii=False, sort_keys=True)},
            "challenge": {"S": approval_challenge(intent)},
            "updated_at": {"S": created_at.isoformat()},
        }
        try:
            self.ddb.put_item(
                TableName=self.table_name,
                Item=item,
                ConditionExpression="attribute_not_exists(pk)",
            )
            return True
        except Exception as exc:
            if _conditional_failure(exc):
                return False
            raise

    def initialize_account_guard(self, guard: AccountGuard) -> bool:
        if guard.captured_at.tzinfo is None:
            raise ValueError("account guard timestamp must be timezone-aware")
        if not guard.account_alias.strip() or not guard.account_fingerprint.strip():
            raise ValueError("account guard identity is required")
        protected = {
            str(code): max(0, int(quantity))
            for code, quantity in guard.protected_holdings.items()
            if int(quantity) > 0
        }
        item = {
            "pk": {"S": "CONTROL#ACCOUNT_GUARD"},
            "status": {"S": "BASELINE_LOCKED"},
            "account_alias": {"S": guard.account_alias},
            "account_fingerprint": {"S": guard.account_fingerprint},
            "protected_holdings_json": {
                "S": json.dumps(protected, ensure_ascii=False, sort_keys=True)
            },
            "captured_at": {"S": guard.captured_at.isoformat()},
            "updated_at": {"S": guard.captured_at.isoformat()},
        }
        try:
            self.ddb.put_item(
                TableName=self.table_name,
                Item=item,
                ConditionExpression="attribute_not_exists(pk)",
            )
            return True
        except Exception as exc:
            if _conditional_failure(exc):
                return False
            raise

    def load_account_guard(self) -> AccountGuard | None:
        response = self.ddb.get_item(
            TableName=self.table_name,
            Key={"pk": {"S": "CONTROL#ACCOUNT_GUARD"}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None
        holdings = json.loads(item["protected_holdings_json"]["S"])
        return AccountGuard(
            account_alias=item["account_alias"]["S"],
            account_fingerprint=item["account_fingerprint"]["S"],
            protected_holdings={str(code): int(quantity) for code, quantity in holdings.items()},
            captured_at=datetime.fromisoformat(item["captured_at"]["S"]),
        )

    def approve(
        self,
        intent: OrderIntent,
        approval: UserApproval,
        *,
        updated_at: datetime,
    ) -> bool:
        if approval.intent_id != intent.intent_id:
            raise ValueError("approval intent mismatch")
        if approval.challenge != approval_challenge(intent):
            raise ValueError("approval challenge mismatch")
        try:
            self.ddb.update_item(
                TableName=self.table_name,
                Key={"pk": {"S": _pk(intent.intent_id)}},
                UpdateExpression="SET #status = :ready, approval_json = :approval, updated_at = :updated",
                ConditionExpression="#status = :pending AND challenge = :challenge",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":ready": {"S": LiveOrderState.READY.value},
                    ":pending": {"S": LiveOrderState.PENDING_APPROVAL.value},
                    ":challenge": {"S": approval.challenge},
                    ":approval": {"S": _approval_json(approval)},
                    ":updated": {"S": updated_at.isoformat()},
                },
            )
            return True
        except Exception as exc:
            if _conditional_failure(exc):
                return False
            raise

    def load(self, intent_id: str) -> StoredLiveOrder | None:
        response = self.ddb.get_item(
            TableName=self.table_name,
            Key={"pk": {"S": _pk(intent_id)}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        return _stored_order(item) if item else None

    def submitted_intent_ids(self) -> frozenset[str]:
        submitted_states = SUBMITTED_STATES
        result: set[str] = set()
        start_key = None
        while True:
            request = {
                "TableName": self.table_name,
                "ProjectionExpression": "pk, #status",
                "ExpressionAttributeNames": {"#status": "status"},
            }
            if start_key:
                request["ExclusiveStartKey"] = start_key
            response = self.ddb.scan(**request)
            for item in response.get("Items", []):
                key = item.get("pk", {}).get("S", "")
                state = item.get("status", {}).get("S", "")
                if key.startswith("LIVE_ORDER#") and state in submitted_states:
                    result.add(key.removeprefix("LIVE_ORDER#"))
            start_key = response.get("LastEvaluatedKey")
            if not start_key:
                break
        return frozenset(result)

    def program_quantity(self, code: str) -> int:
        response = self.ddb.get_item(
            TableName=self.table_name,
            Key={"pk": {"S": _program_position_pk(code)}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        return max(0, int(item.get("quantity", {}).get("N", "0"))) if item else 0

    def program_positions(self) -> dict[str, int]:
        result: dict[str, int] = {}
        start_key = None
        while True:
            request: dict[str, Any] = {"TableName": self.table_name}
            if start_key:
                request["ExclusiveStartKey"] = start_key
            response = self.ddb.scan(**request)
            for item in response.get("Items", []):
                key = item.get("pk", {}).get("S", "")
                if key.startswith("PROGRAM_POSITION#"):
                    code = key.removeprefix("PROGRAM_POSITION#")
                    quantity = max(0, int(item.get("quantity", {}).get("N", "0")))
                    if code and quantity:
                        result[code] = quantity
            start_key = response.get("LastEvaluatedKey")
            if not start_key:
                return result

    def active_orders(self) -> tuple[StoredLiveOrder, ...]:
        return self._orders_in(ACTIVE_STATES)

    def submitted_orders(self) -> tuple[StoredLiveOrder, ...]:
        return self._orders_in(SUBMITTED_STATES)

    def acquire_execution_lock(
        self,
        owner: str,
        *,
        acquired_at: datetime,
        ttl_seconds: int = 120,
    ) -> bool:
        """Allow one live execution at a time; an abandoned lease expires."""
        if acquired_at.tzinfo is None:
            raise ValueError("execution lock timestamp must be timezone-aware")
        expires_at = acquired_at + timedelta(seconds=ttl_seconds)
        try:
            self.ddb.put_item(
                TableName=self.table_name,
                Item={
                    "pk": {"S": EXECUTION_LOCK_PK},
                    "owner": {"S": owner},
                    "acquired_at": {"S": acquired_at.isoformat()},
                    "expires_epoch": {"N": str(int(expires_at.timestamp()))},
                },
                ConditionExpression="attribute_not_exists(pk) OR expires_epoch < :now",
                ExpressionAttributeValues={":now": {"N": str(int(acquired_at.timestamp()))}},
            )
            return True
        except Exception as exc:
            if _conditional_failure(exc):
                return False
            raise

    def release_execution_lock(self, owner: str) -> None:
        try:
            self.ddb.delete_item(
                TableName=self.table_name,
                Key={"pk": {"S": EXECUTION_LOCK_PK}},
                ConditionExpression="#owner = :owner",
                ExpressionAttributeNames={"#owner": "owner"},
                ExpressionAttributeValues={":owner": {"S": owner}},
            )
        except Exception as exc:
            # Another owner took over an expired lease; never delete its lock.
            if not _conditional_failure(exc):
                raise

    def _orders_in(self, states: frozenset[str]) -> tuple[StoredLiveOrder, ...]:
        result: list[StoredLiveOrder] = []
        start_key = None
        while True:
            request: dict[str, Any] = {"TableName": self.table_name}
            if start_key:
                request["ExclusiveStartKey"] = start_key
            response = self.ddb.scan(**request)
            for item in response.get("Items", []):
                key = item.get("pk", {}).get("S", "")
                state = item.get("status", {}).get("S", "")
                if key.startswith("LIVE_ORDER#") and state in states:
                    result.append(_stored_order(item))
            start_key = response.get("LastEvaluatedKey")
            if not start_key:
                return tuple(result)

    def reconcile_fill(
        self,
        order: BrokerOrder,
        status: BrokerOrderStatus,
    ) -> FillReconciliation:
        if status.checked_at.tzinfo is None:
            raise ValueError("fill reconciliation timestamp must be timezone-aware")
        if status.broker_order_no != order.broker_order_no:
            raise ValueError("broker order number mismatch")
        if min(status.ordered_quantity, status.filled_quantity, status.remaining_quantity) < 0:
            raise ValueError("broker quantities cannot be negative")
        if status.filled_quantity + status.remaining_quantity > status.ordered_quantity:
            raise ValueError("broker quantities are inconsistent")

        stored = self.load(order.intent_id)
        if stored is None or stored.broker_order is None:
            raise RuntimeError("acknowledged live order is missing")
        if stored.broker_order.broker_order_no != order.broker_order_no:
            raise RuntimeError("stored broker order number mismatch")
        if stored.state not in {
            LiveOrderState.ACKNOWLEDGED,
            LiveOrderState.PARTIALLY_FILLED,
            LiveOrderState.CANCEL_ACKNOWLEDGED,
        }:
            if stored.state in {LiveOrderState.FILLED, LiveOrderState.CANCELLED, LiveOrderState.REJECTED}:
                return FillReconciliation(
                    order.intent_id,
                    order.broker_order_no,
                    stored.state,
                    status.filled_quantity,
                    status.remaining_quantity,
                    0,
                    self.program_quantity(order.code),
                    status.checked_at,
                )
            raise RuntimeError(f"order state cannot be reconciled: {stored.state.value}")

        raw = self.ddb.get_item(
            TableName=self.table_name,
            Key={"pk": {"S": _pk(order.intent_id)}},
            ConsistentRead=True,
        ).get("Item", {})
        previous = int(raw.get("last_filled_quantity", {}).get("N", "0"))
        if status.filled_quantity < previous:
            raise RuntimeError("broker cumulative fill quantity moved backwards")
        delta = status.filled_quantity - previous
        state = _reconciled_state(status)
        if (
            stored.state == LiveOrderState.CANCEL_ACKNOWLEDGED
            and state in {LiveOrderState.ACKNOWLEDGED, LiveOrderState.PARTIALLY_FILLED}
        ):
            state = LiveOrderState.CANCEL_ACKNOWLEDGED

        values = {
            ":previous": {"N": str(previous)},
            ":filled": {"N": str(status.filled_quantity)},
            ":remaining": {"N": str(status.remaining_quantity)},
            ":state": {"S": state.value},
            ":ack": {"S": LiveOrderState.ACKNOWLEDGED.value},
            ":partial": {"S": LiveOrderState.PARTIALLY_FILLED.value},
            ":cancel_ack": {"S": LiveOrderState.CANCEL_ACKNOWLEDGED.value},
            ":number": {"S": order.broker_order_no},
            ":checked": {"S": status.checked_at.isoformat()},
            ":status_text": {"S": status.status_text[:200]},
        }
        transaction: list[dict[str, Any]] = [{
            "Update": {
                "TableName": self.table_name,
                "Key": {"pk": {"S": _pk(order.intent_id)}},
                "UpdateExpression": (
                    "SET #status = :state, last_filled_quantity = :filled, "
                    "remaining_quantity = :remaining, broker_status_text = :status_text, "
                    "last_reconciled_at = :checked, updated_at = :checked"
                ),
                "ConditionExpression": (
                    "broker_order_no = :number AND (#status = :ack OR #status = :partial "
                    "OR #status = :cancel_ack) "
                    "AND (attribute_not_exists(last_filled_quantity) OR last_filled_quantity = :previous)"
                ),
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": values,
            }
        }]
        if delta:
            signed_delta = delta if order.side == OrderSide.BUY else -delta
            position_update: dict[str, Any] = {
                "TableName": self.table_name,
                "Key": {"pk": {"S": _program_position_pk(order.code)}},
                "UpdateExpression": (
                    "SET code = :code, updated_at = :checked ADD quantity :delta"
                ),
                "ExpressionAttributeValues": {
                    ":code": {"S": order.code},
                    ":checked": {"S": status.checked_at.isoformat()},
                    ":delta": {"N": str(signed_delta)},
                },
            }
            if order.side == OrderSide.SELL:
                position_update["ConditionExpression"] = "attribute_exists(pk) AND quantity >= :required"
                position_update["ExpressionAttributeValues"][":required"] = {"N": str(delta)}
            transaction.append({"Update": position_update})
        try:
            self.ddb.transact_write_items(TransactItems=transaction)
        except Exception as exc:
            if not _conditional_failure(exc):
                raise
            latest = self.ddb.get_item(
                TableName=self.table_name,
                Key={"pk": {"S": _pk(order.intent_id)}},
                ConsistentRead=True,
            ).get("Item", {})
            latest_filled = int(latest.get("last_filled_quantity", {}).get("N", "-1"))
            latest_state = latest.get("status", {}).get("S", "")
            if latest_filled != status.filled_quantity or latest_state != state.value:
                raise
            delta = 0
        return FillReconciliation(
            order.intent_id,
            order.broker_order_no,
            state,
            status.filled_quantity,
            status.remaining_quantity,
            delta,
            self.program_quantity(order.code),
            status.checked_at,
        )

    def set_kill_switch(
        self,
        *,
        account_alias: str,
        active: bool,
        updated_at: datetime,
    ) -> None:
        self.ddb.put_item(
            TableName=self.table_name,
            Item={
                "pk": {"S": "CONTROL#LIVE"},
                "status": {"S": "KILL_SWITCH_ON" if active else "KILL_SWITCH_OFF"},
                "account_alias": {"S": account_alias},
                "updated_at": {"S": updated_at.isoformat()},
            },
        )

    def kill_switch_active(self, *, account_alias: str) -> bool:
        response = self.ddb.get_item(
            TableName=self.table_name,
            Key={"pk": {"S": "CONTROL#LIVE"}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return True
        if item.get("account_alias", {}).get("S") != account_alias:
            return True
        return item.get("status", {}).get("S") != "KILL_SWITCH_OFF"

    def claim(self, intent_id: str, *, claimed_at: datetime) -> bool:
        try:
            self.ddb.update_item(
                TableName=self.table_name,
                Key={"pk": {"S": _pk(intent_id)}},
                UpdateExpression="SET #status = :submitting, updated_at = :updated",
                ConditionExpression="#status = :ready",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":ready": {"S": LiveOrderState.READY.value},
                    ":submitting": {"S": LiveOrderState.SUBMITTING.value},
                    ":updated": {"S": claimed_at.isoformat()},
                },
            )
            return True
        except Exception as exc:
            if _conditional_failure(exc):
                return False
            raise

    def acknowledge(self, order: BrokerOrder, *, updated_at: datetime) -> None:
        self.ddb.update_item(
            TableName=self.table_name,
            Key={"pk": {"S": _pk(order.intent_id)}},
            UpdateExpression=(
                "SET #status = :ack, broker_order_json = :broker, "
                "broker_order_no = :number, last_filled_quantity = :zero, "
                "remaining_quantity = :remaining, updated_at = :updated"
            ),
            ConditionExpression="#status = :submitting",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":ack": {"S": LiveOrderState.ACKNOWLEDGED.value},
                ":submitting": {"S": LiveOrderState.SUBMITTING.value},
                ":broker": {"S": _broker_order_json(order)},
                ":number": {"S": order.broker_order_no},
                ":zero": {"N": "0"},
                ":remaining": {"N": str(order.quantity)},
                ":updated": {"S": updated_at.isoformat()},
            },
        )

    def claim_cancel(
        self,
        order: BrokerOrder,
        *,
        remaining_quantity: int,
        requested_at: datetime,
    ) -> bool:
        if remaining_quantity <= 0:
            return False
        try:
            self.ddb.update_item(
                TableName=self.table_name,
                Key={"pk": {"S": _pk(order.intent_id)}},
                UpdateExpression="SET #status = :cancel_submitting, updated_at = :updated",
                ConditionExpression=(
                    "broker_order_no = :number AND remaining_quantity = :remaining AND "
                    "(#status = :ack OR #status = :partial)"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":ack": {"S": LiveOrderState.ACKNOWLEDGED.value},
                    ":partial": {"S": LiveOrderState.PARTIALLY_FILLED.value},
                    ":cancel_submitting": {"S": LiveOrderState.CANCEL_SUBMITTING.value},
                    ":number": {"S": order.broker_order_no},
                    ":remaining": {"N": str(remaining_quantity)},
                    ":updated": {"S": requested_at.isoformat()},
                },
            )
            return True
        except Exception as exc:
            if _conditional_failure(exc):
                return False
            raise

    def acknowledge_cancel(
        self,
        cancellation: BrokerCancellation,
        *,
        updated_at: datetime,
    ) -> None:
        self.ddb.update_item(
            TableName=self.table_name,
            Key={"pk": {"S": _pk(cancellation.intent_id)}},
            UpdateExpression=(
                "SET #status = :cancel_ack, cancellation_json = :cancellation, "
                "cancellation_order_no = :cancel_number, updated_at = :updated"
            ),
            ConditionExpression=(
                "#status = :cancel_submitting AND broker_order_no = :original_number"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":cancel_ack": {"S": LiveOrderState.CANCEL_ACKNOWLEDGED.value},
                ":cancel_submitting": {"S": LiveOrderState.CANCEL_SUBMITTING.value},
                ":cancellation": {"S": _cancellation_json(cancellation)},
                ":cancel_number": {"S": cancellation.cancellation_order_no},
                ":original_number": {"S": cancellation.original_order_no},
                ":updated": {"S": updated_at.isoformat()},
            },
        )

    def mark_cancel_uncertain(
        self,
        intent_id: str,
        *,
        reason: str,
        updated_at: datetime,
    ) -> None:
        self.ddb.update_item(
            TableName=self.table_name,
            Key={"pk": {"S": _pk(intent_id)}},
            UpdateExpression="SET #status = :uncertain, uncertainty_reason = :reason, updated_at = :updated",
            ConditionExpression="#status = :cancel_submitting",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":uncertain": {"S": LiveOrderState.UNCERTAIN.value},
                ":cancel_submitting": {"S": LiveOrderState.CANCEL_SUBMITTING.value},
                ":reason": {"S": reason[:500]},
                ":updated": {"S": updated_at.isoformat()},
            },
        )

    def mark_uncertain(self, intent_id: str, *, reason: str, updated_at: datetime) -> None:
        self.ddb.update_item(
            TableName=self.table_name,
            Key={"pk": {"S": _pk(intent_id)}},
            UpdateExpression="SET #status = :uncertain, uncertainty_reason = :reason, updated_at = :updated",
            ConditionExpression="#status = :submitting",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":uncertain": {"S": LiveOrderState.UNCERTAIN.value},
                ":submitting": {"S": LiveOrderState.SUBMITTING.value},
                ":reason": {"S": reason[:500]},
                ":updated": {"S": updated_at.isoformat()},
            },
        )


class LiveOrderSupervisor:
    """Reconcile open orders and fail closed on ambiguous broker/account state."""

    def __init__(
        self,
        broker: KiwoomLiveBroker,
        store: DynamoLiveOrderStore,
        *,
        account_alias: str,
        max_unfilled_seconds: int = 180,
        exchange: str = "KRX",
    ) -> None:
        if max_unfilled_seconds <= 0:
            raise ValueError("max_unfilled_seconds must be positive")
        self.broker = broker
        self.store = store
        self.account_alias = account_alias
        self.max_unfilled = timedelta(seconds=max_unfilled_seconds)
        self.exchange = exchange

    def run_once(
        self,
        *,
        checked_at: datetime,
        observed_account_fingerprint: str,
    ) -> SupervisionResult:
        if checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        actions: list[str] = []
        activate_kill = False
        guard = self.store.load_account_guard()
        if (
            guard is None
            or guard.account_alias != self.account_alias
            or guard.account_fingerprint != observed_account_fingerprint
        ):
            activate_kill = True
            actions.append("ACCOUNT_GUARD_MISMATCH")

        active = self.store.active_orders()
        for stored in active:
            order = stored.broker_order
            if order is None or stored.state in AMBIGUOUS_STATES:
                activate_kill = True
                actions.append(f"{stored.intent.intent_id}:AMBIGUOUS_ORDER_STATE")
                continue
            try:
                status = self.broker.order_status(order, checked_at=checked_at)
            except Exception as exc:
                activate_kill = True
                actions.append(
                    f"{order.intent_id}:STATUS_CHECK_FAILED:{type(exc).__name__}"
                )
                continue
            if status.status_text == "NOT_FOUND_REQUIRES_MANUAL_RECONCILIATION":
                activate_kill = True
                actions.append(f"{order.intent_id}:BROKER_ORDER_NOT_FOUND")
                continue
            try:
                result = self.store.reconcile_fill(order, status)
            except Exception as exc:
                activate_kill = True
                actions.append(
                    f"{order.intent_id}:RECONCILIATION_FAILED:{type(exc).__name__}"
                )
                continue
            actions.append(f"{order.intent_id}:RECONCILED:{result.state.value}")
            if (
                result.state in {LiveOrderState.ACKNOWLEDGED, LiveOrderState.PARTIALLY_FILLED}
                and result.remaining_quantity > 0
                and checked_at - order.submitted_at >= self.max_unfilled
            ):
                if not self.store.claim_cancel(
                    order,
                    remaining_quantity=result.remaining_quantity,
                    requested_at=checked_at,
                ):
                    activate_kill = True
                    actions.append(f"{order.intent_id}:CANCEL_CLAIM_FAILED")
                    continue
                try:
                    cancellation = self.broker.cancel_order(
                        order,
                        quantity=result.remaining_quantity,
                        requested_at=checked_at,
                    )
                except Exception as exc:
                    reason = f"{type(exc).__name__}: cancellation result unknown; do not retry"
                    self.store.mark_cancel_uncertain(
                        order.intent_id, reason=reason, updated_at=checked_at
                    )
                    activate_kill = True
                    actions.append(f"{order.intent_id}:CANCEL_UNCERTAIN")
                else:
                    self.store.acknowledge_cancel(cancellation, updated_at=checked_at)
                    actions.append(f"{order.intent_id}:CANCEL_ACKNOWLEDGED")

        mismatches: dict[str, tuple[int, int]] = {}
        try:
            actual_holdings = self.broker.holdings(exchange=self.exchange)
            program_positions = self.store.program_positions()
            protected = guard.protected_holdings if guard else {}
            mismatches = holding_mismatches(
                actual_holdings, protected, program_positions
            )
        except Exception as exc:
            activate_kill = True
            actions.append(f"HOLDINGS_CHECK_FAILED:{type(exc).__name__}")
        else:
            if mismatches:
                activate_kill = True
                actions.append("HOLDINGS_MISMATCH")
        if activate_kill:
            self.store.set_kill_switch(
                account_alias=self.account_alias, active=True, updated_at=checked_at
            )
        return SupervisionResult(
            checked_at=checked_at,
            inspected_orders=len(active),
            actions=tuple(actions),
            holding_mismatches=mismatches,
            kill_switch_activated=activate_kill,
        )


def apply_order_book(
    state: AccountRiskState,
    intent: OrderIntent,
    *,
    active: tuple[StoredLiveOrder, ...],
    submitted: tuple[StoredLiveOrder, ...],
    program_positions: dict[str, int],
) -> AccountRiskState:
    """Add in-flight program orders to an account risk snapshot.

    Open buy orders count at their full approved amount (conservative for
    partial fills) and as open positions, so a second order cannot spend the
    same cash or limit before the first one is reconciled.
    """
    trading_date = intent.created_at.astimezone(KST).date()
    open_buys = [
        stored for stored in active
        if stored.intent.side == OrderSide.BUY and stored.state not in AMBIGUOUS_STATES
        and stored.intent.intent_id != intent.intent_id
    ]
    codes = {code for code, quantity in program_positions.items() if quantity > 0}
    codes |= {stored.intent.code for stored in open_buys}
    same_code_buys = sum(
        1 for stored in submitted
        if stored.intent.side == OrderSide.BUY
        and stored.intent.code == intent.code
        and stored.state != LiveOrderState.REJECTED
        and stored.intent.created_at.astimezone(KST).date() == trading_date
    )
    return replace(
        state,
        current_exposure=state.current_exposure + sum(s.intent.order_amount for s in open_buys),
        open_positions=max(state.open_positions, len(codes)),
        same_code_buy_orders_today=same_code_buys,
        ambiguous_orders=sum(1 for stored in active if stored.state in AMBIGUOUS_STATES),
    )


def holding_mismatches(
    actual_holdings: dict[str, int],
    protected_holdings: dict[str, int],
    program_positions: dict[str, int],
) -> dict[str, tuple[int, int]]:
    """Return code -> (expected, actual) for exact account reconciliation."""
    codes = set(actual_holdings) | set(protected_holdings) | set(program_positions)
    result: dict[str, tuple[int, int]] = {}
    for code in sorted(codes):
        expected = max(0, int(protected_holdings.get(code, 0))) + max(
            0, int(program_positions.get(code, 0))
        )
        actual = max(0, int(actual_holdings.get(code, 0)))
        if expected != actual:
            result[code] = (expected, actual)
    return result


def _pk(intent_id: str) -> str:
    return f"LIVE_ORDER#{intent_id}"


def _program_position_pk(code: str) -> str:
    return f"PROGRAM_POSITION#{code}"


def _reconciled_state(status: BrokerOrderStatus) -> LiveOrderState:
    text = status.status_text.strip().upper()
    if status.remaining_quantity == 0 and status.filled_quantity == status.ordered_quantity:
        return LiveOrderState.FILLED
    if any(token in text for token in ("거부", "REJECT")):
        return LiveOrderState.REJECTED
    if any(token in text for token in ("취소", "CANCEL")):
        return LiveOrderState.CANCELLED
    if status.filled_quantity > 0:
        return LiveOrderState.PARTIALLY_FILLED
    return LiveOrderState.ACKNOWLEDGED


def _approval_json(approval: UserApproval) -> str:
    raw = asdict(approval)
    raw["approved_at"] = approval.approved_at.isoformat()
    return json.dumps(raw, ensure_ascii=False, sort_keys=True)


def _broker_order_json(order: BrokerOrder) -> str:
    raw = asdict(order)
    raw["side"] = order.side.value
    raw["submitted_at"] = order.submitted_at.isoformat()
    return json.dumps(raw, ensure_ascii=False, sort_keys=True)


def _cancellation_json(cancellation: BrokerCancellation) -> str:
    raw = asdict(cancellation)
    raw["requested_at"] = cancellation.requested_at.isoformat()
    return json.dumps(raw, ensure_ascii=False, sort_keys=True)


def _stored_order(item: dict[str, dict[str, str]]) -> StoredLiveOrder:
    raw_intent = json.loads(item["intent_json"]["S"])
    for key in ("reference_at", "created_at", "expires_at"):
        raw_intent[key] = datetime.fromisoformat(raw_intent[key])
    raw_intent["side"] = OrderSide(raw_intent["side"])
    intent = OrderIntent(**raw_intent)
    approval = None
    if "approval_json" in item:
        raw_approval = json.loads(item["approval_json"]["S"])
        raw_approval["approved_at"] = datetime.fromisoformat(raw_approval["approved_at"])
        approval = UserApproval(**raw_approval)
    broker_order = None
    if "broker_order_json" in item:
        raw_broker = json.loads(item["broker_order_json"]["S"])
        raw_broker["side"] = OrderSide(raw_broker["side"])
        raw_broker["submitted_at"] = datetime.fromisoformat(raw_broker["submitted_at"])
        broker_order = BrokerOrder(**raw_broker)
    return StoredLiveOrder(
        intent=intent,
        state=LiveOrderState(item["status"]["S"]),
        approval=approval,
        broker_order=broker_order,
        uncertainty_reason=item.get("uncertainty_reason", {}).get("S"),
        updated_at=(
            datetime.fromisoformat(item["updated_at"]["S"])
            if item.get("updated_at", {}).get("S")
            else None
        ),
    )


def _conditional_failure(exc: Exception) -> bool:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code")
    return code in {"ConditionalCheckFailedException", "TransactionCanceledException"}
