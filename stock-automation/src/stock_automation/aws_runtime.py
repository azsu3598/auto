from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .calendar import TradingCalendar
from .config import StrategyConfig
from .dart import DartClient
from .engine import ClosingBetEngine
from .exit_engine import review_position
from .models import (
    DecisionType,
    ExitAction,
    ExitObservation,
    MarketSnapshot,
    Position,
    Session,
    StopMode,
)
from .backtest import TradingCosts
from .backtest_io import replay_case_from_dict
from .learning import (
    TuningPolicy,
    config_from_champion,
    tune_strategy,
    write_paper_champion,
)
from .medium_term import (
    MediumTermDecisionType,
    MediumTermEngine,
    MediumTermEntryAction,
    MediumTermEntryPlan,
    MediumTermExitAction,
    MediumTermPosition,
    confirm_medium_term_entry,
    review_medium_term_position,
)
from .medium_reporting import (
    render_entry_report,
    render_review_report,
    render_signal_report,
)
from .notifications import build_notifier
from .portfolio import entry_cash_flow, exit_cash_flow
from .providers.kiwoom import Catalyst, KiwoomSnapshotBuilder, _number
from .providers.reliable import KiwoomRetryPolicy, ReliableKiwoomClient
from .reporting import write_markdown_report

KST = timezone(timedelta(hours=9))


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "value"):
        return value.value
    raise TypeError(type(value).__name__)


def _snapshot_json(snapshot: MarketSnapshot) -> str:
    return json.dumps(asdict(snapshot), ensure_ascii=False, default=_json_default, sort_keys=True)


def _load_json(s3, bucket: str, key: str) -> dict[str, Any]:
    response = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def _load_optional_json(s3, bucket: str, key: str) -> dict[str, Any]:
    try:
        return _load_json(s3, bucket, key)
    except Exception as exc:
        error = getattr(exc, "response", {}).get("Error", {})
        if error.get("Code") in {"NoSuchKey", "404", "NotFound"}:
            return {}
        raise


