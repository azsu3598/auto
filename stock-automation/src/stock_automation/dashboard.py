from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib.parse import urlparse

KST = timezone(timedelta(hours=9))
STATIC_DIR = Path(__file__).with_name("dashboard_static")


class DashboardRepository(Protocol):
    def items(self) -> list[dict[str, Any]]: ...


@dataclass(slots=True)
class DynamoDashboardRepository:
    table_name: str
    client: Any

    def items(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        request: dict[str, Any] = {"TableName": self.table_name}
        while True:
            response = self.client.scan(**request)
            result.extend(_decode_item(item) for item in response.get("Items", []))
            key = response.get("LastEvaluatedKey")
            if not key:
                return result
            request["ExclusiveStartKey"] = key


@dataclass(slots=True)
class FixtureDashboardRepository:
    path: Path

    def items(self) -> list[dict[str, Any]]:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("dashboard fixture must be a JSON array")
        return payload


def dashboard_payload(
    items: Iterable[dict[str, Any]], *, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(KST)
    rows = list(items)
    wallets: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    equity_history: dict[str, list[dict[str, Any]]] = {"PAPER": [], "LIVE": []}
    pending_notifications = 0
    mode_configuration: dict[str, dict[str, bool]] = {}

    for item in rows:
        key = str(item.get("pk", ""))
        payload = _payload(item)
        if key.startswith("WALLET#"):
            wallets.append({
                "key": key,
                "strategy": _strategy_label(key),
                "available_cash": _integer(item.get("available_cash")),
                "invested_principal": _integer(item.get("invested_principal")),
                "realized_pnl": _signed_integer(item.get("realized_pnl")),
                "fees_taxes": _integer(item.get("fees_taxes")),
                "updated_at": item.get("updated_at"),
            })
        elif key.startswith("EQUITY#"):
            mode = str(item.get("mode", "PAPER")).strip().upper()
            if mode in equity_history:
                recorded_at = item.get("recorded_at") or key.rsplit("#", 1)[-1]
                total_assets = _integer(item.get("total_assets"))
                if recorded_at and total_assets > 0:
                    equity_history[mode].append({
                        "recorded_at": recorded_at,
                        "total_assets": total_assets,
                        "available_cash": _integer(item.get("available_cash")),
                        "market_value": _integer(item.get("market_value")),
                    })
        elif key.startswith("OPEN#"):
            positions.append(_position_row(key, item, payload))
        elif key.startswith("OUTBOX#"):
            if item.get("delivery_status") == "PENDING":
                pending_notifications += 1
        elif key.startswith("CONTROL#STRATEGY_MODE#"):
            strategy_id = key.removeprefix("CONTROL#STRATEGY_MODE#")
            mode_configuration[strategy_id] = {
                "paper_selected": bool(item.get("paper_enabled", False)),
                "live_selected": bool(item.get("live_enabled", False)),
            }
        elif _is_event(key):
            events.append(_event_row(key, item, payload))

    wallets.sort(key=lambda row: row["strategy"])
    positions.sort(key=lambda row: row.get("entry_at") or "", reverse=True)
    events.sort(key=lambda row: row.get("occurred_at") or "", reverse=True)
    events = events[:30]
    for history in equity_history.values():
        history.sort(key=lambda row: str(row["recorded_at"]))
        del history[:-90]

    cash = sum(row["available_cash"] for row in wallets)
    principal = sum(row["invested_principal"] for row in wallets)
    realized = sum(row["realized_pnl"] for row in wallets)
    fees = sum(row["fees_taxes"] for row in wallets)
    live_enabled = os.getenv("LIVE_ORDER_ENABLED", "") == "1"
    warnings = []
    if not wallets:
        warnings.append("아직 생성된 전략 지갑이 없습니다. AWS 모의작업 실행 전 상태입니다.")
    if pending_notifications:
        warnings.append(f"전송 대기 알림이 {pending_notifications}건 있습니다.")
    if live_enabled:
        warnings.append("위험: 이 프로세스에 실주문 환경변수가 활성화되어 있습니다.")

    return {
        "generated_at": now.isoformat(),
        "mode": "LIVE_LOCKED" if not live_enabled else "LIVE_FLAG_DETECTED",
        "system": {
            "name": "SABU Trading Console",
            "market": "KRX",
            "timezone": "Asia/Seoul",
            "data_source": "DynamoDB paper ledger",
        },
        "metrics": {
            "available_cash": cash,
            "invested_principal": principal,
            "realized_pnl": realized,
            "fees_taxes": fees,
            "open_positions": len(positions),
            "pending_notifications": pending_notifications,
        },
        "wallets": wallets,
        "positions": positions,
        "recent_events": events,
        "strategy_modes": _strategy_mode_rows(mode_configuration),
        "equity_history": equity_history,
        "schedules": _schedule_rows(),
        "safety": [
            {"label": "실주문", "state": "danger" if live_enabled else "safe", "detail": "감지됨" if live_enabled else "잠금"},
            {"label": "NXT 전략", "state": "safe", "detail": "기본 비활성"},
            {"label": "기존 잔고 보호", "state": "blocked", "detail": "코드 구현·통합검증 필요"},
            {"label": "체결 원장 대사", "state": "blocked", "detail": "키움 통합검증 필요"},
            {"label": "모의전략 분리", "state": "safe", "detail": "전략별 지갑"},
            {"label": "일손실 한도", "state": "safe", "detail": "10,000원"},
        ],
        "warnings": warnings,
        "live_transition": {
            "allowed": False,
            "reason": (
                "현재는 모의운용 단계입니다. 기존 잔고 보호와 체결 원장을 키움·AWS에서 "
                "통합 검증한 뒤 별도 사용자 승인 절차를 제공할 예정입니다."
            ),
        },
    }


def serve_dashboard(repository: DashboardRepository, *, port: int = 8765) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("dashboard port must be between 1 and 65535")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
            path = urlparse(self.path).path
            if path == "/api/dashboard":
                try:
                    self._json(200, dashboard_payload(repository.items()))
                except Exception as exc:
                    self._json(503, {
                        "error": "DASHBOARD_DATA_UNAVAILABLE",
                        "detail": type(exc).__name__,
                    })
                return
            assets = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/index.html": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            }
            asset = assets.get(path)
            if asset is None:
                self.send_error(404)
                return
            body = (STATIC_DIR / asset[0]).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", asset[1])
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"SABU Trading Console: http://127.0.0.1:{port}")
    print("Local read-only mode. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def repository_from_environment(*, fixture: str | None = None) -> DashboardRepository:
    if fixture:
        return FixtureDashboardRepository(Path(fixture))
    table = os.getenv("PAPER_TABLE", "").strip()
    if not table:
        raise RuntimeError("PAPER_TABLE is required unless --fixture is provided")
    import boto3

    return DynamoDashboardRepository(table, boto3.client("dynamodb"))


def _decode_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: _decode_value(value) for key, value in item.items()}


def _decode_value(value: Any) -> Any:
    if not isinstance(value, dict) or len(value) != 1:
        return value
    kind, raw = next(iter(value.items()))
    if kind == "S":
        return raw
    if kind == "N":
        number = float(raw)
        return int(number) if number.is_integer() else number
    if kind == "BOOL":
        return bool(raw)
    if kind == "NULL":
        return None
    if kind == "L":
        return [_decode_value(item) for item in raw]
    if kind == "M":
        return {key: _decode_value(item) for key, item in raw.items()}
    return raw


def _payload(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("payload_json")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _position_row(key: str, item: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "strategy": _strategy_label(key),
        "code": payload.get("code", ""),
        "name": payload.get("name", payload.get("code", "확인 불가")),
        "entry_price": _integer(payload.get("entry_price")),
        "quantity": _integer(payload.get("quantity")),
        "remaining_quantity": _integer(item.get("remaining_quantity", payload.get("quantity"))),
        "stop_price": _integer(payload.get("stop_price")),
        "emergency_stop": _integer(payload.get("emergency_stop")),
        "target1": _integer(payload.get("target1")),
        "target2": _integer(payload.get("target2")),
        "entry_at": payload.get("entry_at"),
        "status": payload.get("status", "OPEN"),
    }


def _event_row(key: str, item: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    decision = item.get("decision") or payload.get("decision") or payload.get("action") or "RECORDED"
    nested_position = payload.get("position")
    if not isinstance(nested_position, dict):
        nested_position = {}
    return {
        "key": key,
        "type": _event_type(key),
        "decision": str(decision),
        "stock": (
            payload.get("name")
            or payload.get("stock")
            or nested_position.get("name")
            or payload.get("code")
            or nested_position.get("code")
            or "-"
        ),
        "occurred_at": item.get("decided_at") or payload.get("decided_at") or payload.get("observed_at"),
        "price": payload.get("execution_price") or payload.get("entry_price") or payload.get("reference_price"),
        "quantity": (
            payload.get("execution_quantity")
            or payload.get("quantity")
            or nested_position.get("quantity")
        ),
        "pnl": payload.get("realized_pnl"),
        "reasons": _event_reasons(item, payload, nested_position),
    }


def _event_reasons(
    item: dict[str, Any],
    payload: dict[str, Any],
    position: dict[str, Any],
) -> list[str]:
    raw: list[Any] = []
    for source in (item.get("reason_codes"), payload.get("reason_codes")):
        if isinstance(source, (list, tuple)):
            raw.extend(source)
    selected_code = str(position.get("code") or payload.get("code") or "")
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        selected = next(
            (
                candidate for candidate in candidates
                if isinstance(candidate, dict)
                and (not selected_code or str(candidate.get("code", "")) == selected_code)
            ),
            None,
        )
        if isinstance(selected, dict) and isinstance(selected.get("reasons"), list):
            raw.extend(selected["reasons"])
    if not raw and payload.get("action"):
        raw.append(payload["action"])
    labels = []
    for reason in raw:
        code = str(reason).strip().upper()
        if not code or code == "PAPER_EXECUTION_ONLY":
            continue
        label = _REASON_LABELS.get(code, code.replace("_", " "))
        if label not in labels:
            labels.append(label)
    return labels[:5]


_REASON_LABELS = {
    "TOP_SCORE_SELECTED": "종가배팅 종합점수 1위",
    "TOP_INTRADAY_SCORE_SELECTED": "단타 종합점수 1위",
    "TOP_DAILY_CHART_SELECTED": "중기 차트점수 1위",
    "HIGH_TRADING_VALUE": "거래대금 충분",
    "VOLUME_EXPANSION": "거래량 증가",
    "INTRADAY_VOLUME_EXPANSION": "5분봉 거래량 증가",
    "STRONG_CLOSE": "고가권 마감",
    "ABOVE_5M_MA20": "5분봉 20이평 위",
    "MA20_RECLAIM": "5분봉 20이평 재돌파",
    "ABOVE_VWAP": "VWAP 위",
    "BREAKOUT_HOLD": "돌파 가격 유지",
    "FIVE_MIN_HIGHER_LOWS": "5분봉 저점 상승",
    "CATALYST_CONFIRMED": "당일 촉매 확인",
    "RSI_HEALTHY_MOMENTUM": "RSI 과열 전 상승",
    "NO_QUALIFYING_CANDIDATE": "종가배팅 기준 충족 종목 없음",
    "NO_QUALIFYING_DAY_TRADE_CANDIDATE": "단타 기준 충족 종목 없음",
    "NO_QUALIFYING_MEDIUM_TERM_CANDIDATE": "중기 기준 충족 종목 없음",
    "TARGET1_REACHED": "1차 목표가 도달",
    "TARGET2_REACHED": "2차 목표가 도달",
    "FIVE_MIN_CONFIRMATION": "5분봉 손절 확인",
    "FIVE_MIN_STOP_CONFIRMED": "5분봉 손절 확인",
    "EMERGENCY_INVALIDATION": "비상 손절 조건",
    "NEXT_SESSION_0910": "다음 거래일 09:10 청산",
    "MANDATORY_SAME_DAY_EXIT": "단타 당일 의무 청산",
    "MAXIMUM_HOLDING_PERIOD": "최대 보유기간 도달",
    "NO_EXIT_TRIGGER": "청산 조건 없음",
}


def _is_event(key: str) -> bool:
    return key.startswith(("EXIT#", "MEDIUM#", "DAY#", "202"))


def _event_type(key: str) -> str:
    if key.startswith("EXIT#"):
        return "청산"
    if key.startswith("MEDIUM#"):
        return "중기"
    if key.startswith("DAY#"):
        return "단타"
    return "종가배팅"


def _strategy_label(key: str) -> str:
    if "DAY_TRADE" in key:
        return "장중 단타"
    if "MEDIUM_TERM" in key:
        return "중기 전략"
    if "NXT" in key:
        return "NXT 종가배팅"
    if "CLOSING_BET" in key or "KRX_1520" in key:
        return "KRX 종가배팅"
    return key.replace("#", " · ")


def _integer(value: Any) -> int:
    try:
        return abs(int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _signed_integer(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _schedule_rows() -> list[dict[str, str]]:
    return [
        {"time": "요청 시", "label": "단타 모의 스캔", "strategy": "단타", "state": "manual"},
        {"time": "09:05", "label": "비상 손절·목표 점검", "strategy": "KRX", "state": "configured"},
        {"time": "09:10", "label": "잔여 수량 청산", "strategy": "KRX", "state": "configured"},
        {"time": "14:50", "label": "시장 후보 스캔", "strategy": "KRX", "state": "configured"},
        {"time": "15:10", "label": "후보 재검증", "strategy": "KRX", "state": "configured"},
        {"time": "15:20", "label": "매수 또는 NO_TRADE", "strategy": "KRX", "state": "configured"},
        {"time": "15:35", "label": "중기 포지션 검토", "strategy": "중기", "state": "configured"},
        {"time": "15:40", "label": "중기 신호 생성", "strategy": "중기", "state": "configured"},
    ]


def _strategy_mode_rows(
    configured: dict[str, dict[str, bool]],
) -> list[dict[str, Any]]:
    strategies = (
        ("CLOSING_BET", "종가배팅"),
        ("MEDIUM_TERM", "중기 전략"),
        ("DAY_TRADE", "장중 단타"),
    )
    rows = []
    for strategy_id, label in strategies:
        selected = configured.get(strategy_id, {})
        rows.append({
            "strategy": strategy_id,
            "label": label,
            "paper_selected": selected.get("paper_selected", True),
            "live_selected": selected.get("live_selected", False),
            "live_effective": False,
            "controls_locked": True,
            "detail": "인증·키움 통합검증 후 변경 가능",
        })
    return rows
