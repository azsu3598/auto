from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

# Account reads must be complete. A truncated holdings list would lock an
# incomplete protected baseline, so exceeding this limit fails closed.
MAX_ACCOUNT_PAGES = 20

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


@dataclass(frozen=True, slots=True)
class BrokerCancellation:
    intent_id: str
    original_order_no: str
    cancellation_order_no: str
    cancelled_quantity: int
    requested_at: datetime


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
        rows = self._rows(
            "kt00007",
            {
                "ord_dt": order.submitted_at.strftime("%Y%m%d"),
                "qry_tp": "1",
                "stk_bond_tp": "1",
                "sell_tp": "2" if order.side == OrderSide.BUY else "1",
                "stk_cd": order.code,
                "fr_ord_no": "",
                "dmst_stex_tp": order.exchange,
            },
            "acnt_ord_cntr_prps_dtl",
        )
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

    def cancel_order(
        self,
        order: BrokerOrder,
        *,
        quantity: int,
        requested_at: datetime,
    ) -> BrokerCancellation:
        """Submit one exact cancellation attempt without automatic retry."""
        if requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")
        if quantity <= 0 or quantity > order.quantity:
            raise ValueError("cancellation quantity must be within the original order")
        response = self.client.fetch_page(
            api_id="kt10003",
            path="/api/dostk/ordr",
            body={
                "dmst_stex_tp": order.exchange,
                "orig_ord_no": order.broker_order_no,
                "stk_cd": order.code,
                "cncl_qty": str(quantity),
            },
        )
        body = response.body
        _ensure_success(body)
        cancellation_order_no = str(body.get("ord_no", "")).strip()
        cancelled_quantity = _integer(body.get("cncl_qty"))
        if not cancellation_order_no:
            raise RuntimeError("Kiwoom cancellation response has no order number")
        if cancelled_quantity and cancelled_quantity != quantity:
            raise RuntimeError("Kiwoom cancellation quantity does not match the request")
        return BrokerCancellation(
            intent_id=order.intent_id,
            original_order_no=order.broker_order_no,
            cancellation_order_no=cancellation_order_no,
            cancelled_quantity=quantity,
            requested_at=requested_at,
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
        program_positions: dict[str, int] | None = None,
    ) -> AccountRiskState:
        """Read cash, holdings and realized P&L for one order check.

        With `program_positions`, exposure and open positions count only the
        program-owned quantity, so protected user holdings do not consume the
        program limits. Without it, the whole account is counted.
        """
        cash = self._single("kt00001", {"qry_tp": "3"})
        rows = self._holding_rows(exchange)
        pnl = self._single(
            "ka10074", {"strt_dt": trading_date, "end_dt": trading_date}
        )
        open_rows = [row for row in rows if _integer(row.get("rmnd_qty")) > 0]
        owned = sum(
            _integer(row.get("trde_able_qty"))
            for row in open_rows
            if _code(row) == code
        )
        total_owned = sum(
            _integer(row.get("rmnd_qty"))
            for row in open_rows
            if _code(row) == code
        )
        if program_positions is None:
            exposure = sum(_integer(row.get("evlt_amt")) for row in open_rows)
            open_positions = len(open_rows)
        else:
            program = {
                str(item_code): int(quantity)
                for item_code, quantity in program_positions.items()
                if int(quantity) > 0
            }
            exposure = 0
            for row in open_rows:
                held = _integer(row.get("rmnd_qty"))
                quantity = min(program.get(_code(row), 0), held)
                exposure += _integer(row.get("evlt_amt")) * quantity // held
            open_positions = len(program)
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
            open_positions=open_positions,
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
        result: dict[str, int] = {}
        for row in self._holding_rows(exchange):
            code = _code(row)
            quantity = _integer(row.get("rmnd_qty"))
            if code and quantity > 0:
                result[code] = result.get(code, 0) + quantity
        return result

    def account_numbers(self) -> tuple[str, ...]:
        """Return the distinct account numbers the broker token can use (ka00001)."""
        numbers: list[str] = []
        for body in self._pages("ka00001", {}):
            number = _digits(body.get("acctNo"))
            if number and number not in numbers:
                numbers.append(number)
        return tuple(numbers)

    def _holding_rows(self, exchange: str) -> list[dict[str, Any]]:
        return self._rows(
            "kt00018",
            {"qry_tp": "1", "dmst_stex_tp": exchange.upper()},
            "acnt_evlt_remn_indv_tot",
        )

    def _rows(self, api_id: str, body: dict[str, str], key: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in self._pages(api_id, body):
            values = page.get(key)
            if isinstance(values, list):
                rows.extend(row for row in values if isinstance(row, dict))
        return rows

    def _pages(self, api_id: str, body: dict[str, str]) -> list[dict[str, Any]]:
        """Read every continuation page of one account query or fail closed."""
        pages: list[dict[str, Any]] = []
        cont_yn = None
        next_key = None
        for _ in range(MAX_ACCOUNT_PAGES):
            response = self.client.fetch_page(
                api_id=api_id,
                path="/api/dostk/acnt",
                body=body,
                cont_yn=cont_yn,
                next_key=next_key,
            )
            _ensure_success(response.body)
            pages.append(response.body)
            continuation = getattr(response, "continuation", None)
            cont_yn = getattr(continuation, "cont_yn", None)
            next_key = getattr(continuation, "next_key", None)
            if cont_yn != "Y":
                return pages
        raise RuntimeError(
            f"Kiwoom {api_id} exceeded {MAX_ACCOUNT_PAGES} pages; account read is incomplete"
        )

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


def _code(row: dict[str, Any]) -> str:
    return str(row.get("stk_cd", "")).replace("A", "", 1).strip()


def _digits(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def _integer(value: Any) -> int:
    if value in (None, ""):
        return 0
    return abs(int(float(str(value).strip().replace(",", ""))))


def _signed_integer(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(float(str(value).strip().replace(",", "")))
