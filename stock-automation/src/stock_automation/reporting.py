from __future__ import annotations

import csv
from pathlib import Path

from .models import Decision, DecisionType, MarketSnapshot

EVENT_COLUMNS = (
    "event_id", "recorded_at_kst", "analysis_at_kst", "strategy", "event_type",
    "stock_code", "stock_name", "reference_price", "entry_low", "entry_high",
    "stop_mode", "stop_price", "emergency_stop", "target1", "target2",
    "kospi_pct", "kosdaq_pct", "nxt_eligible", "decision", "actual_trade_status",
    "actual_entry", "actual_exit", "quantity", "check_at_kst", "check_price",
    "outcome_code", "rule_version", "notes",
)


def append_training_event(
    path: str | Path,
    snapshot: MarketSnapshot,
    decision: Decision,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_header = not destination.exists() or destination.stat().st_size == 0
    position = decision.position
    selected = decision.candidates[0].quote if decision.candidates else None
    row = {
        "event_id": decision.event_id,
        "recorded_at_kst": decision.decided_at.strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_at_kst": snapshot.captured_at.strftime("%Y-%m-%d %H:%M:%S"),
        "strategy": "CLOSING_BET" if snapshot.session.value == "KRX_1520" else "NXT_CLOSING_BET",
        "event_type": "SIMULATED_BUY" if position else "NO_TRADE",
        "stock_code": position.code if position else "",
        "stock_name": position.name if position else "",
        "reference_price": position.entry_price if position else "",
        "entry_low": position.entry_price if position else "",
        "entry_high": position.entry_price if position else "",
        "stop_mode": position.stop_mode.value if position else "",
        "stop_price": position.stop_price if position else "",
        "emergency_stop": position.emergency_stop if position else "",
        "target1": position.target1 if position else "",
        "target2": position.target2 if position else "",
        "kospi_pct": snapshot.kospi_change_pct,
        "kosdaq_pct": snapshot.kosdaq_change_pct,
        "nxt_eligible": str(selected.nxt_eligible).upper() if selected else "",
        "decision": decision.decision.value,
        "actual_trade_status": "AI_SIMULATED" if position else "AI_SIM_NO_TRADE",
        "actual_entry": "",
        "actual_exit": "",
        "quantity": position.quantity if position else 0,
        "check_at_kst": snapshot.captured_at.strftime("%Y-%m-%d %H:%M:%S"),
        "check_price": selected.price if selected else "",
        "outcome_code": "|".join(decision.reason_codes),
        "rule_version": decision.rule_version,
        "notes": decision.notes,
    }
    with destination.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def write_markdown_report(
    directory: str | Path,
    snapshot: MarketSnapshot,
    decision: Decision,
) -> Path:
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    stem = snapshot.captured_at.strftime("%Y-%m-%d_%H%M_korean-stock-analysis")
    path = destination / f"{stem}.md"
    sequence = 2
    while path.exists():
        path = destination / f"{stem}-{sequence:02d}.md"
        sequence += 1

    lines = [
        "# 종가배팅 자동 분석",
        "",
        f"- 분석 기준: {snapshot.captured_at.isoformat()}",
        f"- 세션: {snapshot.session.value}",
        f"- 데이터 출처: {snapshot.source}",
        f"- 지연 데이터: {'예' if snapshot.delayed else '아니오'}",
        f"- 규칙 버전: {decision.rule_version}",
        "",
        "## 시장 상태",
        "",
        f"- KOSPI: {snapshot.kospi_change_pct:+.2f}%",
        f"- KOSDAQ: {snapshot.kosdaq_change_pct:+.2f}%",
        "",
        "## 최종 결정",
        "",
    ]
    if decision.decision == DecisionType.BUY and decision.position:
        p = decision.position
        lines.extend([
            f"**AI 모의매수: {p.name}({p.code})**",
            "",
            f"- 모의 체결가: {p.entry_price:,}원",
            f"- 수량: {p.quantity:,}주",
            f"- 투자금: {p.invested_amount:,}원",
            f"- 남은 현금: {decision.remaining_cash:,}원",
            f"- 손절 방식: `{p.stop_mode.value}`",
            f"- 손절가 / 비상 하드 스톱: {p.stop_price:,}원 / {p.emergency_stop:,}원",
            f"- 1차 / 2차 목표가: {p.target1:,}원 / {p.target2:,}원",
            "- 실제 주문은 전송하지 않음",
        ])
    else:
        lines.extend([
            "**NO_TRADE**",
            "",
            "- 투자금: 0원",
            f"- 현금: {decision.remaining_cash:,}원(100%)",
            f"- 사유: {', '.join(decision.reason_codes)}",
        ])

    lines.extend(["", "## 최종 후보", ""])
    if not decision.candidates:
        lines.append("조건을 통과한 후보가 없다.")
    else:
        lines.extend([
            "| 순위 | 종목 | 기준가 | 점수 | 근거 | 위험 |",
            "|---:|---|---:|---:|---|---|",
        ])
        for index, candidate in enumerate(decision.candidates, 1):
            lines.append(
                f"| {index} | {candidate.quote.name}({candidate.quote.code}) | "
                f"{candidate.quote.price:,}원 | {candidate.score:.2f} | "
                f"{', '.join(candidate.reasons)} | {', '.join(candidate.risks) or '-'} |"
            )
        lines.extend(["", "## 차트 근거", ""])
        for candidate in decision.candidates:
            q = candidate.quote
            lines.extend([
                f"### {q.name}({q.code})",
                "",
                f"- 종가 위치: 일중 범위 상단 {q.close_strength * 100:.1f}%",
                f"- 거래량: 전일 대비 {q.volume_ratio:.2f}배",
                f"- 일봉 이평: 5일 {q.ma5:,.0f} / 20일 {q.ma20:,.0f}"
                + (f" / 60일 {q.ma60:,.0f}" if q.ma60 is not None else "")
                + (f" / 120일 {q.ma120:,.0f}" if q.ma120 is not None else ""),
                f"- 5분 20이평: {q.five_min_ma20:,.0f}, 기울기 {q.five_min_ma20_slope:+.2f}",
                f"- VWAP: {q.vwap:,.0f}" if q.vwap is not None else "- VWAP: 확인 불가",
                f"- RSI(14): {q.rsi14:.1f}" if q.rsi14 is not None else "- RSI(14): 확인 불가",
                f"- ATR(14): {q.atr14:,.0f}" if q.atr14 is not None else "- ATR(14): 확인 불가",
                f"- 마감 5분봉 거래량 배율: {q.five_min_volume_ratio:.2f}배"
                if q.five_min_volume_ratio is not None else "- 마감 5분봉 거래량 배율: 확인 불가",
                f"- 최근 1시간 수익률: {q.last_hour_return_pct:+.2f}%"
                if q.last_hour_return_pct is not None else "- 최근 1시간 수익률: 확인 불가",
                f"- 고점·저점 상승 구조: {'예' if q.higher_lows else '아니오/미확인'}",
                f"- 돌파 유지: {'예' if q.breakout_holds else '아니오/미확인'}"
                + (f" (기준 {q.breakout_level:,.0f})" if q.breakout_level is not None else ""),
                f"- 최근 저항: {q.recent_resistance:,.0f}" if q.recent_resistance is not None else "- 최근 저항: 확인 불가",
                f"- 테마: {q.theme or '미분류'}",
                f"- 검증 촉매: {q.catalyst}" if q.catalyst_verified else "- 검증 촉매: 확인 불가",
                f"- 프로그램 순매수: {q.program_net:,}" if q.program_net is not None else "- 프로그램 순매수: 확인 불가",
                f"- 기관 순매수: {q.institution_net:,}" if q.institution_net is not None else "- 기관 순매수: 확인 불가",
                "",
            ])
    lines.extend([
        "",
        "## 불확실성과 무효화 조건",
        "",
        "- 데이터 지연, API 오류, 가격 불일치가 확인되면 거래하지 않는다.",
        "- 촉매가 무효화되거나 시장 충격이 발생하면 비상 하드 스톱을 우선 적용한다.",
        "- 사용자가 별도로 승인하기 전까지 결과는 모의 체결로만 기록한다.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
