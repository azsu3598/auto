"""Summarize why saved closing-bet snapshots produced no candidates.

Read-only and offline: it loads snapshot JSON files that were already downloaded
(for example runs/<date>/KRX_1520/scan_1450-snapshot.json) and runs the engine's
hard filters on them. No AWS clients, credentials, orders, or file writes.
Only the first failed filter per stock is counted, using the base StrategyConfig.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stock_automation.config import StrategyConfig  # noqa: E402
from stock_automation.engine import ClosingBetEngine  # noqa: E402
from stock_automation.io import snapshot_from_dict  # noqa: E402

LABELS = {
    "STALE_QUOTE": "시세 시각이 오래됨",
    "NXT_ELIGIBLE_EXCLUDED": "NXT 대상 종목(KRX 전략 제외)",
    "PRICE_OUT_OF_RANGE": "가격 범위 초과",
    "LOW_TRADING_VALUE": "거래대금 부족",
    "LOW_VOLUME_RATIO": "거래량 증가 부족",
    "WEAK_CLOSE_STRENGTH": "종가 강도 부족",
    "DAY_CHANGE_OUT_OF_RANGE": "당일 등락률 범위 초과",
    "BELOW_5M_MA20_OR_FALLING": "5분봉 20이평 아래이거나 하락",
    "INVALID_SUPPORT": "지지선 유효하지 않음",
    "EXTENDED_FROM_MA5": "5일선에서 과도하게 이격",
    "BELOW_VWAP": "VWAP 아래",
    "RSI_OUT_OF_RANGE": "RSI 범위 이탈",
    "CATALYST_NOT_VERIFIED": "촉매 미확인",
    "MARKET_DECLINE_GATE": "시장 급락 차단",
}


def summarize_file(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    snapshot = snapshot_from_dict(raw)
    engine = ClosingBetEngine(StrategyConfig(session=snapshot.session))
    reasons = engine.rejection_reasons(snapshot)
    passed = len(snapshot.quotes) - len(reasons)
    return {
        "file": str(path),
        "captured_at": snapshot.captured_at.isoformat(),
        "session": snapshot.session.value,
        "quotes": len(snapshot.quotes),
        "passed_hard_filters": passed,
        "counts": dict(Counter(reasons.values())),
        "reasons": reasons,
    }


def collect(paths: list[Path]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    skipped: list[dict] = []
    for path in paths:
        try:
            rows.append(summarize_file(path))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            skipped.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})
    return rows, skipped


def render(rows: list[dict], skipped: list[dict]) -> str:
    total = Counter()
    quotes = passed = 0
    lines = ["## 파일별 결과", "", "| 파일 | 수신 시세 | 하드 필터 통과 | 가장 많은 탈락 사유 |", "|---|---|---|---|"]
    for row in rows:
        total.update(row["counts"])
        quotes += row["quotes"]
        passed += row["passed_hard_filters"]
        top = max(row["counts"].items(), key=lambda item: item[1], default=None)
        top_text = f"{LABELS.get(top[0], top[0])} {top[1]}건" if top else "-"
        lines.append(f"| {row['file']} | {row['quotes']} | {row['passed_hard_filters']} | {top_text} |")
    lines += ["", f"## 전체 집계 (파일 {len(rows)}개, 시세 {quotes}건, 하드 필터 통과 {passed}건)", ""]
    lines += ["| 탈락 사유 | 건수 | 비율 |", "|---|---|---|"]
    rejected = sum(total.values())
    for code, count in sorted(total.items(), key=lambda item: (-item[1], item[0])):
        share = f"{count / rejected * 100:.1f}%" if rejected else "-"
        lines.append(f"| {LABELS.get(code, code)} (`{code}`) | {count} | {share} |")
    lines += [
        "",
        "한 종목은 처음 걸린 사유 하나로만 집계된다. 테마 중복과 점수 미달 탈락은 포함하지 않는다.",
        "기본 설정(StrategyConfig)을 사용하므로 챔피언 규칙으로 바뀐 값은 반영되지 않는다.",
    ]
    if skipped:
        lines += ["", "## 읽지 못한 파일", ""]
        lines += [f"- {item['file']}: {item['error']}" for item in skipped]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="append", default=[], type=Path, help="snapshot JSON file")
    parser.add_argument("--dir", type=Path, help="directory searched recursively for *-snapshot.json")
    parser.add_argument("--json", action="store_true", help="print raw JSON instead of a table")
    args = parser.parse_args(argv)
    paths = list(args.snapshot)
    if args.dir:
        paths += sorted(args.dir.rglob("*-snapshot.json"))
    if not paths:
        parser.error("give at least one --snapshot or a --dir containing *-snapshot.json")
    rows, skipped = collect(paths)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps({"files": rows, "skipped": skipped}, ensure_ascii=False, indent=2))
    else:
        print(render(rows, skipped))
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
