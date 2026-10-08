from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace

from stock_automation.aws_runtime import (
    _archive_replay_case,
    _automatic_disclosure_overlays,
    _deliver_outbox,
    _deliver_pending_outbox,
    _five_min_stop_confirmation,
    _load_or_create_wallet,
    _run_exit,
    _save_decision,
    _save_medium_entry,
    _save_medium_signal,
    _verified_catalyst_overrides,
)
from stock_automation.backtest import TradingCosts
from stock_automation.engine import ClosingBetEngine
from stock_automation.medium_term import MediumTermEngine, confirm_medium_term_entry
from stock_automation.models import Session
from test_engine import quote, snapshot
from test_exit_engine import position
from test_medium_term import snapshot as medium_snapshot

KST = timezone(timedelta(hours=9))


class FakeDdb:
    def __init__(self, open_position=None):
        self.transactions = []
        self.puts = []
        self.open_position = open_position
        self.items = {}

    def transact_write_items(self, **kwargs):
        self.transactions.append(kwargs)
        for action in kwargs["TransactItems"]:
            if "Put" in action:
                item = action["Put"]["Item"]
                self.items[item["pk"]["S"]] = item
            if "Delete" in action:
                self.open_position = None

    def put_item(self, **kwargs):
        self.puts.append(kwargs)
        item = kwargs["Item"]
        self.items[item["pk"]["S"]] = item

    def get_item(self, **kwargs):
        key = kwargs["Key"]["pk"]["S"]
        if key in self.items:
            return {"Item": self.items[key]}
        if key.endswith(Session.KRX_1520.value) and self.open_position:
            p = self.open_position
            return {
                "Item": {
                    "payload_json": {"S": json.dumps(p.to_dict(), ensure_ascii=False)},
                    "remaining_quantity": {"N": str(p.quantity)},
                }
            }
        return {}

    def update_item(self, **kwargs):
        key = kwargs["Key"]["pk"]["S"]
        item = self.items[key]
        item["delivery_status"] = kwargs["ExpressionAttributeValues"][":sent"]
        item["sent_at"] = kwargs["ExpressionAttributeValues"][":sent_at"]

    def scan(self, **kwargs):
        return {
            "Items": [
                item
                for key, item in self.items.items()
                if key.startswith("OUTBOX#")
                and item.get("delivery_status", {}).get("S") == "PENDING"
            ][: kwargs.get("Limit", 25)]
        }


class FakeS3:
    def __init__(self):
        self.objects = []
        self.by_key = {}

    def put_object(self, **kwargs):
        self.objects.append(kwargs)
        self.by_key[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, **kwargs):
        if kwargs["Key"] not in self.by_key:
            error = RuntimeError("missing")
            error.response = {"Error": {"Code": "NoSuchKey"}}
            raise error
        return {"Body": BytesIO(self.by_key[kwargs["Key"]])}


class FakeNotifier:
    def __init__(self):
        self.messages = []

    def send(self, subject, payload):
        self.messages.append((subject, payload))


class FakeQuoteClient:
    def fetch_page(self, **kwargs):
        return SimpleNamespace(
            body={
                "return_code": 0,
                "date": "20261007",
                "tm": "091005",
                "cur_prc": "+10200",
            }
        )


class FakeHistoricalClient:
    def fetch_page(self, **kwargs):
        date = kwargs["body"]["base_dt"]
        times = ["152500", "153000"] if date == "20261006" else ["090500", "091000"]
        rows = [
            {
                "cur_prc": "+10200",
                "trde_qty": "1000",
                "cntr_tm": f"{date}{time}",
                "open_pric": "+10100",
                "high_pric": "+10300",
                "low_pric": "+10050",
            }
            for time in times
        ]
        return SimpleNamespace(
            body={"return_code": 0, "stk_min_pole_chart_qry": rows},
            continuation=SimpleNamespace(cont_yn="N", next_key=None),
        )


class FakeStopConfirmationClient:
    def fetch_page(self, **kwargs):
        self.last_request = kwargs
        rows = [
            {
                "cur_prc": "+9650",
                "trde_qty": "1000",
                "cntr_tm": "20261007090000",
                "open_pric": "+9750",
                "high_pric": "+9800",
                "low_pric": "+9600",
            },
            {
                "cur_prc": "+9680",
                "trde_qty": "900",
                "cntr_tm": "20261007090500",
                "open_pric": "+9650",
                "high_pric": "+9690",
                "low_pric": "+9610",
            },
        ]
        return SimpleNamespace(
            body={"return_code": 0, "stk_min_pole_chart_qry": rows},
            continuation=SimpleNamespace(cont_yn="N", next_key=None),
        )


