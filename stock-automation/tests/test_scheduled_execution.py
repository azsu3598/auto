from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import unittest
from botocore.session import Session
from botocore.validate import validate_parameters
from datetime import datetime, timedelta
from unittest.mock import patch

from stock_automation import aws_runtime
from stock_automation.scheduled_execution import (
    KST, PHASE_WINDOWS, ScheduleRejected, execution_deadline, run_bounded,
)


def occurrence(phase="ENTRY_1520", *, date="2026-10-19"):
    window = PHASE_WINDOWS[phase]
    return datetime.fromisoformat(date).replace(hour=window.hour, minute=window.minute, tzinfo=KST)


def environment(phase="ENTRY_1520", *, date="2026-10-19"):
    return {"RUN_PHASE": phase, "SCHEDULED_AT": occurrence(phase, date=date).isoformat()}


class ScheduledExecutionTests(unittest.TestCase):
    def test_preparation_template_cannot_enable_any_app_schedule(self):
        template = (Path(__file__).resolve().parents[1] / "infra/cloudformation.yaml").read_text(encoding="utf-8")
        for name in ("CoreScheduleState", "NxtScheduleState"):
            block = re.search(r"(?ms)^  " + name + r":\n.*?(?=^  \w+:|^Conditions:)", template).group()
            self.assertIn("AllowedValues: [DISABLED]", block)

    def test_all_phases_reject_old_occurrence_and_late_delivery(self):
        for phase, window in PHASE_WINDOWS.items():
            date = "2026-10-24" if phase == "TUNE_WEEKLY" else "2026-10-19"
            scheduled = occurrence(phase, date=date)
            for delay in (window.latest_start_seconds + 0.001, 3600, 86400):
                with self.subTest(phase=phase, delay=delay), self.assertRaisesRegex(
                    ScheduleRejected, "EXPIRED_SCHEDULE"
                ):
                    execution_deadline(environment(phase, date=date), scheduled + timedelta(seconds=delay))

    def test_last_allowed_start_is_bounded_before_network_stop(self):
        for phase, window in PHASE_WINDOWS.items():
            date = "2026-10-24" if phase == "TUNE_WEEKLY" else "2026-10-19"
            scheduled = occurrence(phase, date=date)
            now = scheduled + timedelta(seconds=window.latest_start_seconds)
            deadline = execution_deadline(environment(phase, date=date), now)
            stop = scheduled.replace(
                hour=8 if phase == "TUNE_WEEKLY" else 9 if scheduled.hour == 9 else 16,
                minute=40 if phase == "TUNE_WEEKLY" else 25 if scheduled.hour == 9 else 10,
            )
            with self.subTest(phase=phase):
                self.assertEqual((deadline - now).total_seconds(), window.runtime_seconds)
                self.assertLessEqual(deadline, stop - timedelta(minutes=5))

    def test_utc_metadata_is_converted_to_kst(self):
        env = environment()
        env["SCHEDULED_AT"] = "2026-10-19T06:20:00Z"
        self.assertEqual(execution_deadline(env, occurrence()), occurrence() + timedelta(seconds=60))

    def test_missing_invalid_naive_and_wrong_phase_time_fail_closed(self):
        for value in ("", "<aws.scheduler.scheduled-time>", "invalid", "2026-10-19T15:20:00",
                      "2026-10-19T15:21:00+09:00", "2026-10-19T15:20:01+09:00"):
            with self.subTest(value=value), self.assertRaises(ScheduleRejected):
                execution_deadline({**environment(), "SCHEDULED_AT": value}, occurrence())

    def test_early_delivery_and_naive_clock_are_rejected(self):
        for now in (occurrence() - timedelta(seconds=1), occurrence().replace(tzinfo=None)):
            with self.assertRaises(ScheduleRejected):
                execution_deadline(environment(), now)

    def test_non_demo_live_and_nxt_cannot_launch(self):
        for override in ({"KIWOOM_MODE": "real"}, {"LIVE_ORDER_ENABLED": "1"},
                         {"RUN_PHASE": "ENTRY_NXT_1955"}, {"RUN_PHASE": "UNKNOWN"}):
            with self.subTest(override=override), self.assertRaises(ScheduleRejected):
                execution_deadline({**environment(), **override}, occurrence())

    def test_daily_weekend_and_weekly_wrong_day_are_rejected(self):
        for phase, date in (("ENTRY_1520", "2026-10-24"), ("TUNE_WEEKLY", "2026-10-19")):
            with self.assertRaisesRegex(ScheduleRejected, "WRONG_SCHEDULE_WEEKDAY"):
                execution_deadline(environment(phase, date=date), occurrence(phase, date=date))

    def test_day_trade_requires_explicit_manual_invocation_and_bounds_close(self):
        env = {"RUN_PHASE": "DAY_TRADE_ON_DEMAND"}
        now = occurrence().replace(hour=14, minute=49, second=50)
        self.assertEqual(execution_deadline(env, now), now + timedelta(seconds=10))
        for bad_env, bad_now in (({**env, "SCHEDULED_AT": "present"}, now),
                                 (env, now.replace(hour=9, minute=0)),
                                 (env, now.replace(minute=50))):
            with self.assertRaises(ScheduleRejected):
                execution_deadline(bad_env, bad_now)

    def test_expired_worker_exits_before_any_aws_or_ledger_calls(self):
        # A one-day-old occurrence is invalid independent of the wall clock used.
        old = (datetime.now(KST) - timedelta(days=7)).replace(hour=15, minute=20, second=0, microsecond=0)
        env = {"RUN_PHASE": "ENTRY_1520", "SCHEDULED_AT": old.isoformat()}
        with patch.dict(os.environ, env, clear=True), patch("boto3.client") as client, \
             patch.object(aws_runtime, "_save_decision") as save, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(aws_runtime.run(), 2)
            client.assert_not_called()
            save.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["status"], "RUN_REJECTED")

    def test_parent_rejects_before_starting_worker(self):
        with patch.dict(os.environ, {"SCHEDULED_AT": "invalid"}, clear=True), \
             patch("stock_automation.scheduled_execution.subprocess.run") as worker, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_bounded(), 2)
            worker.assert_not_called()

    def test_runtime_timeout_reports_reconciliation_without_replay(self):
        # Exercise the real OS timeout/kill path with a harmless sleeping child.
        real_run = subprocess.run
        def sleepy_worker(command, **kwargs):
            return real_run([command[0], "-c", "import time; time.sleep(10)"], **kwargs)
        with patch("stock_automation.scheduled_execution.execution_deadline",
                   return_value=datetime.now(KST) + timedelta(seconds=0.2)), \
             patch("stock_automation.scheduled_execution.subprocess.run", side_effect=sleepy_worker) as worker, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run_bounded(), 124)
            self.assertEqual(worker.call_count, 1)
            result = json.loads(output.getvalue())
            self.assertEqual(result["reason"], "RECONCILE_BEFORE_REPLAY")
            self.assertNotIn("NO_TRADE", output.getvalue())

    def test_worker_failure_is_reported_and_not_retried(self):
        with patch("stock_automation.scheduled_execution.execution_deadline",
                   return_value=datetime.now(KST) + timedelta(seconds=60)), \
             patch("stock_automation.scheduled_execution.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 3)) as worker, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run_bounded(), 3)
            worker.assert_called_once()
            self.assertEqual(json.loads(output.getvalue())["status"], "RUN_FAILED")

    def test_every_schedule_passes_original_occurrence_and_bounded_retry_age(self):
        template = (Path(__file__).resolve().parents[1] / "infra/cloudformation.yaml").read_text(encoding="utf-8")
        inputs = re.findall(r"Input: '(\{.*\})'", template)
        self.assertEqual(len(inputs), 11)
        for raw in inputs:
            payload = json.loads(raw)
            validate_parameters(payload, Session().get_service_model("ecs").shape_for("TaskOverride"))
            env = {x["name"]: x["value"] for x in payload["containerOverrides"][0]["environment"]}
            self.assertEqual(env["SCHEDULED_AT"], "<aws.scheduler.scheduled-time>")
        ages = [int(s) for s in re.findall(r"MaximumEventAgeInSeconds: (\d+)", template)]
        self.assertEqual(len(ages), 11)
        self.assertLessEqual(max(ages), 300)

    def test_scheduler_payload_schema_rejects_cloudformation_property_casing(self):
        from botocore.exceptions import ParamValidationError
        shape = Session().get_service_model("ecs").shape_for("TaskOverride")
        with self.assertRaises(ParamValidationError):
            validate_parameters({"ContainerOverrides": [{"Name": "stock-automation"}]}, shape)


if __name__ == "__main__":
    unittest.main()
