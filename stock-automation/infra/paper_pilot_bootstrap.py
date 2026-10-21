"""Prewarm a dated paper phase without changing the production clock guards."""
from datetime import datetime, timedelta, timezone
import json
import os
import time

PHASE_TIMES = {'SCAN_1450': (14, 50), 'SHORTLIST_1510': (15, 10),
    'ENTRY_1520': (15, 20), 'EQUITY_SNAPSHOT_1550': (15, 50),
    'EXIT_0905': (9, 5), 'EXIT_0910': (9, 10)}
KST = timezone(timedelta(hours=9))


def wait_for_occurrence(env, *, clock, sleep, monotonic):
    phase = env.get('RUN_PHASE')
    if env.get('KIWOOM_MODE') != 'demo' or env.get('LIVE_ORDER_ENABLED') != '0' or phase not in PHASE_TIMES:
        raise ValueError('DATED_PAPER_PHASE_ONLY')
    occurrence = datetime.fromisoformat(env['SCHEDULED_AT'])
    dispatch = datetime.fromisoformat(env['DISPATCHED_AT'])
    if occurrence.tzinfo is None or dispatch.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    local = occurrence.astimezone(KST)
    day = env['PILOT_EXIT_DATE'] if phase.startswith('EXIT_') else env['PILOT_ENTRY_DATE']
    if (local.date().isoformat() != day or local.weekday() >= 5
            or (local.hour, local.minute) != PHASE_TIMES[phase] or local.second or local.microsecond
            or not 120 <= (occurrence - dispatch).total_seconds() <= 180):
        raise ValueError('WRONG_PILOT_OCCURRENCE')
    now = clock()
    if now < dispatch or not -120 <= (occurrence - now).total_seconds() <= 300:
        raise ValueError('OUTSIDE_PREWARM_WINDOW')
    deadline = monotonic() + 300
    while clock() < occurrence:
        if monotonic() >= deadline:
            raise ValueError('PREWARM_BOUND_EXCEEDED')
        sleep(1)
    # run_bounded independently enforces the original, phase-specific late limit.


def main():
    try:
        wait_for_occurrence(os.environ, clock=lambda: datetime.now(timezone.utc), sleep=time.sleep, monotonic=time.monotonic)
    except Exception:
        print(json.dumps({'status': 'RUN_REJECTED', 'reason': 'INVALID_PILOT_OCCURRENCE', 'paper_only': True}), flush=True)
        return 2
    from stock_automation.scheduled_execution import run_bounded
    return run_bounded()


if __name__ == '__main__':
    raise SystemExit(main())