class AwsRuntimeTests(unittest.TestCase):
    def test_catalyst_override_requires_source_flag_and_same_day_verification(self):
        now = datetime(2026, 10, 8, 15, 20, tzinfo=KST)
        common = {
            "theme": "로봇",
            "summary": "공시로 확인된 계약",
            "score": 0.8,
            "verified": True,
            "source": "OpenDART: 20261008000123",
        }
        raw = {
            "VALID": {**common, "verified_at": "2026-10-08T14:55:00+09:00"},
            "NO_SOURCE": {
                **common,
                "source": "",
                "verified_at": "2026-10-08T14:55:00+09:00",
            },
            "STALE": {**common, "verified_at": "2026-10-07T15:20:00+09:00"},
            "UNVERIFIED": {
                **common,
                "verified": False,
                "verified_at": "2026-10-08T14:55:00+09:00",
            },
        }

        result = _verified_catalyst_overrides(raw, now=now)

        self.assertEqual({"VALID"}, set(result))
        self.assertTrue(result["VALID"].verified)

    def test_five_minute_stop_confirmation_uses_two_closed_bars(self):
        confirmed, reclaimed = _five_min_stop_confirmation(
            client=FakeStopConfirmationClient(),
            position=position(),
            now=datetime(2026, 10, 7, 9, 5, 5, tzinfo=KST),
        )
        self.assertTrue(confirmed)
        self.assertFalse(reclaimed)

    def test_opendart_overlays_are_automatically_cached_in_s3(self):
        class FakeDart:
            def __init__(self):
                self.map_calls = 0

            def corporation_codes(self):
                self.map_calls += 1
                return {"123456": "00123456"}

            def overlays(self, stock_codes, *, corporation_codes, checked_at):
                return {
                    stock_codes[0]: {
                        "checked_at": checked_at.isoformat(),
                        "risk_flags": [],
                        "catalyst": "사업보고서",
                        "disclosures": [],
                    }
                }

        dart = FakeDart()
        s3 = FakeS3()
        now = datetime(2026, 10, 7, 15, 40, tzinfo=KST)
        with patch.dict("os.environ", {"DART_API_KEY": "k" * 40}), patch(
            "stock_automation.aws_runtime.DartClient", return_value=dart
        ):
            first = _automatic_disclosure_overlays(
                s3=s3, bucket="paper", now=now, stock_codes=("123456",)
            )
            second = _automatic_disclosure_overlays(
                s3=s3, bucket="paper", now=now, stock_codes=("123456",)
            )
        self.assertIn("123456", first)
        self.assertEqual(first, second)
        self.assertEqual(1, dart.map_calls)
        self.assertIn("config/dart/corp-code-map.json", s3.by_key)
        self.assertIn("config/disclosures/2026-10-07.json", s3.by_key)

    def test_entry_transaction_contains_open_position_pointer(self):
        decision = ClosingBetEngine().evaluate(snapshot(quote()), cash=600_000)
        ddb = FakeDdb()
        self.assertTrue(_save_decision(ddb, "paper", decision))
        self.assertEqual(1, len(ddb.transactions))
        actions = ddb.transactions[0]["TransactItems"]
        pointer = actions[1]["Put"]["Item"]
        self.assertEqual(str(decision.position.quantity), pointer["remaining_quantity"]["N"])
        self.assertTrue(pointer["pk"]["S"].startswith("OPEN#CLOSING_BET#"))

    def test_separate_wallet_persists_available_cash(self):
        ddb = FakeDdb()
        now = datetime(2026, 10, 7, 15, 20, tzinfo=KST)
        key = "WALLET#CLOSING_BET#KRX_1520"
        self.assertEqual(600_000, _load_or_create_wallet(ddb, "paper", key, 600_000, now))
        ddb.items[key]["available_cash"] = {"N": "403573"}
        self.assertEqual(403_573, _load_or_create_wallet(ddb, "paper", key, 600_000, now))

    def test_entry_transaction_atomically_debits_strategy_wallet(self):
        decision = ClosingBetEngine().evaluate(snapshot(quote()), cash=600_000)
        ddb = FakeDdb()
        costs = TradingCosts(1.5, 1.5, 18.0)
        self.assertTrue(
            _save_decision(
                ddb,
                "paper",
                decision,
                wallet_key="WALLET#CLOSING_BET#KRX_1520",
                costs=costs,
            )
        )
        updates = [row["Update"] for row in ddb.transactions[0]["TransactItems"] if "Update" in row]
        self.assertEqual(1, len(updates))
        values = updates[0]["ExpressionAttributeValues"]
        self.assertGreater(int(values[":debit"]["N"]), decision.position.invested_amount)

    def test_0910_run_closes_verified_open_position(self):
        ddb = FakeDdb(open_position=position())
        s3 = FakeS3()
        notifier = FakeNotifier()
        result = _run_exit(
            client=FakeQuoteClient(),
            ddb=ddb,
            s3=s3,
            notifier=notifier,
            bucket="paper",
            table="paper",
            phase="EXIT_0910",
            now=datetime(2026, 10, 7, 9, 10, 10, tzinfo=KST),
            costs=TradingCosts(1.5, 1.5, 18.0),
        )
        self.assertEqual(0, result)
        self.assertIsNone(ddb.open_position)
        self.assertEqual(1, len(s3.objects))
        self.assertEqual(1, len(notifier.messages))
        payload = json.loads(s3.objects[0]["Body"].decode("utf-8"))
        self.assertEqual("SCHEDULED_EXIT", payload["action"])
        self.assertEqual(10_200, payload["execution_price"])

    def test_closed_position_archives_observed_five_minute_replay_path(self):
        s3 = FakeS3()
        p = position()
        snapshot_key = "runs/2026/10/06/KRX_1520/entry_1520-snapshot.json"
        s3.by_key[snapshot_key] = json.dumps({"captured_at": p.entry_at.isoformat()}).encode()

        key = _archive_replay_case(
            client=FakeHistoricalClient(),
            s3=s3,
            bucket="paper",
            session=Session.KRX_1520,
            position=p,
            now=datetime(2026, 10, 7, 9, 10, 10, tzinfo=KST),
        )

        self.assertEqual("replay-cases/KRX_1520/2026-10-06-POS-1.json", key)
        archived = json.loads(s3.by_key[key].decode())
        self.assertEqual(4, len(archived["future_bars"]))
        self.assertEqual("2026-10-07T09:10:00+09:00", archived["scheduled_exit_at"])

    def test_medium_signal_stores_pending_plan_separately(self):
        decision = MediumTermEngine().evaluate(medium_snapshot(), cash=600_000)
        ddb = FakeDdb()

        self.assertTrue(_save_medium_signal(ddb, "paper", decision))
        actions = ddb.transactions[0]["TransactItems"]
        self.assertEqual("PENDING#MEDIUM_TERM", actions[2]["Put"]["Item"]["pk"]["S"])
        self.assertEqual(
            decision.entry_plan.plan_id,
            actions[2]["Put"]["Item"]["plan_id"]["S"],
        )

    def test_medium_confirmed_entry_replaces_pending_with_open_pointer(self):
        decision = MediumTermEngine().evaluate(medium_snapshot(), cash=600_000)
        result = confirm_medium_term_entry(
            decision.entry_plan,
            observed_at=datetime(2026, 10, 8, 9, 15, tzinfo=KST),
            observed_price=11_100,
            cash=600_000,
        )
        ddb = FakeDdb()

        self.assertTrue(_save_medium_entry(ddb, "paper", decision.entry_plan, result))
        actions = ddb.transactions[0]["TransactItems"]
        self.assertEqual("PENDING#MEDIUM_TERM", actions[1]["Delete"]["Key"]["pk"]["S"])
        self.assertEqual("OPEN#MEDIUM_TERM", actions[2]["Put"]["Item"]["pk"]["S"])

    def test_trade_and_notification_outbox_are_atomic_and_retryable(self):
        decision = ClosingBetEngine().evaluate(snapshot(quote()), cash=600_000)
        payload = {"event_id": decision.event_id, "paper_only": True}
        ddb = FakeDdb()
        self.assertTrue(
            _save_decision(
                ddb,
                "paper",
                decision,
                notification=("모의매수", payload),
            )
        )
        outbox = ddb.items[f"OUTBOX#{decision.event_id}"]
        self.assertEqual("PENDING", outbox["delivery_status"]["S"])

        notifier = FakeNotifier()
        delivered = _deliver_outbox(
            ddb,
            "paper",
            notifier,
            decision.event_id,
            datetime(2026, 10, 7, 15, 20, tzinfo=KST),
        )
        self.assertTrue(delivered)
        self.assertEqual(1, len(notifier.messages))
        self.assertEqual("SENT", outbox["delivery_status"]["S"])
        self.assertFalse(
            _deliver_outbox(
                ddb,
                "paper",
                notifier,
                decision.event_id,
                datetime(2026, 10, 7, 15, 21, tzinfo=KST),
            )
        )
        self.assertEqual(1, len(notifier.messages))

    def test_pending_outbox_is_delivered_without_open_position_pointer(self):
        ddb = FakeDdb()
        event_key = "EXIT#CLOSED-POSITION#2026-10-07#SCHEDULED_EXIT"
        ddb.items[f"OUTBOX#{event_key}"] = {
            "pk": {"S": f"OUTBOX#{event_key}"},
            "event_key": {"S": event_key},
            "subject": {"S": "모의매도"},
            "payload_json": {"S": json.dumps({"position_id": "CLOSED-POSITION"})},
            "delivery_status": {"S": "PENDING"},
        }
        notifier = FakeNotifier()
        result = _deliver_pending_outbox(
            ddb,
            "paper",
            notifier,
            datetime(2026, 10, 7, 9, 20, tzinfo=KST),
        )
        self.assertEqual({"sent": 1, "failed": 0}, result)
        self.assertEqual(1, len(notifier.messages))
        self.assertEqual(
            "SENT", ddb.items[f"OUTBOX#{event_key}"]["delivery_status"]["S"]
        )


if __name__ == "__main__":
    unittest.main()
