"""Offline guards for the five-session template and local deployment plan.

No AWS clients, credentials, schedule updates, or broker calls are used here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import fnmatch
import importlib.util
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
UTC_TIMESTAMP_PATTERN = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z"
KST = timezone(timedelta(hours=9))
PHASES = {
    "GATE", "START_PM", "SCAN_1450", "SHORTLIST_1510", "ENTRY_1520",
    "EQUITY_SNAPSHOT_1550", "STOP_PM", "REPORT_PM", "START_AM",
    "EXIT_0905", "EXIT_0910", "STOP_AM", "REPORT_AM", "FALLBACK_PM", "FALLBACK_AM",
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def validate_schedule_bounds(parameters, sessions):
    """Validate actual UTC inputs; cover every event but no extra local dates."""
    # Keep in step with infra/paper_batch.py ALLOWED_SESSION_COUNTS.
    require(isinstance(sessions, list) and len(sessions) in (2, 3, 5), "APPROVED_SESSION_COUNT_REQUIRED")
    for window, field, first_clock, last_clock in (
        ("Pm", "entry_date", "09:45", "16:20"),
        ("Am", "exit_date", "08:55", "09:40"),
    ):
        dates = [datetime.strptime(slot[field], "%Y-%m-%d").date() for slot in sessions]
        require(dates == sorted(set(dates)), "SESSION_DATES_NOT_ORDERED")
        bounds = []
        for suffix in ("Start", "End"):
            raw = parameters.get(window + suffix)
            require(isinstance(raw, str) and re.fullmatch(UTC_TIMESTAMP_PATTERN, raw) is not None,
                    "UTC_MILLISECOND_TIMESTAMP_REQUIRED")
            try:
                bounds.append(datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc))
            except ValueError:
                raise ValueError("INVALID_SCHEDULE_TIMESTAMP") from None
        start, end = bounds
        require(start < end, "SCHEDULE_BOUNDS_REVERSED")
        require(start.astimezone(KST).date() == dates[0] and end.astimezone(KST).date() == dates[-1],
                "SCHEDULE_OUTSIDE_APPROVED_DATES")
        first = datetime.fromisoformat(dates[0].isoformat() + "T" + first_clock + ":00+09:00")
        last = datetime.fromisoformat(dates[-1].isoformat() + "T" + last_clock + ":00+09:00")
        require(start <= first and end >= last, "SCHEDULE_DOES_NOT_COVER_ALL_EVENTS")


def validate_batch_template(template):
    """Fail closed if the generated batch drops its bounded-paper safeguards."""
    parameters, resources = template["Parameters"], template["Resources"]
    require(parameters["PilotState"]["Default"] == "DISABLED", "BATCH_DEFAULT_MUST_BE_DISABLED")
    for name in ("PmStart", "PmEnd", "AmStart", "AmEnd"):
        require(parameters[name].get("Type") == "String"
                and parameters[name].get("AllowedPattern") == UTC_TIMESTAMP_PATTERN,
                "BATCH_TIMESTAMP_CONSTRAINT_MISSING")
    schedules = [r["Properties"] for r in resources.values() if r["Type"] == "AWS::Scheduler::Schedule"]
    require(len(schedules) == 15, "EXACT_FIFTEEN_BATCH_SCHEDULES_REQUIRED")
    require({s["Name"].removeprefix("stock-paper-batch-").upper().replace("-", "_")
             for s in schedules} == PHASES, "BATCH_SCHEDULE_SET_CHANGED")
    for schedule in schedules:
        phase = schedule["Name"].removeprefix("stock-paper-batch-").upper().replace("-", "_")
        window = "Am" if phase.endswith("_AM") or phase.startswith("EXIT_") else "Pm"
        require(schedule["State"] == {"Ref": "PilotState"}
                and schedule["StartDate"] == {"Ref": window + "Start"}
                and schedule["EndDate"] == {"Ref": window + "End"}
                and schedule["ScheduleExpressionTimezone"] == "Asia/Seoul"
                and schedule["FlexibleTimeWindow"] == {"Mode": "OFF"}
                and schedule["Target"]["RetryPolicy"] == {
                    "MaximumEventAgeInSeconds": 60, "MaximumRetryAttempts": 0},
                "BATCH_SCHEDULE_GUARD_CHANGED")
        if phase.startswith("FALLBACK_"):
            require(schedule["Target"]["Arn"] == {
                "Fn::Sub": "arn:${AWS::Partition}:scheduler:::aws-sdk:ec2:stopInstances"},
                "BATCH_INDEPENDENT_STOP_CHANGED")
    require(not any(r["Type"] in {"AWS::EC2::Instance", "AWS::EC2::NatGateway",
                                 "AWS::ECS::Service", "AWS::RDS::DBInstance"} for r in resources.values()),
            "BATCH_ALWAYS_ON_RESOURCE_FORBIDDEN")
    policies = [resources["Boundary"]["Properties"]["PolicyDocument"],
                resources["PilotRole"]["Properties"]["Policies"][0]["PolicyDocument"]]
    forbidden = {"scheduler:UpdateSchedule", "dynamodb:PutItem", "dynamodb:UpdateItem",
                 "dynamodb:DeleteItem", "s3:DeleteObject", "ec2:StartInstances"}
    for policy, limit in zip(policies, (6144, 10240)):
        actions = {a for s in policy["Statement"] for a in
                   ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])}
        require(not any(fnmatch.fnmatchcase(action.lower(), pattern.lower())
                        for action in forbidden for pattern in actions),
                "BATCH_MUTATION_PERMISSION_FORBIDDEN")
        require(len(json.dumps(policy, separators=(",", ":"))) < limit, "BATCH_IAM_POLICY_TOO_LARGE")
    container = resources["PilotTask"]["Properties"]["ContainerDefinitions"][0]
    env = {item["Name"]: item["Value"] for item in container["Environment"]}
    require(env.get("KIWOOM_MODE") == "demo" and env.get("LIVE_ORDER_ENABLED") == "0",
            "BATCH_DEMO_LIVE0_REQUIRED")
    require(container["User"] == "65534:65534" and container["ReadonlyRootFilesystem"] is True
            and container["LinuxParameters"]["Capabilities"]["Drop"] == ["ALL"],
            "BATCH_CONTAINER_ISOLATION_CHANGED")


def validate_operational_plan(document):
    """Reuse the engine's calendar/identity guards, then check deployment bounds."""
    batch = document["batch_plan"]
    require(document.get("stack_name") == "stock-automation-paper-batch-v2"
            and document["parameters"].get("PilotId") == batch.get("batch_id"),
            "APPROVED_BATCH_IDENTITY_REQUIRED")
    previous = sys.modules.get("paper_pilot")
    try:
        def load(name):
            spec = importlib.util.spec_from_file_location(name, ROOT / "infra" / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        sys.modules["paper_pilot"] = load("paper_pilot")
        load("paper_batch").validate_batch(batch)
    finally:
        if previous is None:
            sys.modules.pop("paper_pilot", None)
        else:
            sys.modules["paper_pilot"] = previous
    validate_schedule_bounds(document["parameters"], batch["sessions"])


def main():
    parser = argparse.ArgumentParser(description="Offline batch plan/date validation; no AWS calls")
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate_operational_plan(json.loads(args.plan.read_text(encoding="utf-8-sig")))
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        # Never print local plan contents, account identity, or endpoints.
        code = str(error) if isinstance(error, ValueError) and re.fullmatch(r"[A-Z0-9_]+", str(error)) else type(error).__name__
        print("BATCH_PLAN_VALIDATION_FAILED=" + code)
        return 1
    print("BATCH_PLAN_AND_SCHEDULE_BOUNDS: PASS; NO_AWS_CALLS; NO_MUTATIONS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