def _verified_catalyst_overrides(
    raw: dict[str, Any], *, now: datetime
) -> dict[str, Catalyst]:
    """Accept only explicitly sourced catalysts verified on the KST run date."""
    result: dict[str, Catalyst] = {}
    run_date = now.astimezone(KST).date()
    for code, value in raw.items():
        if not isinstance(value, dict) or value.get("verified") is not True:
            continue
        if not str(value.get("source", "")).strip():
            continue
        summary = str(value.get("summary", "")).strip()
        theme = str(value.get("theme", "")).strip()
        if not summary or not theme:
            continue
        try:
            verified_at = datetime.fromisoformat(str(value.get("verified_at", "")))
            score = float(value["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if verified_at.tzinfo is None:
            continue
        if verified_at.astimezone(KST).date() != run_date:
            continue
        if verified_at.astimezone(timezone.utc) > now.astimezone(timezone.utc) + timedelta(minutes=5):
            continue
        result[str(code)] = Catalyst(
            theme=theme,
            summary=summary,
            score=max(0.0, min(1.0, score)),
            verified=True,
        )
    return result


def _dart_corporation_codes(s3, bucket: str, client: DartClient, now: datetime) -> dict[str, str]:
    key = os.getenv("DART_CORP_CODE_KEY", "config/dart/corp-code-map.json")
    cached = _load_optional_json(s3, bucket, key)
    updated_at = cached.get("updated_at")
    try:
        updated = datetime.fromisoformat(updated_at) if updated_at else None
    except (TypeError, ValueError):
        updated = None
    codes = cached.get("codes")
    if (
        updated
        and updated.tzinfo is not None
        and 0 <= (now - updated).total_seconds() <= 7 * 24 * 60 * 60
        and isinstance(codes, dict)
        and codes
    ):
        return {str(stock): str(corp) for stock, corp in codes.items()}
    result = client.corporation_codes()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(
            {"updated_at": now.isoformat(), "codes": result},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    return result


def _automatic_disclosure_overlays(
    *, s3, bucket: str, now: datetime, stock_codes: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    client = DartClient(_require("DART_API_KEY"))
    corporation_codes = _dart_corporation_codes(s3, bucket, client, now)
    overlays = client.overlays(
        stock_codes,
        corporation_codes=corporation_codes,
        checked_at=now,
    )
    prefix = os.getenv("DISCLOSURE_PREFIX", "config/disclosures")
    key = f"{prefix}/{now:%Y-%m-%d}.json"
    existing = _load_optional_json(s3, bucket, key)
    existing.update(overlays)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(existing, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    return overlays


def _market_change(client, market: str, index_code: str) -> float:
    response = client.fetch_page(
        api_id="ka20001",
        path="/api/dostk/sect",
        body={"mrkt_tp": market, "inds_cd": index_code},
    )
    body = response.body
    if body.get("return_code") not in (None, 0, "0"):
        raise RuntimeError(f"market index API error: {body.get('return_msg', '')}")
    return _number(body.get("flu_rt"), signed=True)


def _outbox_action(
    table_name: str,
    event_key: str,
    subject: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "Put": {
            "TableName": table_name,
            "Item": _ddb_json_item(
                f"OUTBOX#{event_key}",
                payload,
                event_key=event_key,
                subject=subject[:100],
                delivery_status="PENDING",
            ),
            "ConditionExpression": "attribute_not_exists(pk)",
        }
    }


def _runtime_costs() -> TradingCosts:
    return TradingCosts(
        buy_fee_bps=float(_require("BUY_FEE_BPS")),
        sell_fee_bps=float(_require("SELL_FEE_BPS")),
        sell_tax_bps=float(_require("SELL_TAX_BPS")),
    )


def _load_or_create_wallet(
    ddb, table_name: str, wallet_key: str, initial_cash: int, now: datetime
) -> int:
    if initial_cash <= 0:
        raise ValueError("initial wallet cash must be positive")
    response = ddb.get_item(
        TableName=table_name,
        Key={"pk": {"S": wallet_key}},
        ConsistentRead=True,
    )
    item = response.get("Item")
    if item:
        return int(item["available_cash"]["N"])
    try:
        ddb.put_item(
            TableName=table_name,
            Item={
                "pk": {"S": wallet_key},
                "initial_cash": {"N": str(initial_cash)},
                "available_cash": {"N": str(initial_cash)},
                "invested_principal": {"N": "0"},
                "realized_pnl": {"N": "0"},
                "fees_taxes": {"N": "0"},
                "updated_at": {"S": now.isoformat()},
            },
            ConditionExpression="attribute_not_exists(pk)",
        )
        return initial_cash
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code != "ConditionalCheckFailedException":
            raise
    response = ddb.get_item(
        TableName=table_name,
        Key={"pk": {"S": wallet_key}},
        ConsistentRead=True,
    )
    item = response.get("Item")
    if not item:
        raise RuntimeError("paper wallet initialization race could not be resolved")
    return int(item["available_cash"]["N"])


def _wallet_entry_action(
    table_name: str,
    wallet_key: str,
    *,
    price: int,
    quantity: int,
    costs: TradingCosts,
    now: datetime,
) -> dict[str, Any]:
    flow = entry_cash_flow(price, quantity, costs)
    return {
        "Update": {
            "TableName": table_name,
            "Key": {"pk": {"S": wallet_key}},
            "UpdateExpression": (
                "SET available_cash = available_cash - :debit, "
                "invested_principal = invested_principal + :principal, updated_at = :updated "
                "ADD fees_taxes :fee"
            ),
            "ConditionExpression": "available_cash >= :debit",
            "ExpressionAttributeValues": {
                ":debit": {"N": str(flow.cash_debit)},
                ":principal": {"N": str(flow.principal)},
                ":fee": {"N": str(flow.buy_fee)},
                ":updated": {"S": now.isoformat()},
            },
        }
    }


def _wallet_exit_action(
    table_name: str,
    wallet_key: str,
    *,
    entry_price: int,
    exit_price: int,
    quantity: int,
    costs: TradingCosts,
    now: datetime,
) -> tuple[dict[str, Any], Any]:
    flow = exit_cash_flow(
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        costs=costs,
    )
    action = {
        "Update": {
            "TableName": table_name,
            "Key": {"pk": {"S": wallet_key}},
            "UpdateExpression": (
                "SET available_cash = available_cash + :credit, "
                "invested_principal = invested_principal - :basis, updated_at = :updated "
                "ADD realized_pnl :pnl, fees_taxes :costs"
            ),
            "ConditionExpression": "invested_principal >= :basis",
            "ExpressionAttributeValues": {
                ":credit": {"N": str(flow.net_proceeds)},
                ":basis": {"N": str(flow.cost_basis)},
                ":pnl": {"N": str(flow.net_pnl)},
                ":costs": {"N": str(flow.sell_fee + flow.sell_tax)},
                ":updated": {"S": now.isoformat()},
            },
        }
    }
    return action, flow


def _deliver_outbox(ddb, table_name: str, notifier, event_key: str, now: datetime) -> bool:
    if notifier is None:
        return False
    key = f"OUTBOX#{event_key}"
    response = ddb.get_item(
        TableName=table_name,
        Key={"pk": {"S": key}},
        ConsistentRead=True,
    )
    item = response.get("Item")
    if not item or item.get("delivery_status", {}).get("S") == "SENT":
        return False
    notifier.send(item["subject"]["S"], json.loads(item["payload_json"]["S"]))
    ddb.update_item(
        TableName=table_name,
        Key={"pk": {"S": key}},
        UpdateExpression="SET delivery_status = :sent, sent_at = :sent_at",
        ConditionExpression="delivery_status = :pending",
        ExpressionAttributeValues={
            ":pending": {"S": "PENDING"},
            ":sent": {"S": "SENT"},
            ":sent_at": {"S": now.isoformat()},
        },
    )
    return True


def _deliver_pending_outbox(
    ddb, table_name: str, notifier, now: datetime, *, limit: int = 25
) -> dict[str, int]:
    """Best-effort drain so closed-position alerts survive pointer deletion."""
    if notifier is None:
        return {"sent": 0, "failed": 0}
    sent = 0
    failed = 0
    start_key = None
    while sent + failed < limit:
        request = {
            "TableName": table_name,
            "FilterExpression": "begins_with(pk, :prefix) AND delivery_status = :pending",
            "ExpressionAttributeValues": {
                ":prefix": {"S": "OUTBOX#"},
                ":pending": {"S": "PENDING"},
            },
            "Limit": 100,
        }
        if start_key:
            request["ExclusiveStartKey"] = start_key
        response = ddb.scan(**request)
        for item in response.get("Items", []):
            if sent + failed >= limit:
                break
            event_key = item.get("event_key", {}).get("S")
            if not event_key:
                failed += 1
                continue
            try:
                sent += int(_deliver_outbox(ddb, table_name, notifier, event_key, now))
            except Exception:
                failed += 1
        start_key = response.get("LastEvaluatedKey")
        if not start_key:
            break
    return {"sent": sent, "failed": failed}


def _save_decision(
    ddb,
    table_name: str,
    decision,
    notification=None,
    *,
    wallet_key: str | None = None,
    costs: TradingCosts | None = None,
) -> bool:
    payload = decision.to_dict()
    item = {
        "pk": decision.idempotency_key,
        "event_id": decision.event_id,
        "decision": decision.decision.value,
        "decided_at": decision.decided_at.isoformat(),
        "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
    }
    try:
        if decision.decision == DecisionType.BUY and decision.position:
            actions = [
                {
                    "Put": {
                        "TableName": table_name,
                        "Item": {key: {"S": str(value)} for key, value in item.items()},
                        "ConditionExpression": "attribute_not_exists(pk)",
                    }
                },
                {
                    "Put": {
                        "TableName": table_name,
                        "Item": {
                            "pk": {"S": f"OPEN#CLOSING_BET#{decision.session.value}"},
                            "event_id": {"S": decision.event_id},
                            "position_id": {"S": decision.position.position_id},
                            "remaining_quantity": {"N": str(decision.position.quantity)},
                            "payload_json": {
                                "S": json.dumps(decision.position.to_dict(), ensure_ascii=False, sort_keys=True)
                            },
                        },
                        "ConditionExpression": "attribute_not_exists(pk)",
                    }
                },
            ]
            if wallet_key and costs:
                actions.append(_wallet_entry_action(
                    table_name,
                    wallet_key,
                    price=decision.position.entry_price,
                    quantity=decision.position.quantity,
                    costs=costs,
                    now=decision.decided_at,
                ))
            if notification:
                actions.append(_outbox_action(
                    table_name, decision.event_id, notification[0], notification[1]
                ))
            ddb.transact_write_items(TransactItems=actions)
        else:
            ddb.put_item(
                TableName=table_name,
                Item={key: {"S": str(value)} for key, value in item.items()},
                ConditionExpression="attribute_not_exists(pk)",
            )
        return True
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return False
        raise


def _load_open_position(ddb, table_name: str, session: Session) -> tuple[Position, int] | None:
    response = ddb.get_item(
        TableName=table_name,
        Key={"pk": {"S": f"OPEN#CLOSING_BET#{session.value}"}},
        ConsistentRead=True,
    )
    item = response.get("Item")
    if not item:
        return None
    raw = json.loads(item["payload_json"]["S"])
    raw["session"] = Session(raw["session"])
    raw["stop_mode"] = StopMode(raw["stop_mode"])
    raw["entry_at"] = datetime.fromisoformat(raw["entry_at"])
    position = Position(**raw)
    remaining = int(item.get("remaining_quantity", {"N": str(position.quantity)})["N"])
    return position, remaining


def _current_observation(client, position: Position, now: datetime) -> ExitObservation:
    response = client.fetch_page(
        api_id="ka10007",
        path="/api/dostk/mrkcond",
        body={"stk_cd": position.code},
    )
    body = response.body
    if body.get("return_code") not in (None, 0, "0"):
        raise RuntimeError(f"quote API error: {body.get('return_msg', '')}")
    price = int(_number(body.get("cur_prc")))
    if price <= 0:
        raise RuntimeError("verified exit quote is unavailable")
    date_text = str(body.get("date", ""))
    time_text = str(body.get("tm", "")).zfill(6)
    observed_at = now
    if len(date_text) == 8 and len(time_text) == 6 and date_text.isdigit() and time_text.isdigit():
        observed_at = datetime.strptime(date_text + time_text, "%Y%m%d%H%M%S").replace(tzinfo=KST)
    if abs((now - observed_at).total_seconds()) > 180:
        raise RuntimeError("exit quote is stale")
    closed_below, reclaimed = _five_min_stop_confirmation(
        client=client,
        position=position,
        now=now,
    )
    return ExitObservation(
        observed_at=observed_at,
        price=price,
        five_min_closed_below_stop=closed_below,
        following_candle_reclaimed_stop=reclaimed,
    )


def _five_min_stop_confirmation(
    *, client, position: Position, now: datetime
) -> tuple[bool, bool | None]:
    """Return a two-candle soft-stop confirmation without blocking hard stops.

    A chart endpoint failure leaves the confirmation unknown.  The caller can
    still execute an emergency-price stop from the independently verified quote.
    """
    try:
        bars = KiwoomSnapshotBuilder(client).historical_five_minute_bars(
            code=position.code,
            base_date=now.strftime("%Y%m%d"),
            exchange="KRX",
        )
    except Exception:
        return False, None

    completed: list[tuple[datetime, int]] = []
    for bar in bars:
        try:
            timestamp = datetime.strptime(bar.timestamp, "%Y%m%d%H%M%S").replace(tzinfo=KST)
        except ValueError:
            continue
        if timestamp <= now:
            completed.append((timestamp, int(bar.close)))
    completed.sort(key=lambda row: row[0])
    if len(completed) < 2:
        return False, None
    previous, following = completed[-2], completed[-1]
    if (following[0] - previous[0]).total_seconds() < 5 * 60:
        return False, None
    if previous[1] >= position.stop_price:
        return False, None
    return True, following[1] >= position.stop_price


def _save_exit(
    ddb,
    table_name: str,
    session: Session,
    position: Position,
    result,
    notification=None,
    *,
    wallet_key: str | None = None,
    costs: TradingCosts | None = None,
) -> bool:
    pointer = f"OPEN#CLOSING_BET#{session.value}"
    event_key = (
        f"EXIT#{position.position_id}#{result.decided_at:%Y%m%dT%H%M%S}#"
        f"{result.action.value}"
    )
    payload = {
        "position_id": position.position_id,
        "code": position.code,
        "name": position.name,
        "action": result.action.value,
        "decided_at": result.decided_at.isoformat(),
        "execution_price": result.execution_price,
        "execution_quantity": result.execution_quantity,
        "remaining_quantity": result.remaining_quantity,
        "realized_pnl": result.realized_pnl,
        "reason_codes": list(result.reason_codes),
    }
    put_event = {
        "Put": {
            "TableName": table_name,
            "Item": {
                "pk": {"S": event_key},
                "position_id": {"S": position.position_id},
                "payload_json": {"S": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
            },
            "ConditionExpression": "attribute_not_exists(pk)",
        }
    }
    actions = [put_event]
    if result.action in {ExitAction.FULL_PROFIT, ExitAction.STOP_LOSS, ExitAction.SCHEDULED_EXIT}:
        actions.append({
            "Delete": {
                "TableName": table_name,
                "Key": {"pk": {"S": pointer}},
                "ConditionExpression": (
                    "position_id = :position_id AND remaining_quantity = :expected_quantity"
                ),
                "ExpressionAttributeValues": {
                    ":position_id": {"S": position.position_id},
                    ":expected_quantity": {"N": str(result.execution_quantity)},
                },
            }
        })
    elif result.action == ExitAction.PARTIAL_PROFIT:
        actions.append({
            "Update": {
                "TableName": table_name,
                "Key": {"pk": {"S": pointer}},
                "UpdateExpression": "SET remaining_quantity = :quantity",
                "ConditionExpression": (
                    "position_id = :position_id AND remaining_quantity = :expected_quantity"
                ),
                "ExpressionAttributeValues": {
                    ":position_id": {"S": position.position_id},
                    ":quantity": {"N": str(result.remaining_quantity)},
                    ":expected_quantity": {
                        "N": str(result.execution_quantity + result.remaining_quantity)
                    },
                },
            }
        })
    if notification and result.action != ExitAction.HOLD:
        actions.append(_outbox_action(table_name, event_key, notification[0], notification[1]))
    if (
        wallet_key
        and costs
        and result.execution_price is not None
        and result.execution_quantity > 0
    ):
        wallet_action, _ = _wallet_exit_action(
            table_name,
            wallet_key,
            entry_price=position.entry_price,
            exit_price=result.execution_price,
            quantity=result.execution_quantity,
            costs=costs,
            now=result.decided_at,
        )
        actions.append(wallet_action)
    try:
        if len(actions) == 1:
            ddb.put_item(**put_event["Put"])
        else:
            ddb.transact_write_items(TransactItems=actions)
        return True
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return False
        raise


def _publish_notification(notifier, subject: str, payload: dict[str, Any]) -> None:
    if notifier is None:
        return
    notifier.send(subject[:100], payload)


def _medium_plan_from_dict(raw: dict[str, Any]) -> MediumTermEntryPlan:
    data = dict(raw)
    data["signal_at"] = datetime.fromisoformat(data["signal_at"])
    return MediumTermEntryPlan(**data)


def _medium_position_from_dict(raw: dict[str, Any]) -> MediumTermPosition:
    data = dict(raw)
    data["signal_at"] = datetime.fromisoformat(data["signal_at"])
    data["entry_at"] = datetime.fromisoformat(data["entry_at"])
    return MediumTermPosition(**data)


def _ddb_json_item(pk: str, payload: dict[str, Any], **strings: str) -> dict[str, dict[str, str]]:
    item = {
        "pk": {"S": pk},
        "payload_json": {"S": json.dumps(payload, ensure_ascii=False, default=_json_default, sort_keys=True)},
    }
    item.update({key: {"S": value} for key, value in strings.items()})
    return item


def _load_medium_pointer(ddb, table_name: str, pointer: str):
    response = ddb.get_item(
        TableName=table_name,
        Key={"pk": {"S": pointer}},
        ConsistentRead=True,
    )
    return response.get("Item")


def _save_medium_signal(ddb, table_name: str, decision) -> bool:
    event_key = f"MEDIUM#SIGNAL#{decision.decided_at:%Y-%m-%d}"
    event = {
        "Put": {
            "TableName": table_name,
            "Item": _ddb_json_item(
                event_key,
                decision.to_dict(),
                event_id=decision.event_id,
                decision=decision.decision.value,
            ),
            "ConditionExpression": "attribute_not_exists(pk)",
        }
    }
    actions = [event]
    if decision.decision == MediumTermDecisionType.SIGNAL and decision.entry_plan:
        actions.extend([{
            "ConditionCheck": {
                "TableName": table_name,
                "Key": {"pk": {"S": "OPEN#MEDIUM_TERM"}},
                "ConditionExpression": "attribute_not_exists(pk)",
            }
        }, {
            "Put": {
                "TableName": table_name,
                "Item": _ddb_json_item(
                    "PENDING#MEDIUM_TERM",
                    asdict(decision.entry_plan),
                    plan_id=decision.entry_plan.plan_id,
                ),
                "ConditionExpression": "attribute_not_exists(pk)",
            }
        }])
    try:
        if len(actions) == 1:
            ddb.put_item(**event["Put"])
        else:
            ddb.transact_write_items(TransactItems=actions)
        return True
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return False
        raise


def _load_medium_plan(ddb, table_name: str) -> MediumTermEntryPlan | None:
    item = _load_medium_pointer(ddb, table_name, "PENDING#MEDIUM_TERM")
    if not item:
        return None
    return _medium_plan_from_dict(json.loads(item["payload_json"]["S"]))


def _load_medium_position(ddb, table_name: str) -> tuple[MediumTermPosition, int] | None:
    item = _load_medium_pointer(ddb, table_name, "OPEN#MEDIUM_TERM")
    if not item:
        return None
    position = _medium_position_from_dict(json.loads(item["payload_json"]["S"]))
    remaining = int(item.get("remaining_quantity", {"N": str(position.quantity)})["N"])
    return position, remaining


def _current_price(client, code: str, now: datetime) -> tuple[datetime, int]:
    response = client.fetch_page(
        api_id="ka10007",
        path="/api/dostk/mrkcond",
        body={"stk_cd": code},
    )
    body = response.body
    if body.get("return_code") not in (None, 0, "0"):
        raise RuntimeError(f"quote API error: {body.get('return_msg', '')}")
    price = int(_number(body.get("cur_prc")))
    if price <= 0:
        raise RuntimeError("verified medium-term quote is unavailable")
    date_text = str(body.get("date", ""))
    time_text = str(body.get("tm", "")).zfill(6)
    observed_at = now
    if len(date_text) == 8 and len(time_text) == 6 and date_text.isdigit() and time_text.isdigit():
        observed_at = datetime.strptime(date_text + time_text, "%Y%m%d%H%M%S").replace(tzinfo=KST)
    if abs((now - observed_at).total_seconds()) > 600:
        raise RuntimeError("medium-term quote is stale")
    return observed_at, price


def _disclosure_state(raw: dict[str, Any], code: str, now: datetime) -> tuple[bool, tuple[str, ...]]:
    item = raw.get(code, {})
    checked_at = item.get("checked_at")
    try:
        checked = datetime.fromisoformat(checked_at) if checked_at else None
    except (TypeError, ValueError):
        checked = None
    valid = bool(
        checked
        and checked.tzinfo is not None
        and 0 <= (now - checked).total_seconds() <= 3 * 24 * 60 * 60
    )
    flags = item.get("risk_flags", ())
    if not isinstance(flags, (list, tuple)):
        return False, ()
    return valid, tuple(str(value) for value in flags)


def _save_medium_entry(
    ddb,
    table_name: str,
    plan: MediumTermEntryPlan,
    result,
    notification=None,
    *,
    wallet_key: str | None = None,
    costs: TradingCosts | None = None,
) -> bool:
    event_key = f"MEDIUM#ENTRY#{plan.plan_id}#{result.observed_at:%Y-%m-%d}"
    payload = asdict(result)
    payload["action"] = result.action.value
    actions = [{
        "Put": {
            "TableName": table_name,
            "Item": _ddb_json_item(event_key, payload, plan_id=plan.plan_id),
            "ConditionExpression": "attribute_not_exists(pk)",
        }
    }, {
        "Delete": {
            "TableName": table_name,
            "Key": {"pk": {"S": "PENDING#MEDIUM_TERM"}},
            "ConditionExpression": "plan_id = :plan_id",
            "ExpressionAttributeValues": {":plan_id": {"S": plan.plan_id}},
        }
    }]
    if result.action == MediumTermEntryAction.ENTER and result.position:
        actions.append({
            "Put": {
                "TableName": table_name,
                "Item": {
                    **_ddb_json_item(
                        "OPEN#MEDIUM_TERM",
                        asdict(result.position),
                        position_id=result.position.position_id,
                    ),
                    "remaining_quantity": {"N": str(result.position.quantity)},
                },
                "ConditionExpression": "attribute_not_exists(pk)",
            }
        })
    if notification:
        actions.append(_outbox_action(table_name, event_key, notification[0], notification[1]))
    if (
        wallet_key
        and costs
        and result.action == MediumTermEntryAction.ENTER
        and result.position
    ):
        actions.append(_wallet_entry_action(
            table_name,
            wallet_key,
            price=result.position.entry_price,
            quantity=result.position.quantity,
            costs=costs,
            now=result.observed_at,
        ))
    try:
        ddb.transact_write_items(TransactItems=actions)
        return True
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return False
        raise


def _save_medium_review(
    ddb,
    table_name: str,
    position: MediumTermPosition,
    result,
    notification=None,
    *,
    wallet_key: str | None = None,
    costs: TradingCosts | None = None,
) -> bool:
    event_key = f"MEDIUM#REVIEW#{position.position_id}#{result.decided_at:%Y-%m-%d}"
    payload = asdict(result)
    payload["action"] = result.action.value
    event = {
        "Put": {
            "TableName": table_name,
            "Item": _ddb_json_item(event_key, payload, position_id=position.position_id),
            "ConditionExpression": "attribute_not_exists(pk)",
        }
    }
    actions = [event]
    if result.action == MediumTermExitAction.PARTIAL_PROFIT:
        actions.append({
            "Update": {
                "TableName": table_name,
                "Key": {"pk": {"S": "OPEN#MEDIUM_TERM"}},
                "UpdateExpression": "SET remaining_quantity = :quantity",
                "ConditionExpression": "position_id = :position_id",
                "ExpressionAttributeValues": {
                    ":position_id": {"S": position.position_id},
                    ":quantity": {"N": str(result.remaining_quantity)},
                },
            }
        })
    elif result.action != MediumTermExitAction.HOLD:
        actions.append({
            "Delete": {
                "TableName": table_name,
                "Key": {"pk": {"S": "OPEN#MEDIUM_TERM"}},
                "ConditionExpression": "position_id = :position_id",
                "ExpressionAttributeValues": {":position_id": {"S": position.position_id}},
            }
        })
    if notification and result.action != MediumTermExitAction.HOLD:
        actions.append(_outbox_action(table_name, event_key, notification[0], notification[1]))
    if (
        wallet_key
        and costs
        and result.execution_price is not None
        and result.execution_quantity > 0
    ):
        wallet_action, _ = _wallet_exit_action(
            table_name,
            wallet_key,
            entry_price=position.entry_price,
            exit_price=result.execution_price,
            quantity=result.execution_quantity,
            costs=costs,
            now=result.decided_at,
        )
        actions.append(wallet_action)
    try:
        if len(actions) == 1:
            ddb.put_item(**event["Put"])
        else:
            ddb.transact_write_items(TransactItems=actions)
        return True
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return False
        raise


def _put_phase_artifact(s3, bucket: str, now: datetime, phase: str, payload: dict[str, Any]) -> str:
    key = f"medium-term/{now:%Y/%m/%d}/{phase.lower()}.json"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False, default=_json_default, sort_keys=True).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    return key


def _put_phase_markdown(s3, bucket: str, now: datetime, phase: str, content: str) -> str:
    key = f"medium-term/{now:%Y/%m/%d}/{phase.lower()}.md"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="text/markdown; charset=utf-8",
    )
    return key


def _run_medium_signal(
    *, client, ddb, s3, notifier, bucket: str, table: str, now: datetime, initial_cash: int,
) -> int:
    if _load_medium_position(ddb, table) or _load_medium_plan(ddb, table):
        print(json.dumps({"status": "SKIPPED", "reason": "MEDIUM_POSITION_OR_PLAN_EXISTS"}))
        return 0
    cash = _load_or_create_wallet(
        ddb, table, "WALLET#MEDIUM_TERM", initial_cash, now
    )
    builder = KiwoomSnapshotBuilder(client)
    candidate_limit = int(os.getenv("MEDIUM_CANDIDATE_LIMIT", "40"))
    candidate_codes = builder.medium_term_candidate_codes(candidate_limit)
    overlays = _automatic_disclosure_overlays(
        s3=s3, bucket=bucket, now=now, stock_codes=candidate_codes
    )
    snapshot = builder.build_medium_term_snapshot(
        captured_at=now,
        disclosure_overlays=overlays,
        candidate_limit=candidate_limit,
    )
    decision = MediumTermEngine().evaluate(snapshot, cash=cash)
    payload = decision.to_dict()
    payload["snapshot_source"] = snapshot.source
    payload["snapshot_quote_count"] = len(snapshot.quotes)
    payload["paper_only"] = True
    _put_phase_artifact(s3, bucket, now, "MEDIUM_SIGNAL_1540", payload)
    _put_phase_markdown(
        s3,
        bucket,
        now,
        "MEDIUM_SIGNAL_1540",
        render_signal_report(snapshot, decision),
    )
    inserted = _save_medium_signal(ddb, table, decision)
    if inserted and decision.decision == MediumTermDecisionType.SIGNAL and decision.entry_plan:
        _publish_notification(notifier, f"[중기 모의신호] {decision.entry_plan.name}", payload)
    print(json.dumps({"status": "RECORDED" if inserted else "DUPLICATE_SKIPPED", **payload}, ensure_ascii=False))
    return 0


def _run_medium_entry(
    *, client, ddb, s3, notifier, calendar: TradingCalendar,
    bucket: str, table: str, now: datetime, initial_cash: int,
) -> int:
    plan = _load_medium_plan(ddb, table)
    if plan is None:
        print(json.dumps({"status": "SKIPPED", "reason": "NO_PENDING_MEDIUM_PLAN"}))
        return 0
    wallet_key = "WALLET#MEDIUM_TERM"
    cash = _load_or_create_wallet(ddb, table, wallet_key, initial_cash, now)
    costs = _runtime_costs()
    observed_at, price = _current_price(client, plan.code, now)
    overlays = _automatic_disclosure_overlays(
        s3=s3, bucket=bucket, now=now, stock_codes=(plan.code,)
    )
    checked, flags = _disclosure_state(overlays, plan.code, now)
    result = confirm_medium_term_entry(
        plan,
        observed_at=observed_at,
        observed_price=price,
        cash=cash,
        risk_flags=flags,
        disclosure_checked=checked,
        trading_days_since_signal=calendar.trading_days_between(
            plan.signal_at.date(), observed_at.date()
        ),
    )
    payload = asdict(result)
    payload["action"] = result.action.value
    payload["paper_only"] = True
    if result.action == MediumTermEntryAction.ENTER and result.position:
        cash_flow = entry_cash_flow(
            result.position.entry_price, result.position.quantity, costs
        )
        payload["buy_fee"] = cash_flow.buy_fee
        payload["cash_debit"] = cash_flow.cash_debit
        payload["available_cash_after"] = cash - cash_flow.cash_debit
    _put_phase_artifact(s3, bucket, now, "MEDIUM_ENTRY_0915", payload)
    _put_phase_markdown(
        s3,
        bucket,
        now,
        "MEDIUM_ENTRY_0915",
        render_entry_report(result),
    )
    label = "모의매수" if result.action == MediumTermEntryAction.ENTER else "진입취소"
    event_key = f"MEDIUM#ENTRY#{plan.plan_id}#{result.observed_at:%Y-%m-%d}"
    notification = (f"[중기 {label}] {plan.name}", payload) if notifier else None
    inserted = _save_medium_entry(
        ddb,
        table,
        plan,
        result,
        notification=notification,
        wallet_key=wallet_key,
        costs=costs,
    )
    if notification:
        _deliver_outbox(ddb, table, notifier, event_key, now)
    print(json.dumps({"status": "RECORDED" if inserted else "DUPLICATE_SKIPPED", **payload}, ensure_ascii=False, default=_json_default))
    return 0


def _run_medium_review(
    *, client, ddb, s3, notifier, calendar: TradingCalendar,
    bucket: str, table: str, now: datetime,
) -> int:
    loaded = _load_medium_position(ddb, table)
    if loaded is None:
        print(json.dumps({"status": "SKIPPED", "reason": "NO_OPEN_MEDIUM_POSITION"}))
        return 0
    position, remaining = loaded
    wallet_key = "WALLET#MEDIUM_TERM"
    costs = _runtime_costs()
    observed_at, price = _current_price(client, position.code, now)
    overlays = _automatic_disclosure_overlays(
        s3=s3, bucket=bucket, now=now, stock_codes=(position.code,)
    )
    checked, flags = _disclosure_state(overlays, position.code, now)
    if not checked:
        raise RuntimeError("current disclosure verification is unavailable for medium review")
    held = calendar.trading_days_between(position.entry_at.date(), observed_at.date())
    result = review_medium_term_position(
        position,
        observed_at=observed_at,
        closing_price=price,
        trading_days_held=held,
        risk_flags=flags,
        remaining_quantity=remaining,
    )
    payload = asdict(result)
    if result.execution_price is not None and result.execution_quantity > 0:
        cash_flow = exit_cash_flow(
            entry_price=position.entry_price,
            exit_price=result.execution_price,
            quantity=result.execution_quantity,
            costs=costs,
        )
        payload["gross_pnl"] = cash_flow.gross_pnl
        payload["realized_pnl"] = cash_flow.net_pnl
        payload["fees_taxes"] = cash_flow.total_costs
    payload.update({
        "action": result.action.value,
        "position_id": position.position_id,
        "stock": position.name,
        "code": position.code,
        "trading_days_held": held,
        "paper_only": True,
    })
    _put_phase_artifact(s3, bucket, now, "MEDIUM_REVIEW_1535", payload)
    _put_phase_markdown(
        s3,
        bucket,
        now,
        "MEDIUM_REVIEW_1535",
        render_review_report(
            position,
            result,
            trading_days_held=held,
            net_pnl=payload.get("realized_pnl"),
            total_costs=payload.get("fees_taxes"),
        ),
    )
    event_key = f"MEDIUM#REVIEW#{position.position_id}#{result.decided_at:%Y-%m-%d}"
    notification = None
    if notifier and result.action != MediumTermExitAction.HOLD:
        notification = (
            f"[중기 모의매도] {position.name} {result.action.value}", payload
        )
    inserted = _save_medium_review(
        ddb,
        table,
        position,
        result,
        notification=notification,
        wallet_key=wallet_key,
        costs=costs,
    )
    if notification:
        _deliver_outbox(ddb, table, notifier, event_key, now)
    print(json.dumps({"status": "RECORDED" if inserted else "DUPLICATE_SKIPPED", **payload}, ensure_ascii=False, default=_json_default))
    return 0


def _run_exit(
    *, client, ddb, s3, notifier,
    bucket: str, table: str, phase: str, now: datetime,
    costs: TradingCosts | None = None,
) -> int:
    results = []
    costs = costs or _runtime_costs()
    for session in (Session.KRX_1520, Session.NXT_1955):
        loaded = _load_open_position(ddb, table, session)
        if loaded is None:
            continue
        position, remaining = loaded
        observation = _current_observation(client, position, now)
        scheduled_exit_at = now.replace(hour=9, minute=10, second=0, microsecond=0)
        result = review_position(
            position,
            observation,
            scheduled_exit_at=scheduled_exit_at,
            remaining_quantity=remaining,
        )
        payload = {
            "session": session.value,
            "phase": phase,
            "position_id": position.position_id,
            "action": result.action.value,
            "observed_at": result.decided_at.isoformat(),
            "execution_price": result.execution_price,
            "execution_quantity": result.execution_quantity,
            "remaining_quantity": result.remaining_quantity,
            "gross_pnl": result.realized_pnl,
            "reason_codes": list(result.reason_codes),
        }
        if result.execution_price is not None and result.execution_quantity > 0:
            cash_flow = exit_cash_flow(
                entry_price=position.entry_price,
                exit_price=result.execution_price,
                quantity=result.execution_quantity,
                costs=costs,
            )
            payload["realized_pnl"] = cash_flow.net_pnl
            payload["fees_taxes"] = cash_flow.total_costs
        else:
            payload["realized_pnl"] = 0
            payload["fees_taxes"] = 0
        event_key = (
            f"EXIT#{position.position_id}#{result.decided_at:%Y%m%dT%H%M%S}#"
            f"{result.action.value}"
        )
        notification = None
        if notifier is not None and result.action != ExitAction.HOLD:
            notification = (f"[모의매매] {position.name} {result.action.value}", payload)
        inserted = _save_exit(
            ddb,
            table,
            session,
            position,
            result,
            notification=notification,
            wallet_key=f"WALLET#CLOSING_BET#{session.value}",
            costs=costs,
        )
        payload["status"] = "RECORDED" if inserted else "DUPLICATE_SKIPPED"
        if result.remaining_quantity == 0:
            try:
                replay_key = _archive_replay_case(
                    client=client,
                    s3=s3,
                    bucket=bucket,
                    session=session,
                    position=position,
                    now=now,
                )
                payload["replay_case_key"] = replay_key
            except Exception as exc:
                payload["replay_archive_error"] = f"{type(exc).__name__}: {exc}"
        s3.put_object(
            Bucket=bucket,
            Key=f"runs/{now:%Y/%m/%d}/{session.value}/{phase.lower()}-{position.position_id}.json",
            Body=json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        if notification:
            _deliver_outbox(ddb, table, notifier, event_key, now)
        results.append(payload)
    print(json.dumps({"status": "EXIT_REVIEW_COMPLETE", "results": results}, ensure_ascii=False))
    return 0


def _archive_replay_case(
    *, client, s3, bucket: str, session: Session, position: Position, now: datetime,
) -> str:
    entry_phase = "entry_nxt_1955" if session == Session.NXT_1955 else "entry_1520"
    snapshot_key = (
        f"runs/{position.entry_at:%Y/%m/%d}/{session.value}/"
        f"{entry_phase}-snapshot.json"
    )
    snapshot = _load_json(s3, bucket, snapshot_key)
    builder = KiwoomSnapshotBuilder(client)
    bars = []
    entry_exchange = "NXT" if session == Session.NXT_1955 else "KRX"
    bars.extend(
        builder.historical_five_minute_bars(
            code=position.code,
            base_date=position.entry_at.strftime("%Y%m%d"),
            exchange=entry_exchange,
        )
    )
    if now.date() != position.entry_at.date():
        bars.extend(
            builder.historical_five_minute_bars(
                code=position.code,
                base_date=now.strftime("%Y%m%d"),
                exchange="KRX",
            )
        )
    future_bars = []
    for bar in sorted(bars, key=lambda item: item.timestamp):
        observed_at = datetime.strptime(bar.timestamp, "%Y%m%d%H%M%S").replace(tzinfo=KST)
        if not (position.entry_at < observed_at <= now):
            continue
        future_bars.append(
            {
                "observed_at": observed_at.isoformat(),
                "open": int(bar.open),
                "high": int(bar.high),
                "low": int(bar.low),
                "close": int(bar.close),
                "volume": int(bar.volume),
            }
        )
    if not future_bars:
        raise RuntimeError("no five-minute replay bars were returned")
    scheduled_exit_at = now.replace(hour=9, minute=10, second=0, microsecond=0)
    case = {
        "snapshot": snapshot,
        "future_bars": future_bars,
        "scheduled_exit_at": scheduled_exit_at.isoformat(),
        "position_id": position.position_id,
        "recorded_at": now.isoformat(),
    }
    key = f"replay-cases/{session.value}/{position.entry_at:%Y-%m-%d}-{position.position_id}.json"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(case, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    return key


def _list_replay_cases(s3, bucket: str, session: Session, limit: int) -> tuple:
    prefix = f"replay-cases/{session.value}/"
    keys = []
    token = None
    while True:
        request = {"Bucket": bucket, "Prefix": prefix}
        if token:
            request["ContinuationToken"] = token
        response = s3.list_objects_v2(**request)
        keys.extend(item["Key"] for item in response.get("Contents", []) if item["Key"].endswith(".json"))
        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")
    selected = sorted(keys)[-limit:]
    return tuple(replay_case_from_dict(_load_json(s3, bucket, key)) for key in selected)


def _run_tuning(*, s3, notifier, bucket: str, now: datetime) -> int:
    costs = TradingCosts(
        buy_fee_bps=float(_require("BUY_FEE_BPS")),
        sell_fee_bps=float(_require("SELL_FEE_BPS")),
        sell_tax_bps=float(_require("SELL_TAX_BPS")),
    )
    minimum_cases = int(os.getenv("TUNING_MINIMUM_CASES", "40"))
    maximum_cases = int(os.getenv("TUNING_MAXIMUM_CASES", "250"))
    cash = int(os.getenv("STARTING_CASH", "600000"))
    outcomes = []
    for session in (Session.KRX_1520, Session.NXT_1955):
        cases = _list_replay_cases(s3, bucket, session, maximum_cases)
        base = StrategyConfig(session=session)
        champion_key = f"config/rules/{session.value}.json"
        current = _load_optional_json(s3, bucket, champion_key)
        if current:
            base = config_from_champion(base, current)
        result = tune_strategy(
            cases,
            starting_cash=cash,
            costs=costs,
            base_config=base,
            policy=TuningPolicy(minimum_cases=minimum_cases),
        )
        result_key = f"tuning/{now:%Y/%m/%d}/{session.value}.json"
        s3.put_object(
            Bucket=bucket,
            Key=result_key,
            Body=json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        outcome = {
            "session": session.value,
            "status": result.status,
            "reason": result.reason,
            "training_cases": result.training_cases,
            "validation_cases": result.validation_cases,
            "result_key": result_key,
        }
        if result.promoted:
            with tempfile.TemporaryDirectory() as directory:
                path = f"{directory}/champion.json"
                version = f"closing-{session.value.lower()}-{now:%Y%m%d}"
                write_paper_champion(path, result, base, new_rule_version=version)
                s3.put_object(
                    Bucket=bucket,
                    Key=champion_key,
                    Body=Path(path).read_bytes(),
                    ContentType="application/json; charset=utf-8",
                )
            outcome["champion_key"] = champion_key
            _publish_notification(
                notifier,
                f"[모의전략 승격] {session.value}",
                outcome,
            )
        outcomes.append(outcome)
    print(json.dumps({"status": "TUNING_COMPLETE", "outcomes": outcomes}, ensure_ascii=False))
    return 0


def run() -> int:
    """ECS entrypoint for scheduled analysis and paper execution only."""
    import boto3
    from kiwoom import get_client

    bucket = _require("PAPER_BUCKET")
    table = _require("PAPER_TABLE")
    calendar_key = _require("TRADING_CALENDAR_KEY")
    catalyst_prefix = os.getenv("CATALYST_PREFIX", "config/catalysts")
    phase = os.getenv("RUN_PHASE", "ENTRY_1520")
    session = Session.NXT_1955 if phase == "ENTRY_NXT_1955" else Session.KRX_1520
    cash = int(os.getenv("STARTING_CASH", "600000"))
    candidate_limit = int(os.getenv("CANDIDATE_LIMIT", "40"))
    now = datetime.now(KST)

    s3 = boto3.client("s3")
    ddb = boto3.client("dynamodb")
    notification_channel = os.getenv("NOTIFICATION_CHANNEL", "disabled")
    notification_secret_arn = os.getenv("NOTIFICATION_SECRET_ARN")
    notifier = build_notifier(
        notification_channel,
        boto3.client("secretsmanager"),
        notification_secret_arn,
        sns_client=boto3.client("sns"),
        sns_topic_arn=os.getenv("SNS_NOTIFICATION_TOPIC_ARN"),
    )
    outbox_result = _deliver_pending_outbox(ddb, table, notifier, now)
    if outbox_result["sent"] or outbox_result["failed"]:
        print(json.dumps({"status": "OUTBOX_DRAIN", **outbox_result}))
    if phase == "TUNE_WEEKLY":
        return _run_tuning(
            s3=s3,
            notifier=notifier,
            bucket=bucket,
            now=now,
        )

    calendar = TradingCalendar.from_dict(_load_json(s3, bucket, calendar_key))
    if not calendar.is_trading_day(now.date()):
        print(json.dumps({"status": "SKIPPED", "reason": "NOT_TRADING_DAY", "date": str(now.date())}))
        return 0

    raw_client = get_client(mode=os.getenv("KIWOOM_MODE", "demo"), timeout_seconds=20)
    client = ReliableKiwoomClient(
        raw_client,
        KiwoomRetryPolicy(
            min_interval_seconds=float(os.getenv("KIWOOM_MIN_INTERVAL_SECONDS", "0.25")),
            max_attempts=int(os.getenv("KIWOOM_READ_MAX_ATTEMPTS", "4")),
        ),
    )
    medium_cash = int(os.getenv("MEDIUM_STARTING_CASH", "600000"))
    if phase == "MEDIUM_SIGNAL_1540":
        return _run_medium_signal(
            client=client, ddb=ddb, s3=s3, notifier=notifier,
            bucket=bucket, table=table, now=now, initial_cash=medium_cash,
        )
    if phase == "MEDIUM_ENTRY_0915":
        return _run_medium_entry(
            client=client, ddb=ddb, s3=s3, notifier=notifier, calendar=calendar,
            bucket=bucket, table=table, now=now, initial_cash=medium_cash,
        )
    if phase == "MEDIUM_REVIEW_1535":
        return _run_medium_review(
            client=client, ddb=ddb, s3=s3, notifier=notifier, calendar=calendar,
            bucket=bucket, table=table, now=now,
        )
    if phase in {"EXIT_0905", "EXIT_0910"}:
        return _run_exit(
            client=client,
            ddb=ddb,
            s3=s3,
            notifier=notifier,
            bucket=bucket,
            table=table,
            phase=phase,
            now=now,
        )

    builder = KiwoomSnapshotBuilder(client)
    catalysts = builder.theme_context(session=session)
    catalyst_key = f"{catalyst_prefix}/{now:%Y-%m-%d}.json"
    raw_catalysts = _load_optional_json(s3, bucket, catalyst_key)
    verified_overrides = _verified_catalyst_overrides(raw_catalysts, now=now)
    catalysts.update(verified_overrides)

    date_prefix = f"runs/{now:%Y/%m/%d}/{session.value}"
    candidate_codes = None
    effective_candidate_limit = candidate_limit
    if phase == "ENTRY_1520":
        shortlist = _load_optional_json(s3, bucket, f"{date_prefix}/shortlist.json")
        raw_codes = shortlist.get("codes")
        if isinstance(raw_codes, list):
            candidate_codes = tuple(str(code) for code in raw_codes)
            effective_candidate_limit = len(candidate_codes)
        else:
            # A missed 15:10 task must not trigger a large burst at 15:20.
            effective_candidate_limit = min(
                candidate_limit, int(os.getenv("ENTRY_FALLBACK_CANDIDATE_LIMIT", "12"))
            )

    snapshot = builder.build(
        captured_at=now,
        session=session,
        catalysts=catalysts,
        kospi_change_pct=_market_change(client, "0", "001"),
        kosdaq_change_pct=_market_change(client, "1", "101"),
        candidate_limit=effective_candidate_limit,
        candidate_codes=candidate_codes,
    )
    s3.put_object(
        Bucket=bucket,
        Key=f"{date_prefix}/{phase.lower()}-snapshot.json",
        Body=_snapshot_json(snapshot).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    if phase == "SHORTLIST_1510":
        shortlist_limit = int(os.getenv("SHORTLIST_LIMIT", "12"))
        ranked = ClosingBetEngine(StrategyConfig(session=session)).rank_candidates(snapshot)
        shortlist_payload = {
            "captured_at": snapshot.captured_at.isoformat(),
            "session": session.value,
            "codes": [candidate.quote.code for candidate in ranked[:shortlist_limit]],
            "scores": {
                candidate.quote.code: candidate.score for candidate in ranked[:shortlist_limit]
            },
        }
        s3.put_object(
            Bucket=bucket,
            Key=f"{date_prefix}/shortlist.json",
            Body=json.dumps(shortlist_payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        print(json.dumps({
            "status": "SHORTLIST_RECORDED",
            "phase": phase,
            "quotes": len(snapshot.quotes),
            "shortlist_count": len(shortlist_payload["codes"]),
        }))
        return 0
    if phase == "SCAN_1450":
        print(json.dumps({"status": "SNAPSHOT_ONLY", "phase": phase, "quotes": len(snapshot.quotes)}))
        return 0

    if phase not in {"ENTRY_1520", "ENTRY_NXT_1955"}:
        raise RuntimeError(f"unsupported RUN_PHASE: {phase}")
    base_config = StrategyConfig(session=session)
    champion_key = os.getenv("PAPER_CHAMPION_KEY", f"config/rules/{session.value}.json")
    champion = _load_optional_json(s3, bucket, champion_key)
    active_config = config_from_champion(base_config, champion) if champion else base_config
    wallet_key = f"WALLET#CLOSING_BET#{session.value}"
    available_cash = _load_or_create_wallet(ddb, table, wallet_key, cash, now)
    costs = _runtime_costs()
    decision = ClosingBetEngine(active_config).evaluate(snapshot, cash=available_cash)
    with tempfile.TemporaryDirectory() as directory:
        report = write_markdown_report(directory, snapshot, decision)
        s3.put_object(
            Bucket=bucket,
            Key=f"{date_prefix}/final-report.md",
            Body=report.read_bytes(),
            ContentType="text/markdown; charset=utf-8",
        )
    s3.put_object(
        Bucket=bucket,
        Key=f"{date_prefix}/decision.json",
        Body=json.dumps(decision.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    notification = None
    if notifier and decision.decision == DecisionType.BUY and decision.position:
        cash_flow = entry_cash_flow(
            decision.position.entry_price, decision.position.quantity, costs
        )
        notification = (
            f"[모의매수] {decision.position.name}",
            {
                "simulation": True,
                "session": decision.session.value,
                "stock": decision.position.name,
                "code": decision.position.code,
                "entry_price": decision.position.entry_price,
                "quantity": decision.position.quantity,
                "buy_fee": cash_flow.buy_fee,
                "cash_debit": cash_flow.cash_debit,
                "available_cash_after": available_cash - cash_flow.cash_debit,
                "stop_price": decision.position.stop_price,
                "target1": decision.position.target1,
                "target2": decision.position.target2,
                "decided_at": decision.decided_at.isoformat(),
            },
        )
    inserted = _save_decision(
        ddb,
        table,
        decision,
        notification=notification,
        wallet_key=wallet_key,
        costs=costs,
    )
    if notification:
        _deliver_outbox(ddb, table, notifier, decision.event_id, now)
    print(json.dumps({"status": "RECORDED" if inserted else "DUPLICATE_SKIPPED", **decision.to_dict()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
