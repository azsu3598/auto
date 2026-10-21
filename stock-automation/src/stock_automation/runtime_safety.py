"""Fail-closed checks and one-attempt leases for AWS paper workers."""
from __future__ import annotations

import ipaddress
import json
import uuid
from datetime import datetime, timedelta, timezone


class RuntimeRejected(ValueError):
    pass


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise RuntimeRejected("TIMEZONE_REQUIRED")
    return result


def verify_network(*, s3, ec2, env, now, egress_probe):
    """Match the proof to this EC2 start, then verify the actual private path."""
    try:
        rows = ec2.describe_instances(InstanceIds=[env["NAT_INSTANCE_ID"]])["Reservations"]
        instances = [vm for row in rows for vm in row["Instances"]]
        if len(instances) != 1:
            raise RuntimeRejected("NAT_IDENTITY")
        vm = instances[0]
        tags = {x["Key"]: x["Value"] for x in vm.get("Tags", [])}
        if vm["State"]["Name"] != "running" or vm["SourceDestCheck"] or tags.get("Project") != "paper-fixed-egress":
            raise RuntimeRejected("NAT_NOT_READY")
        proof = json.loads(s3.get_object(Bucket=env["PAPER_BUCKET"], Key="control/network/current.json")["Body"].read())
        launch = vm["LaunchTime"]
        ready = timestamp(proof["ready_at"])
        expiry = timestamp(proof["expires_at"])
        if (proof["state"] != "READY" or proof["instance_id"] != env["NAT_INSTANCE_ID"]
                or timestamp(proof["launch_time"]) != launch
                or not launch <= ready <= now < expiry
                or expiry > launch + timedelta(minutes=120)):
            raise RuntimeRejected("STALE_OR_CLOSING_NETWORK")
        if ipaddress.IPv4Address(egress_probe().strip()) != ipaddress.IPv4Address(env["EXPECTED_EGRESS_IP"]):
            raise RuntimeRejected("EGRESS_MISMATCH")
    except RuntimeRejected:
        raise
    except Exception:
        raise RuntimeRejected("NETWORK_CHECK_FAILED") from None


def acquire_attempt(ddb, table, phase, occurrence, now):
    """Never reacquire an old attempt, even if it crashed or its TTL elapsed.

    Retain the attempt as reconciliation evidence. Ledger/outbox recovery is a
    separate human-reviewed operation, not an automatic retry of the worker.
    """
    original = timestamp(occurrence).astimezone(timezone.utc).isoformat()
    key = "CONTROL#RUN#" + phase + "#" + original
    owner = uuid.uuid4().hex
    try:
        ddb.put_item(TableName=table, Item={"pk": {"S": key}, "owner": {"S": owner},
            "status": {"S": "RUNNING"}, "started_at": {"S": now.isoformat()}},
            ConditionExpression="attribute_not_exists(pk)")
    except Exception as error:
        if getattr(error, "response", {}).get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise RuntimeRejected("DUPLICATE_OR_UNRECONCILED_ATTEMPT") from None
        raise RuntimeRejected("ATTEMPT_ACQUIRE_FAILED") from None
    return key, owner


def finish_attempt(ddb, table, attempt, status, now):
    key, owner = attempt
    ddb.update_item(TableName=table, Key={"pk": {"S": key}},
        UpdateExpression="SET #status = :status, finished_at = :at",
        ConditionExpression="#owner = :owner AND #status = :running",
        ExpressionAttributeNames={"#owner": "owner", "#status": "status"},
        ExpressionAttributeValues={":status": {"S": status}, ":at": {"S": now.isoformat()},
            ":owner": {"S": owner}, ":running": {"S": "RUNNING"}})
