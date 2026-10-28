import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from stock_automation.live_broker import KiwoomLiveBroker
from stock_automation.order_safety import (
    AccountRiskState,
    LiveOrderPolicy,
    OrderSide,
    UserApproval,
    approval_challenge,
    authorize_live_order,
    build_order_intent,
)

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 7, 15, 20, tzinfo=KST)


class Response:
    def __init__(self, body):
        self.body = body
        self.continuation = SimpleNamespace(cont_yn="N", next_key=None)


class FakeClient:
    def __init__(self):
        self.calls = []

    def fetch_page(self, **kwargs):
        self.calls.append(kwargs)
        api_id = kwargs["api_id"]
        if api_id == "kt10000":
            return Response({"return_code": 0, "ord_no": "0001234", "dmst_stex_tp": "KRX"})
        if api_id == "kt00007":
            return Response({
                "return_code": 0,
                "acnt_ord_cntr_prps_dtl": [{
                    "ord_no": "0001234", "ord_qty": "10", "cntr_qty": "6",
                    "ord_remnq": "4", "cntr_uv": "10020", "acpt_tp": "부분체결",
                }],
            })
        if api_id == "kt10003":
            return Response({
                "return_code": 0,
                "ord_no": "0001235",
                "base_orig_ord_no": "0001234",
                "cncl_qty": "000000000004",
            })
        if api_id == "kt00001":
            return Response({"return_code": 0, "ord_alow_amt": "500000"})
        if api_id == "kt00018":
            return Response({
                "return_code": 0,
                "acnt_evlt_remn_indv_tot": [
                    {"stk_cd": "A123456", "rmnd_qty": "10", "trde_able_qty": "8", "evlt_amt": "101000"},
                    {"stk_cd": "654321", "rmnd_qty": "5", "trde_able_qty": "5", "evlt_amt": "70000"},
                ],
            })
        if api_id == "ka10074":
            return Response({"return_code": 0, "rlzt_pl": "-4500"})
        raise AssertionError(api_id)


def authorized_intent():
    intent = build_order_intent(
        event_id="EVENT-1",
        strategy="CLOSING_BET",
        side=OrderSide.BUY,
        code="123456",
        name="테스트",
        quantity=10,
        limit_price=10_000,
        reference_price=10_000,
        reference_at=NOW,
        created_at=NOW,
        account_alias="main",
    )
    approval = UserApproval(
        intent_id=intent.intent_id,
        challenge=approval_challenge(intent),
        approved_at=NOW,
        approved_by="USER",
    )
    state = AccountRiskState(
        account_alias="main",
        available_cash=600_000,
        current_exposure=0,
        realized_daily_pnl=0,
        open_positions=0,
        owned_quantity=0,
        kill_switch_active=False,
        observed_account_fingerprint="fingerprint-main",
        holdings_reconciled=True,
    )
    authorization = authorize_live_order(
        intent,
        approval=approval,
        state=state,
        policy=LiveOrderPolicy(
            live_order_enabled=True,
            expected_account_fingerprint="fingerprint-main",
        ),
        checked_at=NOW,
    )
    return intent, authorization


