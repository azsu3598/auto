"""Fictional test data. Never write this into recommendation/trade ledgers."""
from datetime import datetime, timezone, timedelta

NOW = datetime(2026, 10, 23, 14, 0, tzinfo=timezone(timedelta(hours=9)))


def quote(code="DEMO_A", **changes):
    data = {
        "code": code, "name": "가상 기업 " + code, "theme": code, "risk_group": code,
        "source": "FICTIONAL_TEST_DATA", "market": "KOSPI", "venue": "KRX", "session": "REGULAR",
        "nxt_eligible": False, "delayed": False, "observed_at": NOW.isoformat(),
        "flow_at": NOW.isoformat(), "technical_at": NOW.isoformat(), "flow_unit": "KRW",
        "technical_complete": True, "levels_tick_validated": True,
        "price": 12500, "open": 12200, "high": 12600, "low": 12000, "trading_value_krw": 48_000_000_000,
        "entry_low": 12400, "entry_high": 12500, "stop": 12200, "emergency_floor": 12100,
        "target1": 13200, "target2": 13600, "ma5": 12000, "ma20": 11900, "ma120": 11000,
        "five_min_ma20": 12400, "five_min_slope": 1, "volume_ratio": 1.8, "day_change_pct": 4,
        "institution_net_krw": 100_000_000, "program_net_krw": 200_000_000,
        "catalyst": {"verified": True, "headline": "가상 검증 촉매 · 실제 기사 아님",
                     "url": "https://example.invalid/fictional", "published_at": NOW.isoformat(),
                     "verified_at": NOW.isoformat()},
    }
    data.update(changes)
    return data


def snapshot(quotes=None, **changes):
    data = {"schema_version": 1, "purpose": "RESEARCH_ONLY", "is_sample": True,
            "captured_at": NOW.isoformat(), "scanned_at": NOW.isoformat(),
            "universe_basis": "FRESH_MARKET_SCAN", "universe_complete": True, "source": "FICTIONAL_TEST_DATA",
            "market": {"observed_at": NOW.isoformat(), "delayed": False, "kospi_pct": .4, "kosdaq_pct": .2},
            "quotes": [quote()] if quotes is None else quotes}
    data.update(changes)
    return data
