import unittest
from datetime import datetime, timedelta, timezone

from stock_automation.live_broker import BrokerOrder
from stock_automation.live_execution import (
    DynamoLiveOrderStore,
    LiveExecutionResult,
    LiveOrderExecutor,
    LiveOrderState,
)
from stock_automation.order_safety import (
    AuthorizationStatus,
    OrderAuthorization,
    OrderSide,
    UserApproval,
    approval_challenge,
    build_order_intent,
)

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 7, 15, 20, tzinfo=KST)


class ConditionalFailure(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeDdb:
    def __init__(self):
        self.items = {}

    def put_item(self, **kwargs):
        key = kwargs["Item"]["pk"]["S"]
        if key in self.items:
            raise ConditionalFailure()
        self.items[key] = dict(kwargs["Item"])

    def get_item(self, **kwargs):
        item = self.items.get(kwargs["Key"]["pk"]["S"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, **kwargs):
        key = kwargs["Key"]["pk"]["S"]
        item = self.items.get(key)
        if item is None:
            raise ConditionalFailure()
        values = kwargs["ExpressionAttributeValues"]
        current = item.get("status", {}).get("S")
        condition = kwargs.get("ConditionExpression", "")
        expected = None
        if ":pending" in condition:
            expected = values[":pending"]["S"]
            if item.get("challenge", {}).get("S") != values[":challenge"]["S"]:
                raise ConditionalFailure()
        elif ":ready" in condition:
            expected = values[":ready"]["S"]
        elif ":submitting" in condition:
            expected = values[":submitting"]["S"]
        if expected is not None and current != expected:
            raise ConditionalFailure()
        status_value = next(
            (values[name]["S"] for name in (":ready", ":submitting", ":ack", ":uncertain")
             if name in values and values[name]["S"] != current),
            current,
        )
        item["status"] = {"S": status_value}
        mappings = {
            ":approval": "approval_json", ":broker": "broker_order_json",
            ":number": "broker_order_no", ":reason": "uncertainty_reason",
            ":updated": "updated_at",
        }
        for token, field in mappings.items():
            if token in values:
                item[field] = values[token]

    def scan(self, **kwargs):
        return {"Items": [dict(item) for item in self.items.values()]}


class MemoryStore:
    def __init__(self, ready=True):
        self.ready = ready
        self.state = LiveOrderState.READY if ready else LiveOrderState.SUBMITTING
        self.order = None
        self.reason = None
        self.claims = 0

    def claim(self, intent_id, *, claimed_at):
        self.claims += 1
        if not self.ready:
            return False
        self.ready = False
        self.state = LiveOrderState.SUBMITTING
        return True

    def acknowledge(self, order, *, updated_at):
        self.order = order
        self.state = LiveOrderState.ACKNOWLEDGED

    def mark_uncertain(self, intent_id, *, reason, updated_at):
        self.reason = reason
        self.state = LiveOrderState.UNCERTAIN


class FakeBroker:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = 0

    def submit_limit_order(self, intent, authorization, *, submitted_at, exchange):
        self.calls += 1
        if self.failure:
            raise self.failure
        return BrokerOrder(
            intent.intent_id, "777", intent.side, intent.code, intent.quantity,
            intent.limit_price, exchange, submitted_at,
        )


def intent():
    return build_order_intent(
        event_id="EVENT-1", strategy="CLOSING_BET", side=OrderSide.BUY,
        code="123456", name="테스트", quantity=10, limit_price=10_000,
        reference_price=10_000, reference_at=NOW, created_at=NOW,
        account_alias="main",
    )


def authorization(order):
    return OrderAuthorization(
        AuthorizationStatus.AUTHORIZED, NOW, order.intent_id,
        ("ALL_LIVE_ORDER_GATES_PASSED",),
        approval_challenge(order),
    )


class LiveExecutionTests(unittest.TestCase):
    def test_pending_approval_ready_claim_and_ack_are_one_way(self):
        ddb = FakeDdb()
        store = DynamoLiveOrderStore(ddb, "table")
        order_intent = intent()
        self.assertTrue(store.create_pending(order_intent, created_at=NOW))
        self.assertFalse(store.create_pending(order_intent, created_at=NOW))
        user_approval = UserApproval(
            order_intent.intent_id, approval_challenge(order_intent), NOW, "USER"
        )
        self.assertTrue(store.approve(order_intent, user_approval, updated_at=NOW))
        self.assertTrue(store.claim(order_intent.intent_id, claimed_at=NOW))
        self.assertFalse(store.claim(order_intent.intent_id, claimed_at=NOW))
        broker_order = BrokerOrder(
            order_intent.intent_id, "777", OrderSide.BUY, "123456", 10, 10_000,
            "KRX", NOW,
        )
        store.acknowledge(broker_order, updated_at=NOW)
        loaded = store.load(order_intent.intent_id)
        self.assertEqual(LiveOrderState.ACKNOWLEDGED, loaded.state)
        self.assertEqual("777", loaded.broker_order.broker_order_no)
        self.assertEqual(
            frozenset({order_intent.intent_id}), store.submitted_intent_ids()
        )

    def test_kill_switch_defaults_on_and_requires_matching_account_control(self):
        ddb = FakeDdb()
        store = DynamoLiveOrderStore(ddb, "table")
        self.assertTrue(store.kill_switch_active(account_alias="main"))
        store.set_kill_switch(account_alias="main", active=False, updated_at=NOW)
        self.assertFalse(store.kill_switch_active(account_alias="main"))
        self.assertTrue(store.kill_switch_active(account_alias="different"))

    def test_executor_claims_before_call_and_records_ack(self):
        store = MemoryStore()
        broker = FakeBroker()
        order_intent = intent()
        result = LiveOrderExecutor(broker, store).execute(
            order_intent, authorization(order_intent), submitted_at=NOW
        )
        self.assertEqual(LiveOrderState.ACKNOWLEDGED, result.state)
        self.assertEqual(1, broker.calls)
        self.assertEqual(LiveOrderState.ACKNOWLEDGED, store.state)

    def test_unknown_broker_result_locks_order_without_retry(self):
        store = MemoryStore()
        broker = FakeBroker(TimeoutError("unknown"))
        order_intent = intent()
        executor = LiveOrderExecutor(broker, store)
        first = executor.execute(order_intent, authorization(order_intent), submitted_at=NOW)
        second = executor.execute(order_intent, authorization(order_intent), submitted_at=NOW)
        self.assertEqual(LiveOrderState.UNCERTAIN, first.state)
        self.assertEqual("DUPLICATE_OR_NON_READY_ORDER_BLOCKED", second.detail)
        self.assertEqual(1, broker.calls)

    def test_executor_rejects_expired_or_mutated_authorization_before_claim(self):
        order_intent = intent()
        expired_store = MemoryStore()
        with self.assertRaises(PermissionError):
            LiveOrderExecutor(FakeBroker(), expired_store).execute(
                order_intent,
                authorization(order_intent),
                submitted_at=order_intent.expires_at + timedelta(seconds=1),
            )
        self.assertEqual(0, expired_store.claims)

        changed = build_order_intent(
            event_id=order_intent.event_id,
            strategy=order_intent.strategy,
            side=order_intent.side,
            code=order_intent.code,
            name=order_intent.name,
            quantity=order_intent.quantity,
            limit_price=order_intent.limit_price,
            reference_price=9_900,
            reference_at=order_intent.reference_at,
            created_at=order_intent.created_at,
            account_alias=order_intent.account_alias,
        )
        changed_store = MemoryStore()
        with self.assertRaises(PermissionError):
            LiveOrderExecutor(FakeBroker(), changed_store).execute(
                changed, authorization(order_intent), submitted_at=NOW
            )
        self.assertEqual(0, changed_store.claims)


if __name__ == "__main__":
    unittest.main()
