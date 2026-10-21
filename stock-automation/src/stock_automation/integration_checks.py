"""Explicit paper-environment probes, isolated from wallets and positions."""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Mapping

from .doctor import DiagnosticCheck


def storage_probes(env: Mapping[str, str], client_factory: Callable | None = None) -> list[DiagnosticCheck]:
    if client_factory is None:
        import boto3
        client_factory = boto3.client
    result = []
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.json"
            path.write_text('{"paper_probe":true}', encoding="utf-8")
            if json.loads(path.read_text(encoding="utf-8"))["paper_probe"] is not True:
                raise RuntimeError("temporary file mismatch")
        result.append(DiagnosticCheck("temporary_storage", True, "write/read/cleanup passed"))
    except Exception as error:
        result.append(DiagnosticCheck("temporary_storage", False, type(error).__name__))
        return result
    probe = uuid.uuid4().hex
    payload = json.dumps({"paper_probe": True, "nonce": probe}).encode("utf-8")
    try:
        s3 = client_factory("s3")
        key = f"validation/integration/{probe}.json"
        s3.put_object(Bucket=env["PAPER_BUCKET"], Key=key, Body=payload, ContentType="application/json")
        if s3.get_object(Bucket=env["PAPER_BUCKET"], Key=key)["Body"].read() != payload:
            raise RuntimeError("validation artifact mismatch")
        result.append(DiagnosticCheck("s3_write_read", True, "dedicated validation artifact verified"))
    except Exception as error:
        result.append(DiagnosticCheck("s3_write_read", False, type(error).__name__))
    keys = [f"CONTROL#INTEGRATION_PROBE#{probe}#{i}" for i in (1, 2)]
    inserted = False
    passed = False
    cleanup_ok = True
    try:
        ddb = client_factory("dynamodb")
        def transaction(value):
            return [{"Put": {"TableName": env["PAPER_TABLE"], "Item": {
                "pk": {"S": key}, "probe_owner": {"S": probe}, "probe_value": {"S": value}},
                "ConditionExpression": "attribute_not_exists(pk)"}} for key in keys]
        ddb.transact_write_items(TransactItems=transaction("original"))
        inserted = True
        try:
            ddb.transact_write_items(TransactItems=transaction("must-not-overwrite"))
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code != "TransactionCanceledException":
                raise
            reasons = getattr(error, "response", {}).get("CancellationReasons", [])
            if len(reasons) != len(keys) or any(row.get("Code") != "ConditionalCheckFailed" for row in reasons):
                raise RuntimeError("duplicate rejection reason not verified") from None
        else:
            raise RuntimeError("Duplicate transaction unexpectedly succeeded")
        for key in keys:
            item = ddb.get_item(TableName=env["PAPER_TABLE"], Key={"pk": {"S": key}}, ConsistentRead=True)["Item"]
            if item["probe_owner"] != {"S": probe} or item["probe_value"] != {"S": "original"}:
                raise RuntimeError("transaction isolation mismatch")
        passed = True
    except Exception:
        passed = False
    finally:
        if inserted:
            for key in keys:
                try:
                    ddb.delete_item(TableName=env["PAPER_TABLE"], Key={"pk": {"S": key}},
                        ConditionExpression="probe_owner = :owner", ExpressionAttributeValues={":owner": {"S": probe}})
                except Exception:
                    cleanup_ok = False
    result.append(DiagnosticCheck("dynamodb_transaction", passed and cleanup_ok,
        "atomic write/read/duplicate rejection/cleanup passed" if passed and cleanup_ok else "probe or cleanup failed; inspect dedicated validation records"))
    return result


def notification_probe(env: Mapping[str, str], client_factory: Callable | None = None) -> DiagnosticCheck:
    if client_factory is None:
        import boto3
        client_factory = boto3.client
    from .notifications import build_notifier
    try:
        notifier = build_notifier(env.get("NOTIFICATION_CHANNEL", "disabled"),
            client_factory("secretsmanager"), env.get("NOTIFICATION_SECRET_ARN"),
            sns_client=client_factory("sns"), sns_topic_arn=env.get("SNS_NOTIFICATION_TOPIC_ARN"))
        if notifier is None:
            return DiagnosticCheck("notification_delivery", False, "notification channel unavailable")
        notifier.send("[SABU 모의환경] AWS 연결 확인", {
            "simulation": True, "kind": "INTEGRATION_PROBE", "message": "AWS 모의환경의 알림 연결을 확인했습니다."})
        return DiagnosticCheck("notification_delivery", True, "test notification delivered")
    except Exception as error:
        return DiagnosticCheck("notification_delivery", False, type(error).__name__)
