"""End-to-end live-order scenarios on scripted Kiwoom responses.

The real broker adapter, DynamoDB store, executor and supervisor run together;
only the Kiwoom HTTP client and DynamoDB are fakes. No network calls.
"""
import unittest
from datetime import timedelta
from types import SimpleNamespace

from stock_automation.live_broker import KiwoomLiveBroker
from stock_automation.live_execution import (
    AccountGuard,
    DynamoLiveOrderStore,
    LiveOrderExecutor,
    LiveOrderState,
    LiveOrderSupervisor,
)
from stock_automation.order_safety import (
    AccountRiskState,
    LiveOrderPolicy,
    OrderSide,
    UserApproval,
    approval_challenge,
    authorize_live_order,
    build_order_intent,
)
from test_live_execution import NOW, FakeDdb


class Response:
    def __init__(self, body, cont_yn="N", next_key=None):
        self.body = body
        self.continuation = SimpleNamespace(cont_yn=cont_yn, next_key=next_key)


class ScriptedClient:
    """Return queued responses per api_id; the last one repeats."""

    def __init__(self, **script):
        self.script = {api: list(items) for api, items in script.items()}
        self.calls = []

    def fetch_page(self, **kwargs):
        self.calls.append(kwargs)
        queue = self.script.get(kwargs["api_id"])
        if not queue:
            raise AssertionError(f"unexpected Kiwoom call {kwargs['api_id']}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, Response) else Response(item)

    def count(self, api_id):
        return sum(1 for call in self.calls if call["api_id"] == api_id)


def ok(**fields):
    return {"return_code": 0, **fields}


def order_row(filled, remaining, status, number="0001234", ordered=10):
    return ok(acnt_ord_cntr_prps_dtl=[{
        "ord_no": number, "ord_qty": str(ordered), "cntr_qty": str(filled),
        "ord_remnq": str(remaining), "cntr_uv": "10000", "acpt_tp": status,
    }])


def holdings(**quantities):
    return ok(acnt_evlt_remn_indv_tot=[
        {"stk_cd": code, "rmnd_qty": str(quantity)} for code, quantity in quantities.items()
    ])


class Scenario:
    """One approved order in a fresh live table with an empty protected baseline."""

    def __init__(self, client, *, side=OrderSide.BUY, quantity=10, protected=None, program=None):
        self.client = client
        self.store = DynamoLiveOrderStore(FakeDdb(), "stock-automation-live")
        self.store.initialize_account_guard(AccountGuard("main", "fp", protected or {}, NOW))
        for code, amount in (program or {}).items():
            self.store.ddb.items[f"PROGRAM_POSITION#{code}"] = {
                "pk": {"S": f"PROGRAM_POSITION#{code}"}, "quantity": {"N": str(amount)},
            }
        self.broker = KiwoomLiveBroker(client, account_alias="main")
        self.intent = build_order_intent(
            event_id="EVENT-1", strategy="CLOSING_BET", side=side, code="123456",
            name="테스트", quantity=quantity, limit_price=10_000, reference_price=10_000,
            reference_at=NOW, created_at=NOW, account_alias="main",
        )
        approval = UserApproval(self.intent.intent_id, approval_challenge(self.intent), NOW, "USER")
        self.store.create_pending(self.intent, created_at=NOW)
        self.store.approve(self.intent, approval, updated_at=NOW)
        self.authorization = authorize_live_order(
            self.intent,
            approval=approval,
            state=AccountRiskState(
                "main", 600_000, 0, 0, 0, 10, False,
                observed_account_fingerprint="fp", holdings_reconciled=True,
                program_owned_quantity=quantity,
            ),
            policy=LiveOrderPolicy(live_order_enabled=True, expected_account_fingerprint="fp"),
            checked_at=NOW,
        )
        assert self.authorization.authorized, self.authorization.reason_codes

    def execute(self):
        return LiveOrderExecutor(self.broker, self.store).execute(
            self.intent, self.authorization, submitted_at=NOW
        )

    def supervise(self, seconds):
        return LiveOrderSupervisor(self.broker, self.store, account_alias="main").run_once(
            checked_at=NOW + timedelta(seconds=seconds), observed_account_fingerprint="fp"
        )

    def state(self):
        return self.store.load(self.intent.intent_id).state


class SubmissionScenarios(unittest.TestCase):
    def test_broker_error_response_is_locked_as_uncertain_and_never_resent(self):
        client = ScriptedClient(kt10000=[{"return_code": 20, "return_msg": "주문가능금액 부족"}])
        scenario = Scenario(client)
        first = scenario.execute()
        second = scenario.execute()
        self.assertEqual(LiveOrderState.UNCERTAIN, first.state)
        self.assertEqual("DUPLICATE_OR_NON_READY_ORDER_BLOCKED", second.detail)
        self.assertEqual(1, client.count("kt10000"))

    def test_accepted_response_without_order_number_is_uncertain(self):
        client = ScriptedClient(kt10000=[ok()])
        scenario = Scenario(client)
        self.assertEqual(LiveOrderState.UNCERTAIN, scenario.execute().state)
        self.assertEqual(LiveOrderState.UNCERTAIN, scenario.state())

    def test_response_lost_after_send_is_not_retried_and_restart_turns_kill_switch_on(self):
        client = ScriptedClient(kt10000=[TimeoutError("read timed out")], kt00018=[holdings()])
        scenario = Scenario(client)
        self.assertEqual(LiveOrderState.UNCERTAIN, scenario.execute().state)
        result = scenario.supervise(30)
        self.assertTrue(result.kill_switch_activated)
        self.assertIn(f"{scenario.intent.intent_id}:AMBIGUOUS_ORDER_STATE", result.actions)
        self.assertEqual(0, client.count("kt00007"))
        self.assertEqual(1, client.count("kt10000"))
        self.assertTrue(scenario.store.kill_switch_active(account_alias="main"))

    def test_crash_between_claim_and_send_is_ambiguous_on_restart(self):
        client = ScriptedClient(kt00018=[holdings()])
        scenario = Scenario(client)
        scenario.store.claim(scenario.intent.intent_id, claimed_at=NOW)  # process died here
        self.assertEqual("DUPLICATE_OR_NON_READY_ORDER_BLOCKED", scenario.execute().detail)
        self.assertTrue(scenario.supervise(30).kill_switch_activated)
        self.assertEqual(0, client.count("kt10000"))


class FillScenarios(unittest.TestCase):
    def test_partial_fill_then_timeout_cancel_then_cancelled_keeps_only_filled_quantity(self):
        client = ScriptedClient(
            kt10000=[ok(ord_no="0001234")],
            kt00007=[order_row(6, 4, "부분체결"), order_row(6, 0, "취소")],
            kt10003=[ok(ord_no="0001235", cncl_qty="4")],
            kt00018=[holdings(**{"123456": 6})],
        )
        scenario = Scenario(client)
        self.assertEqual(LiveOrderState.ACKNOWLEDGED, scenario.execute().state)

        first = scenario.supervise(181)
        self.assertFalse(first.kill_switch_activated, first.actions)
        self.assertEqual(LiveOrderState.CANCEL_ACKNOWLEDGED, scenario.state())
        self.assertEqual("4", client.calls[-2]["body"]["cncl_qty"])

        second = scenario.supervise(190)
        self.assertFalse(second.kill_switch_activated, second.actions)
        self.assertEqual(LiveOrderState.CANCELLED, scenario.state())
        self.assertEqual(6, scenario.store.program_quantity("123456"))
        self.assertEqual(1, client.count("kt10003"))
        self.assertEqual(1, client.count("kt10000"))

    def test_unfilled_order_before_timeout_is_left_alone(self):
        client = ScriptedClient(
            kt10000=[ok(ord_no="0001234")],
            kt00007=[order_row(0, 10, "접수")],
            kt00018=[holdings()],
        )
        scenario = Scenario(client)
        scenario.execute()
        result = scenario.supervise(60)
        self.assertFalse(result.kill_switch_activated, result.actions)
        self.assertEqual(LiveOrderState.ACKNOWLEDGED, scenario.state())
        self.assertEqual(0, client.count("kt10003"))

    def test_broker_rejection_after_acknowledgement_adds_no_position(self):
        client = ScriptedClient(
            kt10000=[ok(ord_no="0001234")],
            kt00007=[order_row(0, 0, "거부")],
            kt00018=[holdings()],
        )
        scenario = Scenario(client)
        scenario.execute()
        result = scenario.supervise(5)
        self.assertFalse(result.kill_switch_activated, result.actions)
        self.assertEqual(LiveOrderState.REJECTED, scenario.state())
        self.assertEqual(0, scenario.store.program_quantity("123456"))

    def test_order_found_only_on_a_later_page_is_reconciled(self):
        client = ScriptedClient(
            kt10000=[ok(ord_no="0001234")],
            kt00007=[
                Response(order_row(1, 0, "체결", number="0009999"), "Y", "PAGE-2"),
                Response(order_row(10, 0, "체결")),
            ],
            kt00018=[holdings(**{"123456": 10})],
        )
        scenario = Scenario(client)
        scenario.execute()
        result = scenario.supervise(5)
        self.assertFalse(result.kill_switch_activated, result.actions)
        self.assertEqual(LiveOrderState.FILLED, scenario.state())
        self.assertEqual(10, scenario.store.program_quantity("123456"))

    def test_order_missing_at_broker_turns_kill_switch_on_without_ledger_change(self):
        client = ScriptedClient(
            kt10000=[ok(ord_no="0001234")],
            kt00007=[ok(acnt_ord_cntr_prps_dtl=[])],
            kt00018=[holdings()],
        )
        scenario = Scenario(client)
        scenario.execute()
        result = scenario.supervise(5)
        self.assertTrue(result.kill_switch_activated)
        self.assertIn(f"{scenario.intent.intent_id}:BROKER_ORDER_NOT_FOUND", result.actions)
        self.assertEqual(LiveOrderState.ACKNOWLEDGED, scenario.state())

    def test_cumulative_fill_moving_backwards_turns_kill_switch_on(self):
        client = ScriptedClient(
            kt10000=[ok(ord_no="0001234")],
            kt00007=[order_row(6, 4, "부분체결"), order_row(3, 7, "부분체결")],
            kt00018=[holdings(**{"123456": 6})],
        )
        scenario = Scenario(client)
        scenario.execute()
        self.assertFalse(scenario.supervise(5).kill_switch_activated)
        result = scenario.supervise(10)
        self.assertTrue(result.kill_switch_activated)
        self.assertEqual(6, scenario.store.program_quantity("123456"))

    def test_cancel_response_quantity_mismatch_is_uncertain_and_not_retried(self):
        client = ScriptedClient(
            kt10000=[ok(ord_no="0001234")],
            kt00007=[order_row(6, 4, "부분체결")],
            kt10003=[ok(ord_no="0001235", cncl_qty="3")],
            kt00018=[holdings(**{"123456": 6})],
        )
        scenario = Scenario(client)
        scenario.execute()
        first = scenario.supervise(181)
        self.assertTrue(first.kill_switch_activated)
        self.assertIn(f"{scenario.intent.intent_id}:CANCEL_UNCERTAIN", first.actions)
        second = scenario.supervise(240)
        self.assertTrue(second.kill_switch_activated)
        self.assertEqual(1, client.count("kt10003"))


class AccountScenarios(unittest.TestCase):
    def test_partial_sell_reduces_only_program_quantity(self):
        client = ScriptedClient(
            kt10001=[ok(ord_no="0002000")],
            kt00007=[order_row(4, 6, "부분체결", number="0002000", ordered=10)],
            kt00018=[holdings(**{"123456": 16})],
        )
        scenario = Scenario(client, side=OrderSide.SELL, protected={"123456": 10}, program={"123456": 10})
        scenario.execute()
        result = scenario.supervise(5)
        self.assertFalse(result.kill_switch_activated, result.actions)
        self.assertEqual(6, scenario.store.program_quantity("123456"))

    def test_sell_fill_beyond_program_quantity_is_refused_and_kills(self):
        client = ScriptedClient(
            kt10001=[ok(ord_no="0002000")],
            kt00007=[order_row(10, 0, "체결", number="0002000", ordered=10)],
            kt00018=[holdings(**{"123456": 10})],
        )
        scenario = Scenario(client, side=OrderSide.SELL, protected={"123456": 10}, program={"123456": 4})
        scenario.execute()
        result = scenario.supervise(5)
        self.assertTrue(result.kill_switch_activated)
        self.assertEqual(4, scenario.store.program_quantity("123456"))

    def test_manual_sale_of_protected_holding_is_detected(self):
        client = ScriptedClient(kt00018=[holdings(**{"654321": 3})])
        scenario = Scenario(client, protected={"654321": 5})
        result = scenario.supervise(5)
        self.assertTrue(result.kill_switch_activated)
        self.assertEqual({"654321": (5, 3)}, result.holding_mismatches)

    def test_holdings_read_failure_turns_kill_switch_on(self):
        client = ScriptedClient(kt00018=[{"return_code": 1, "return_msg": "조회 실패"}])
        scenario = Scenario(client)
        result = scenario.supervise(5)
        self.assertTrue(result.kill_switch_activated)
        self.assertIn("HOLDINGS_CHECK_FAILED:RuntimeError", result.actions)


if __name__ == "__main__":
    unittest.main()