class KiwoomLiveBrokerTests(unittest.TestCase):
    def test_submits_exact_authorized_limit_buy_once(self):
        client = FakeClient()
        broker = KiwoomLiveBroker(client, account_alias="main")
        intent, authorization = authorized_intent()
        result = broker.submit_limit_order(intent, authorization, submitted_at=NOW)
        self.assertEqual("0001234", result.broker_order_no)
        self.assertEqual(1, len(client.calls))
        self.assertEqual("kt10000", client.calls[0]["api_id"])
        self.assertEqual({
            "dmst_stex_tp": "KRX", "stk_cd": "123456", "ord_qty": "10",
            "ord_uv": "10000", "trde_tp": "0", "cond_uv": "",
        }, client.calls[0]["body"])

    def test_rejected_authorization_never_calls_broker(self):
        client = FakeClient()
        broker = KiwoomLiveBroker(client, account_alias="main")
        intent, _authorization = authorized_intent()
        rejected = authorize_live_order(
            intent,
            approval=None,
            state=AccountRiskState(
                "main", 600_000, 0, 0, 0, 0, False,
                observed_account_fingerprint="fingerprint-main",
                holdings_reconciled=True,
            ),
            policy=LiveOrderPolicy(
                live_order_enabled=True,
                expected_account_fingerprint="fingerprint-main",
            ),
            checked_at=NOW,
        )
        with self.assertRaises(PermissionError):
            broker.submit_limit_order(intent, rejected, submitted_at=NOW)
        self.assertEqual([], client.calls)

    def test_reads_partial_fill_by_exact_broker_order_number(self):
        broker = KiwoomLiveBroker(FakeClient(), account_alias="main")
        intent, authorization = authorized_intent()
        order = broker.submit_limit_order(intent, authorization, submitted_at=NOW)
        status = broker.order_status(order, checked_at=NOW + timedelta(seconds=10))
        self.assertEqual(6, status.filled_quantity)
        self.assertEqual(4, status.remaining_quantity)
        self.assertEqual(10_020, status.average_fill_price)

    def test_cancels_only_the_verified_remaining_quantity_once(self):
        client = FakeClient()
        broker = KiwoomLiveBroker(client, account_alias="main")
        intent, authorization = authorized_intent()
        order = broker.submit_limit_order(intent, authorization, submitted_at=NOW)

        result = broker.cancel_order(
            order, quantity=4, requested_at=NOW + timedelta(minutes=3)
        )

        self.assertEqual("0001235", result.cancellation_order_no)
        self.assertEqual(4, result.cancelled_quantity)
        cancel_call = client.calls[-1]
        self.assertEqual("kt10003", cancel_call["api_id"])
        self.assertEqual({
            "dmst_stex_tp": "KRX",
            "orig_ord_no": "0001234",
            "stk_cd": "123456",
            "cncl_qty": "4",
        }, cancel_call["body"])

    def test_account_risk_uses_orderable_cash_holdings_and_realized_pnl(self):
        broker = KiwoomLiveBroker(FakeClient(), account_alias="main")
        state = broker.account_risk_state(
            code="123456", trading_date="20261007", kill_switch_active=True
        )
        self.assertEqual(500_000, state.available_cash)
        self.assertEqual(171_000, state.current_exposure)
        self.assertEqual(-4_500, state.realized_daily_pnl)
        self.assertEqual(2, state.open_positions)
        self.assertEqual(8, state.owned_quantity)
        self.assertEqual(10, state.total_owned_quantity)
        self.assertTrue(state.kill_switch_active)

        reconciled = broker.account_risk_state(
            code="123456",
            trading_date="20261007",
            kill_switch_active=False,
            protected_baseline_quantity=10,
            program_owned_quantity=0,
            holdings_reconciled=True,
        )
        self.assertTrue(reconciled.holdings_reconciled)

    def test_reads_existing_holdings_for_protected_baseline(self):
        broker = KiwoomLiveBroker(FakeClient(), account_alias="main")
        self.assertEqual({"123456": 10, "654321": 5}, broker.holdings())

    def test_program_positions_exclude_protected_holdings_from_limits(self):
        broker = KiwoomLiveBroker(FakeClient(), account_alias="main")
        state = broker.account_risk_state(
            code="123456",
            trading_date="20261007",
            kill_switch_active=False,
            program_positions={"123456": 4},
        )
        # 4 of 10 shares valued at 101,000 belong to the program; 654321 is protected.
        self.assertEqual(40_400, state.current_exposure)
        self.assertEqual(1, state.open_positions)

        empty = broker.account_risk_state(
            code="123456", trading_date="20261007", kill_switch_active=False,
            program_positions={},
        )
        self.assertEqual((0, 0), (empty.current_exposure, empty.open_positions))

    def test_holdings_read_every_continuation_page(self):
        client = PagedClient([
            [{"stk_cd": "A111111", "rmnd_qty": "3"}],
            [{"stk_cd": "222222", "rmnd_qty": "7"}],
        ])
        broker = KiwoomLiveBroker(client, account_alias="main")
        self.assertEqual({"111111": 3, "222222": 7}, broker.holdings())
        self.assertEqual([None, "Y"], [call["cont_yn"] for call in client.calls])
        self.assertEqual("KEY-1", client.calls[1]["next_key"])

    def test_holdings_fail_closed_when_pages_never_end(self):
        client = PagedClient([[{"stk_cd": "111111", "rmnd_qty": "1"}]] * 25)
        broker = KiwoomLiveBroker(client, account_alias="main")
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            broker.holdings()

    def test_account_numbers_are_read_from_broker_and_normalized(self):
        client = AccountClient(["1234-5678", "12345678"])
        broker = KiwoomLiveBroker(client, account_alias="main")
        self.assertEqual(("12345678",), broker.account_numbers())


class PagedClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch_page(self, **kwargs):
        index = len(self.calls)
        self.calls.append(kwargs)
        response = Response({"return_code": 0, "acnt_evlt_remn_indv_tot": self.pages[index]})
        if index + 1 < len(self.pages):
            response.continuation = SimpleNamespace(cont_yn="Y", next_key=f"KEY-{index + 1}")
        return response


class AccountClient:
    def __init__(self, numbers):
        self.numbers = numbers
        self.calls = []

    def fetch_page(self, **kwargs):
        index = len(self.calls)
        self.calls.append(kwargs)
        assert kwargs["api_id"] == "ka00001"
        response = Response({"return_code": 0, "acctNo": self.numbers[index]})
        if index + 1 < len(self.numbers):
            response.continuation = SimpleNamespace(cont_yn="Y", next_key="NEXT")
        return response


if __name__ == "__main__":
    unittest.main()
