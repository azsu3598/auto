from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from .live_broker import BrokerOrder, KiwoomLiveBroker
from .order_safety import (
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
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True, slots=True)
class StoredLiveOrder:
    intent: OrderIntent
    state: LiveOrderState
    approval: UserApproval | None = None
    broker_order: BrokerOrder | None = None
    uncertainty_reason: str | None = None


@dataclass(frozen=True, slots=True)
class LiveExecutionResult:
    intent_id: str
    state: LiveOrderState
    broker_order_no: str | None
    detail: str


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
        submitted_states = {
            LiveOrderState.SUBMITTING.value,
            LiveOrderState.ACKNOWLEDGED.value,
            LiveOrderState.UNCERTAIN.value,
        }
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
                "broker_order_no = :number, updated_at = :updated"
            ),
            ConditionExpression="#status = :submitting",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":ack": {"S": LiveOrderState.ACKNOWLEDGED.value},
                ":submitting": {"S": LiveOrderState.SUBMITTING.value},
                ":broker": {"S": _broker_order_json(order)},
                ":number": {"S": order.broker_order_no},
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


def _pk(intent_id: str) -> str:
    return f"LIVE_ORDER#{intent_id}"


def _approval_json(approval: UserApproval) -> str:
    raw = asdict(approval)
    raw["approved_at"] = approval.approved_at.isoformat()
    return json.dumps(raw, ensure_ascii=False, sort_keys=True)


def _broker_order_json(order: BrokerOrder) -> str:
    raw = asdict(order)
    raw["side"] = order.side.value
    raw["submitted_at"] = order.submitted_at.isoformat()
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
    )


def _conditional_failure(exc: Exception) -> bool:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code")
    return code in {"ConditionalCheckFailedException", "TransactionCanceledException"}
