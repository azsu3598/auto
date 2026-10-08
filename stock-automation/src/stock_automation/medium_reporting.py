from __future__ import annotations

from .medium_term import (
    MediumTermDecision,
    MediumTermEntryConfirmation,
    MediumTermExitDecision,
    MediumTermPosition,
    MediumTermSnapshot,
)


def render_signal_report(snapshot: MediumTermSnapshot, decision: MediumTermDecision) -> str:
    lines = [
        "# 중기 전략 모의신호 보고서",
        "",
        f"- 기준시각: {snapshot.captured_at.isoformat()}",
        f"- 데이터 출처: {snapshot.source}",
        "- 실행 구분: 모의투자 전용",
        f"- 결정: {decision.decision.value}",
        f"- 가용현금: {decision.starting_cash:,}원",
        "",
        "## 후보",
        "",
    ]
    if not decision.candidates:
        lines.append("- 검증 기준을 통과한 후보 없음")
    for candidate in decision.candidates:
        quote = candidate.quote
        lines.extend([
            f"### {quote.name} ({quote.code})",
            "",
            f"- 기준가: {quote.price:,}원",
            f"- 점수: {candidate.score:.2f}",
            f"- 근거: {', '.join(candidate.reasons) or '없음'}",
            f"- 위험: {', '.join(candidate.risks) or '없음'}",
            f"- 공시·촉매: {quote.catalyst or '확인된 긍정 촉매 없음'}",
            "",
        ])
    lines.extend(["## 최종 계획", ""])
    plan = decision.entry_plan
    if plan is None:
        lines.append(f"- NO_TRADE: {', '.join(decision.reason_codes)}")
    else:
        lines.extend([
            f"- 종목: {plan.name} ({plan.code})",
            f"- 신호 기준가: {plan.reference_price:,}원",
            f"- 익일 최대 진입가: {plan.maximum_entry_price:,}원",
            f"- 제안 수량: {plan.suggested_quantity}주",
            f"- 투자논리 훼손가: {plan.thesis_invalidation:,}원",
            f"- 비상 하한: {plan.emergency_stop:,}원",
            f"- 목표가: {plan.target1:,}원 / {plan.target2:,}원",
            "- 주의: 당일 체결이 아니며 다음 거래일 확인가로 재검증",
        ])
    return "\n".join(lines).rstrip() + "\n"


def render_entry_report(result: MediumTermEntryConfirmation) -> str:
    lines = [
        "# 중기 전략 익일 진입 확인",
        "",
        f"- 확인시각: {result.observed_at.isoformat()}",
        f"- 확인가격: {result.observed_price:,}원",
        f"- 결정: {result.action.value}",
        f"- 사유: {', '.join(result.reason_codes)}",
        "- 실행 구분: 모의투자 전용",
    ]
    if result.position:
        position = result.position
        lines.extend([
            f"- 종목: {position.name} ({position.code})",
            f"- 모의 진입가/수량: {position.entry_price:,}원 / {position.quantity}주",
            f"- 투자금: {position.invested_amount:,}원",
            f"- 투자논리 훼손가: {position.thesis_invalidation:,}원",
            f"- 목표가: {position.target1:,}원 / {position.target2:,}원",
        ])
    return "\n".join(lines) + "\n"


def render_review_report(
    position: MediumTermPosition,
    result: MediumTermExitDecision,
    *,
    trading_days_held: int,
    net_pnl: int | None,
    total_costs: int | None,
) -> str:
    lines = [
        "# 중기 전략 보유 포지션 재평가",
        "",
        f"- 판단시각: {result.decided_at.isoformat()}",
        f"- 종목: {position.name} ({position.code})",
        f"- 진입가: {position.entry_price:,}원",
        f"- 보유 거래일: {trading_days_held}일",
        f"- 결정: {result.action.value}",
        f"- 사유: {', '.join(result.reason_codes)}",
        f"- 남은 수량: {result.remaining_quantity}주",
        "- 실행 구분: 모의투자 전용",
    ]
    if result.execution_price is not None:
        lines.extend([
            f"- 모의 체결가/수량: {result.execution_price:,}원 / {result.execution_quantity}주",
            f"- 순실현손익: {net_pnl or 0:,}원",
            f"- 수수료·세금: {total_costs or 0:,}원",
        ])
    return "\n".join(lines) + "\n"
