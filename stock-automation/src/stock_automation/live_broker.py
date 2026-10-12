from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .order_safety import (
    AccountRiskState,
    AuthorizationStatus,
    OrderAuthorization,
    OrderIntent,
    OrderSide,
    approval_challenge,
)


class KiwoomOrderClient(Protocol):
    def fetch_page(
        self,
        *,
        api_id: str,
        path: str,
        body: dict[str, str],
        cont_yn: str | None = None,
        next_key: str | None = None,
    ): ...


@dataclass(frozen=True, slots=True)
class BrokerOrder:
    intent_id: str
    broker_order_no: str
    side: OrderSide
    code: str
    quantity: int
    limit_price: int
    exchange: str
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class BrokerOrderStatus:
    broker_order_no: str
    ordered_quantity: int
    filled_quantity: int
    remaining_quantity: int
    average_fill_price: int | None
    status_text: str
    checked_at: datetime


class KiwoomLiveBroker:
    """Minimal domestic-stock live broker using documented Kiwoom REST TRs.

    Order submission is deliberately one-shot. It must receive an authorization
    produced for the exact intent and must not be wrapped by a retrying client.
    A timeout after submission is an unknown state, not permission to resend.
    """

    def __init__(self, client: KiwoomOrderClient, *, account_alias: str) -> None:
        if not account_alias.strip():
            raise ValueError("account_alias is required")
        self.client = client
        self.account_alias = account_alias.strip()

    def submit_limit_order(
        self,
        intent: OrderIntent,
        authorization: OrderAuthorization,
        *,
        submitted_at: datetime,
        exchange: str = "KRX",
    ) -> BrokerOrder:
        if submitted_at.tzinfo is None:
            raise ValueError("submitted_at must be timezone-aware")
        if authorization.status != AuthorizationStatus.AUTHORIZED:
            raise PermissionError("live order authorization was rejected")
        if authorization.intent_id != intent.intent_id:
            raise PermissionError("authorization does not match order intent")
        if authorization.intent_challenge != approval_challenge(intent):
            raise PermissionError("authorization does not match the exact order payload")
        if submitted_at < authorization.checked_at or submitted_at > intent.expires_at:
            raise PermissionError("authorized order expired before broker submission")
        if intent.account_alias != self.account_alias:
            raise PermissionError("broker account alias does not match order intent")
        exchange = exchange.upper()
        if exchange not in {"KRX", "NXT", "SOR"}:
            raise ValueError("exchange must be KRX, NXT, or SOR")

        api_id = "kt10000" if intent.side == OrderSide.BUY else "kt10001"
        # Never retry this call automatically. A network timeout can happen after
        # the broker accepted the order, so the state must be reconciled first.
        response = self.client.fetch_page(
            api_id=api_id,
            path="/api/dostk/ordr",
            body={
                "dmst_stex_tp": exchange,
                "stk_cd": intent.code,
                "ord_qty": str(intent.quantity),
                "ord_uv": str(intent.limit_price),
                "trde_tp": "0",
                "cond_uv": "",
            },
        )
        body = response.body
        _ensure_success(body)
        order_no = str(body.get("ord_no", "")).strip()
        if not order_no:
            raise RuntimeError("Kiwoom accepted response without an order number")
        return BrokerOrder(
            intent_id=intent.intent_id,
            broker_order_no=order_no,
            side=intent.side,
            code=intent.code,
            quantity=intent.quantity,
            limit_price=intent.limit_price,
            exchange=exchange,
            submitted_at=submitted_at,
        )

    def order_status(
        self,
        order: BrokerOrder,
        *,
        checked_at: datetime,
    ) -> BrokerOrderStatus:
        if checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        response = self.client.fetch_page(
            api_id="kt00007",
            path="/api/dostk/acnt",
            body={
                "ord_dt": order.submitted_at.strftime("%Y%m%d"),
                "qry_tp": "1",
                "stk_bond_tp": "1",
                "sell_tp": "2" if order.side == OrderSide.BUY else "1",
                "stk_cd": order.code,
                "fr_ord_no": "",
                "dmst_stex_tp": order.exchange,
            },
        )
        body = response.body
        _ensure_success(body)
        rows = body.get("acnt_ord_cntr_prps_dtl")
        if not isinstance(rows, list):
            rows = []
        match = next(
            (
                row for row in rows
                if isinstance(row, dict)
                and str(row.get("ord_no", "")).strip() == order.broker_order_no
            ),
            None,
        )
        if match is None:
            return BrokerOrderStatus(
                broker_order_no=order.broker_order_no,
                ordered_quantity=order.quantity,
                filled_quantity=0,
                remaining_quantity=order.quantity,
                average_fill_price=None,
                status_text="NOT_FOUND_REQUIRES_MANUAL_RECONCILIATION",
                checked_at=checked_at,
            )
        filled = _integer(match.get("cntr_qty"))
        remaining = _integer(match.get("ord_remnq"))
        ordered = _integer(match.get("ord_qty")) or order.quantity
        return BrokerOrderStatus(
            broker_order_no=order.broker_order_no,
            ordered_quantity=ordered,
            filled_quantity=filled,
            remaining_quantity=remaining,
            average_fill_price=_integer(match.get("cntr_uv")) or None,
            status_text=str(match.get("acpt_tp") or match.get("io_tp_nm") or "UNKNOWN"),
            checked_at=checked_at,
        )

    def account_risk_state(
        self,
        *,
        code: str,
        trading_date: str,
        kill_switch_active: bool,
        already_submitted_intent_ids: frozenset[str] = frozenset(),
        exchange: str = "KRX",
        observed_account_fingerprint: str | None = None,
        protected_baseline_quantity: int = 0,
        program_owned_quantity: int = 0,
        holdings_reconciled: bool = False,
    ) -> AccountRiskState:
        cash = self._single("kt00001", {"qry_tp": "3"})
        holdings = self._single(
            "kt00018", {"qry_tp": "1", "dmst_stex_tp": exchange.upper()}
        )
        pnl = self._single(
            "ka10074", {"strt_dt": trading_date, "end_dt": trading_date}
        )
        rows = holdings.get("acnt_evlt_remn_indv_tot")
        if not isinstance(rows, list):
            rows = []
        open_rows = [
            row for row in rows
            if isinstance(row, dict) and _integer(row.get("rmnd_qty")) > 0
        ]
        owned = sum(
            _integer(row.get("trde_able_qty"))
            for row in open_rows
            if str(row.get("stk_cd", "")).replace("A", "", 1).strip() == code
        )
        total_owned = sum(
            _integer(row.get("rmnd_qty"))
            for row in open_rows
            if str(row.get("stk_cd", "")).replace("A", "", 1).strip() == code
        )
        exposure = sum(_integer(row.get("evlt_amt")) for row in open_rows)
        normalized_baseline = max(0, protected_baseline_quantity)
        normalized_program = max(0, program_owned_quantity)
        reconciled = bool(
            holdings_reconciled
            and total_owned >= normalized_baseline + normalized_program
        )
        return AccountRiskState(
            account_alias=self.account_alias,
            available_cash=_integer(cash.get("ord_alow_amt")),
            current_exposure=exposure,
            realized_daily_pnl=_signed_integer(pnl.get("rlzt_pl")),
            open_positions=len(open_rows),
            owned_quantity=owned,
            kill_switch_active=kill_switch_active,
            already_submitted_intent_ids=already_submitted_intent_ids,
            observed_account_fingerprint=observed_account_fingerprint,
            protected_baseline_quantity=normalized_baseline,
            program_owned_quantity=normalized_program,
            holdings_reconciled=reconciled,
            total_owned_quantity=total_owned,
        )

    def holdings(self, *, exchange: str = "KRX") -> dict[str, int]:
        body = self._single(
            "kt00018", {"qry_tp": "1", "dmst_stex_tp": exchange.upper()}
        )
        rows = body.get("acnt_evlt_remn_indv_tot")
        if not isinstance(rows, list):
            return {}
        result: dict[str, int] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("stk_cd", "")).replace("A", "", 1).strip()
            quantity = _integer(row.get("rmnd_qty"))
            if code and quantity > 0:
                result[code] = quantity
        return result

    def _single(self, api_id: str, body: dict[str, str]) -> dict[str, Any]:
        response = self.client.fetch_page(
            api_id=api_id,
            path="/api/dostk/acnt",
            body=body,
        )
        _ensure_success(response.body)
        return response.body


def _ensure_success(body: dict[str, Any]) -> None:
    code = body.get("return_code")
    if code not in (None, 0, "0"):
        raise RuntimeError(f"Kiwoom API error {code}: {body.get('return_msg', '')}")


def _integer(value: Any) -> int:
    if value in (None, ""):
        return 0
    return abs(int(float(str(value).strip().replace(",", ""))))


def _signed_integer(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(float(str(value).strip().replace(",", "")))
