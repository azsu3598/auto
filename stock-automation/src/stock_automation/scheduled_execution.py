"""Fail closed on delayed paper schedules and bound each worker's lifetime.

Scheduler supplies SCHEDULED_AT from <aws.scheduler.scheduled-time>. It is the
original occurrence, not the attempt time. No account or credential data is logged.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping


KST = timezone(timedelta(hours=9))


class ScheduleRejected(ValueError):
    pass


@dataclass(frozen=True)
class PhaseWindow:
    hour: int
    minute: int
    latest_start_seconds: int
    runtime_seconds: int


# Finish before the existing NAT stop times (09:25 / 16:10 / Saturday 08:40).
# Entry is deliberately confined to the 15:20 minute; never invent a past fill.
PHASE_WINDOWS = {
    "SCAN_1450": PhaseWindow(14, 50, 240, 300),
    "SHORTLIST_1510": PhaseWindow(15, 10, 180, 180),
    "ENTRY_1520": PhaseWindow(15, 20, 59, 60),
    "EXIT_0905": PhaseWindow(9, 5, 120, 120),
    "EXIT_0910": PhaseWindow(9, 10, 120, 120),
    "MEDIUM_ENTRY_0915": PhaseWindow(9, 15, 120, 180),
    "MEDIUM_REVIEW_1535": PhaseWindow(15, 35, 120, 180),
    "MEDIUM_SIGNAL_1540": PhaseWindow(15, 40, 120, 180),
    "EQUITY_SNAPSHOT_1550": PhaseWindow(15, 50, 180, 180),
    "TUNE_WEEKLY": PhaseWindow(8, 0, 300, 1200),
}


def execution_deadline(env: Mapping[str, str], now: datetime) -> datetime:
    """Validate before AWS/API calls, including after a slow worker startup."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ScheduleRejected("CLOCK_TIMEZONE_REQUIRED")
    now = now.astimezone(KST)
    if env.get("KIWOOM_MODE", "demo") != "demo":
        raise ScheduleRejected("DEMO_MODE_REQUIRED")
    if env.get("LIVE_ORDER_ENABLED", "0") != "0":
        raise ScheduleRejected("LIVE_ORDERS_DISABLED_REQUIRED")
    phase = env.get("RUN_PHASE", "ENTRY_1520")
    if phase == "DAY_TRADE_ON_DEMAND":
        if env.get("SCHEDULED_AT"):
            raise ScheduleRejected("DAY_TRADE_MUST_BE_MANUAL")
        start = now.replace(hour=9, minute=10, second=0, microsecond=0)
        end = now.replace(hour=14, minute=50, second=0, microsecond=0)
        if now.weekday() >= 5 or not start <= now < end:
            raise ScheduleRejected("OUTSIDE_DAY_TRADE_WINDOW")
        return min(now + timedelta(seconds=300), end)
    window = PHASE_WINDOWS.get(phase)
    if window is None:
        raise ScheduleRejected("UNSUPPORTED_OR_DISABLED_PHASE")
    raw = env.get("SCHEDULED_AT", "")
    try:
        scheduled = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        raise ScheduleRejected("SCHEDULED_TIME_REQUIRED") from None
    if scheduled.tzinfo is None or scheduled.utcoffset() is None:
        raise ScheduleRejected("SCHEDULED_TIMEZONE_REQUIRED")
    scheduled = scheduled.astimezone(KST)
    if (scheduled.hour, scheduled.minute, scheduled.second, scheduled.microsecond) != (
        window.hour, window.minute, 0, 0
    ):
        raise ScheduleRejected("WRONG_PHASE_OCCURRENCE")
    valid_day = scheduled.weekday() == 5 if phase == "TUNE_WEEKLY" else scheduled.weekday() < 5
    if not valid_day:
        raise ScheduleRejected("WRONG_SCHEDULE_WEEKDAY")
    if now < scheduled:
        raise ScheduleRejected("EARLY_DELIVERY")
    if now > scheduled + timedelta(seconds=window.latest_start_seconds):
        raise ScheduleRejected("EXPIRED_SCHEDULE")
    return min(
        now + timedelta(seconds=window.runtime_seconds),
        scheduled + timedelta(seconds=window.latest_start_seconds + window.runtime_seconds),
    )


def _failure(status: str, reason: str) -> None:
    # Deliberately omit raw environment, exceptions, timestamps, and task identifiers.
    print(json.dumps({"status": status, "reason": reason, "paper_only": True}), flush=True)


def run_bounded() -> int:
    """Supervise a single worker; timeout kills/reaps it, with no automatic replay.

    An interrupted DynamoDB transaction may have committed. Preserve the ledger
    and reconcile it; a timeout is never evidence of NO_TRADE or of no fill.
    """
    now = datetime.now(KST)
    try:
        deadline = execution_deadline(os.environ, now)
    except ScheduleRejected as error:
        _failure("RUN_REJECTED", str(error))
        return 2
    remaining = (deadline - datetime.now(KST)).total_seconds()
    if remaining <= 0:
        _failure("RUN_REJECTED", "WORKER_START_DEADLINE")
        return 2
    try:
        result = subprocess.run(
            [sys.executable, "-m", "stock_automation.aws_runtime", "--bounded-worker"],
            timeout=remaining,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _failure("RUN_TIMED_OUT", "RECONCILE_BEFORE_REPLAY")
        return 124
    except OSError:
        _failure("RUN_FAILED", "WORKER_START_FAILED")
        return 1
    if result.returncode:
        _failure("RUN_FAILED", "WORKER_NONZERO_EXIT")
    return result.returncode if result.returncode >= 0 else 1
