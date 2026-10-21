"""Prewarm one diagnostic container, then use the unchanged real-clock worker."""
from datetime import datetime, timedelta, timezone
import json
import os
import time


def wait_for_occurrence(env, *, clock, sleep, monotonic):
    if env.get('KIWOOM_MODE') != 'demo' or env.get('LIVE_ORDER_ENABLED') != '0' or env.get('RUN_PHASE') != 'EXIT_0905':
        raise ValueError('EMPTY_PAPER_EXIT_ONLY')
    occurrence = datetime.fromisoformat(env['SCHEDULED_AT'])
    if occurrence.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    local = occurrence.astimezone(timezone(timedelta(hours=9)))
    if local.weekday() >= 5 or (local.hour, local.minute, local.second, local.microsecond) != (9, 5, 0, 0):
        raise ValueError('REGULAR_0905_OCCURRENCE_REQUIRED')
    now = clock()
    if (occurrence - now).total_seconds() > 300:
        raise ValueError('PREWARM_TOO_EARLY')
    deadline = monotonic() + 300
    while clock() < occurrence:
        if monotonic() >= deadline:
            raise ValueError('PREWARM_BOUND_EXCEEDED')
        sleep(1)


def main():
    try:
        wait_for_occurrence(os.environ, clock=lambda: datetime.now(timezone.utc), sleep=time.sleep, monotonic=time.monotonic)
    except Exception:
        print(json.dumps({'status': 'RUN_REJECTED', 'reason': 'INVALID_PREWARM_OR_OCCURRENCE', 'paper_only': True}), flush=True)
        return 2
    from stock_automation.scheduled_execution import run_bounded
    return run_bounded()


if __name__ == '__main__':
    raise SystemExit(main())
