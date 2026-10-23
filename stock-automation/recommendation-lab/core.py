"""Research-only scoring. No imports from the execution application or SDKs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from urllib.parse import urlsplit

RULE_VERSION = "recommendation-lab-0.1-UNVALIDATED"
KST = timezone(timedelta(hours=9))


class DataBlocked(ValueError):
    """Required market evidence is malformed, stale or unverified."""


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise DataBlocked("INVALID_TIMESTAMP") from exc
    if result.tzinfo is None:
        raise DataBlocked("TIMEZONE_REQUIRED")
    return result


def fresh(value, now, seconds=90):
    observed = timestamp(value)
    age = (now - observed).total_seconds()
    if age < -2 or age > seconds:
        raise DataBlocked("STALE_OR_FUTURE_DATA")
    return observed


def number(data, key, *, positive=False, integer=False):
    value = data.get(key)
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (positive and value <= 0)
            or (integer and not isinstance(value, int))):
        raise DataBlocked("INVALID_NUMBER:" + key)
    return value


def label(data, key, maximum=200):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise DataBlocked("INVALID_TEXT:" + key)
    return value


def validate_quote(q, now, sample):
    if not isinstance(q, dict):
        raise DataBlocked("INVALID_QUOTE")
    code = label(q, "code", 12)
    pattern = r"DEMO_[A-Z0-9]+" if sample else r"[0-9A-Z]{6}"
    if not re.fullmatch(pattern, code):
        raise DataBlocked("INVALID_SYMBOL")
    for key in ("name", "theme", "risk_group", "source"):
        label(q, key)
    if q.get("venue") not in {"KRX", "NXT"} or q.get("market") not in {"KOSPI", "KOSDAQ"}:
        raise DataBlocked("VENUE_REQUIRED")
    if q.get("session") not in {"REGULAR", "PRE_MARKET", "AFTER_MARKET"}:
        raise DataBlocked("SESSION_REQUIRED")
    if not isinstance(q.get("nxt_eligible"), bool) or (q["venue"] == "NXT" and not q["nxt_eligible"]):
        raise DataBlocked("NXT_ELIGIBILITY_REQUIRED")
    if q.get("delayed") is not False:
        raise DataBlocked("DELAYED_QUOTE")
    fresh(q.get("observed_at"), now)
    fresh(q.get("flow_at"), now)
    technical_at = fresh(q.get("technical_at"), now, 360)
    if technical_at.astimezone(KST).date() != now.astimezone(KST).date():
        raise DataBlocked("TECHNICAL_DATE_MISMATCH")
    if q.get("flow_unit") != "KRW" or q.get("technical_complete") is not True:
        raise DataBlocked("UNVERIFIED_FLOW_OR_TECHNICALS")
    if any("foreign" in key.lower() for key in q):
        raise DataBlocked("FOREIGN_FLOW_NOT_SUPPORTED")
    for key in ("price", "open", "high", "low", "trading_value_krw", "entry_low", "entry_high",
                "stop", "emergency_floor", "target1", "target2"):
        number(q, key, positive=True, integer=True)
    for key in ("ma5", "ma20", "ma120", "five_min_ma20", "volume_ratio"):
        number(q, key, positive=True)
    for key in ("day_change_pct", "five_min_slope", "institution_net_krw", "program_net_krw"):
        number(q, key)
    if not q["low"] <= q["price"] <= q["high"] or not q["low"] <= q["open"] <= q["high"]:
        raise DataBlocked("INCONSISTENT_OHLC")
    if not (q["emergency_floor"] < q["stop"] < q["entry_low"] <= q["price"]
            <= q["entry_high"] < q["target1"] < q["target2"]):
        raise DataBlocked("INVALID_RISK_LEVELS")
    if q.get("levels_tick_validated") is not True:
        raise DataBlocked("TICK_SIZE_NOT_VALIDATED")
    catalyst = q.get("catalyst")
    if not isinstance(catalyst, dict) or catalyst.get("verified") is not True:
        raise DataBlocked("CATALYST_UNVERIFIED")
    label(catalyst, "headline", 500)
    url = urlsplit(label(catalyst, "url", 2000))
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise DataBlocked("INVALID_CATALYST_SOURCE")
    published = timestamp(catalyst.get("published_at"))
    verified = timestamp(catalyst.get("verified_at"))
    age = (now - published).total_seconds()
    if not -2 <= age <= 86400 or not -2 <= (now - verified).total_seconds() <= 3600 or verified < published:
        raise DataBlocked("CATALYST_EXPIRED")


def analyze(snapshot, *, now, capital=600_000, loss_budget=10_000):
    """Input provenance is asserted by a future trusted collector, not verified online here."""
    if now.tzinfo is None:
        raise DataBlocked("TIMEZONE_REQUIRED")
    if (isinstance(capital, bool) or not isinstance(capital, int) or not 1 <= capital <= 700_000
            or isinstance(loss_budget, bool) or not isinstance(loss_budget, int) or not 1 <= loss_budget <= 10_000):
        raise DataBlocked("INVALID_RESEARCH_BUDGET")
    if (not isinstance(snapshot, dict) or type(snapshot.get("schema_version")) is not int or snapshot.get("schema_version") != 1
            or snapshot.get("purpose") != "RESEARCH_ONLY"
            or not isinstance(snapshot.get("is_sample"), bool)):
        raise DataBlocked("RESEARCH_SCHEMA_REQUIRED")
    sample = snapshot["is_sample"]
    fresh(snapshot.get("captured_at"), now)
    fresh(snapshot.get("scanned_at"), now)
    if snapshot.get("universe_basis") != "FRESH_MARKET_SCAN":
        raise DataBlocked("FRESH_UNIVERSE_REQUIRED")
    label(snapshot, "source")
    quotes = snapshot.get("quotes")
    if not isinstance(quotes, list) or len(quotes) > 2000:
        raise DataBlocked("INVALID_UNIVERSE_SIZE")
    if snapshot.get("universe_complete") is not True:
        raise DataBlocked("PARTIAL_UNIVERSE")
    market = snapshot.get("market")
    if not isinstance(market, dict) or market.get("delayed") is not False:
        raise DataBlocked("MARKET_DATA_REQUIRED")
    fresh(market.get("observed_at"), now)
    for key in ("kospi_pct", "kosdaq_pct"):
        number(market, key)
    excluded, eligible, seen = [], [], set()
    for q in quotes:
        code = q.get("code", "") if isinstance(q, dict) else ""
        try:
            validate_quote(q, now, sample)
            if code in seen:
                raise DataBlocked("DUPLICATE_SYMBOL")
            seen.add(code)
        except DataBlocked as exc:
            # Partial or broken input is not a successful scan with zero candidates.
            raise DataBlocked("QUOTE_VALIDATION:" + str(code) + ":" + str(exc)) from exc
        reason = None
        index = market["kospi_pct" if q["market"] == "KOSPI" else "kosdaq_pct"]
        if index <= -2:
            reason = "MARKET_SHOCK"
        elif q["trading_value_krw"] < 10_000_000_000:
            reason = "LOW_TRADING_VALUE"
        elif q["day_change_pct"] >= 12 or q["price"] / q["ma5"] > 1.08:
            reason = "EXTENDED_MOVE"
        elif q["price"] < max(q["ma20"], q["ma120"], q["five_min_ma20"]) or q["five_min_slope"] <= 0:
            reason = "WEAK_TECHNICALS"
        elif q["institution_net_krw"] <= 0 or q["program_net_krw"] <= 0:
            reason = "FLOW_NOT_SUPPORTIVE"
        elif q["volume_ratio"] < 1.2:
            reason = "VOLUME_NOT_EXPANDING"
        hard_risk = q["entry_high"] - q["emergency_floor"]
        reward = q["target1"] - q["entry_high"]
        if not reason and reward / hard_risk < 1.5:
            reason = "UNFAVORABLE_REWARD_RISK"
        if reason:
            excluded.append({"code": code, "reason": reason})
            continue
        strength = (q["price"] - q["low"]) / max(1, q["high"] - q["low"])
        # Experimental rule score, not a calibrated probability of profit.
        score = (min(40, 10 * math.log10(q["trading_value_krw"] / 1_000_000 + 1))
                 + 20 + 15 * strength + 10 * min(2, q["volume_ratio"]) / 2 + 10
                 + (3 if q["price"] < 50_000 else 0))
        eligible.append((score, q, hard_risk))
    eligible.sort(key=lambda row: (-row[0], row[1]["code"]))
    candidates, themes, groups = [], set(), set()
    remaining, planned_risk = capital, 0
    for score, q, risk in eligible:
        if len(candidates) >= 3 or q["theme"] in themes or q["risk_group"] in groups:
            excluded.append({"code": q["code"], "reason": "THEME_OR_PORTFOLIO_LIMIT"})
            continue
        quantity = min(min(capital // 4, remaining) // q["entry_high"],
                       min(loss_budget // 3, loss_budget - planned_risk) // risk)
        if quantity < 1:
            excluded.append({"code": q["code"], "reason": "BUDGET_OR_RISK_LIMIT"})
            continue
        allocation = quantity * q["entry_high"]
        remaining -= allocation
        planned_risk += quantity * risk
        themes.add(q["theme"]); groups.add(q["risk_group"])
        candidates.append({
            "code": q["code"], "name": q["name"], "theme": q["theme"], "score": round(score, 2),
            "venue": q["venue"], "session": q["session"], "nxt_eligible": q["nxt_eligible"],
            "reference_price": q["price"], "observed_at": q["observed_at"],
            "entry_low": q["entry_low"], "entry_high": q["entry_high"], "maximum_chase_price": q["entry_high"],
            "suggested_quantity": quantity, "allocation_krw": allocation,
            "allocation_pct": round(100 * allocation / capital, 2),
            "stop_mode": "5M_CONFIRMED", "stop_price": q["stop"],
            "emergency_stop": q["emergency_floor"], "emergency_stop_mode": "IMMEDIATE",
            "target1": q["target1"], "target2": q["target2"],
            "planned_emergency_loss_krw": quantity * risk,
            "reasons": ["거래대금·거래량 확대 조건 충족", "당일 기관·프로그램 순매수 조건 충족",
                        "분봉·일봉 지지와 비상 하한 기준 손익비 확인", q["catalyst"]["headline"]],
            "risks": ["실험적 규칙이며 수익 확률이 아님", "호가 미연결: 매도벽·스프레드 확인 필요",
                      "갭과 비용으로 실제 손실이 계획손실을 초과할 수 있음"],
            "sources": [q["source"], q["catalyst"]["url"]],
        })
    deadlines = [timestamp(snapshot[key]) + timedelta(seconds=90) for key in ("captured_at", "scanned_at")]
    deadlines.append(timestamp(market["observed_at"]) + timedelta(seconds=90))
    for q in quotes:
        deadlines.extend(timestamp(q[key]) + timedelta(seconds=90) for key in ("observed_at", "flow_at"))
        deadlines.extend([timestamp(q["technical_at"]) + timedelta(seconds=360),
                          timestamp(q["catalyst"]["published_at"]) + timedelta(days=1),
                          timestamp(q["catalyst"]["verified_at"]) + timedelta(hours=1)])
    expires = min(*deadlines, now + timedelta(seconds=30))
    return {"schema_version": 1, "purpose": "RESEARCH_ONLY", "rule_version": RULE_VERSION,
            "status": "CANDIDATES" if candidates else "NO_TRADE", "is_sample": sample,
            "generated_at": now.isoformat(), "data_cutoff_at": snapshot["captured_at"],
            "expires_at": expires.isoformat(), "explanation_type": "RULE_BASED",
            "market": market, "candidates": candidates, "excluded": excluded,
            "research_capital_krw": capital, "allocated_krw": capital - remaining,
            "remaining_cash_krw": remaining, "planned_emergency_loss_krw": planned_risk,
            "order_submission": False, "ledger_mutation": False,
            "limitations": ["입력 파일의 출처·사실 확인은 향후 연결할 신뢰된 수집기에서 수행해야 함",
                            "AI·뉴스 자동 수집·실시간 수집 미연결", "독립 검증 전 개발용 연구 결과"]}
