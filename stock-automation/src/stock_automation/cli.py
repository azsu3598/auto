from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backtest import TradingCosts, run_backtest
from .backtest_io import load_replay_cases
from .config import StrategyConfig
from .doctor import diagnose
from .engine import ClosingBetEngine
from .io import load_snapshot
from .ledger import DuplicateDecisionError, JsonlLedger
from .reporting import append_training_event, write_markdown_report
from .learning import TuningPolicy, tune_strategy, write_paper_champion, write_tuning_result
from .medium_term import MediumTermEngine
from .medium_term_io import load_medium_term_snapshot
from .day_trade import DayTradeEngine
from .day_trade_io import load_day_trade_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scheduled closing-bet paper trader")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="score a snapshot and record a paper decision")
    analyze.add_argument("--snapshot", required=True)
    analyze.add_argument("--ledger", required=True)
    analyze.add_argument("--cash", type=int, default=600_000)
    analyze.add_argument("--output")
    analyze.add_argument("--report-dir")
    analyze.add_argument("--training-events")
    sub.add_parser("aws-run", help="run the scheduled AWS paper-trading task")
    backtest = sub.add_parser("backtest", help="replay recorded 5-minute paths")
    _add_replay_arguments(backtest)
    backtest.add_argument("--output", required=True)
    tune = sub.add_parser("tune", help="walk-forward tune chart thresholds for paper mode")
    _add_replay_arguments(tune)
    tune.add_argument("--output", required=True)
    tune.add_argument("--paper-champion")
    tune.add_argument("--minimum-cases", type=int, default=40)
    tune.add_argument("--minimum-validation-trades", type=int, default=5)
    medium = sub.add_parser(
        "medium-analyze",
        help="score a separate 20-40 trading-day paper strategy snapshot",
    )
    medium.add_argument("--snapshot", required=True)
    medium.add_argument("--ledger", required=True)
    medium.add_argument("--cash", type=int, default=600_000)
    medium.add_argument("--output")
    day_trade = sub.add_parser(
        "daytrade-analyze",
        help="score one isolated intraday snapshot and record a paper decision",
    )
    day_trade.add_argument("--snapshot", required=True)
    day_trade.add_argument("--ledger", required=True)
    day_trade.add_argument("--cash", type=int, default=600_000)
    day_trade.add_argument("--output")
    day_trade_kiwoom = sub.add_parser(
        "daytrade-kiwoom-scan",
        help="run one on-demand Kiwoom read-only scan and record a paper decision",
    )
    day_trade_kiwoom.add_argument("--catalysts")
    day_trade_kiwoom.add_argument("--ledger", required=True)
    day_trade_kiwoom.add_argument("--cash", type=int, default=600_000)
    day_trade_kiwoom.add_argument("--candidate-limit", type=int, default=30)
    day_trade_kiwoom.add_argument("--output")
    doctor = sub.add_parser(
        "doctor",
        help="validate paper-only credentials and optionally probe read APIs",
    )
    doctor.add_argument("--online", action="store_true")
    doctor.add_argument("--aws", action="store_true")
    doctor.add_argument("--write-probes", action="store_true", help="explicitly verify temporary/S3 storage and isolated DynamoDB transactions")
    doctor.add_argument("--test-notification", action="store_true", help="explicitly send one paper-environment test notification")
    storage_check = sub.add_parser("verify-storage-contract", help="explicit isolated paper wallet/lease storage checks; no strategy or broker calls")
    storage_check.add_argument("--confirm-isolated-probe", action="store_true", required=True)
    dashboard = sub.add_parser(
        "dashboard", help="run the local read-only paper-trading operations console"
    )
    dashboard.add_argument("--port", type=int, default=8765)
    dashboard.add_argument("--fixture", help="preview the console with a local JSON fixture")
    live_prepare = sub.add_parser(
        "live-prepare", help="create an exact real-order intent without submitting it"
    )
    live_prepare.add_argument("--side", choices=("BUY", "SELL"), required=True)
    live_prepare.add_argument("--code", required=True)
    live_prepare.add_argument("--name", required=True)
    live_prepare.add_argument("--quantity", type=int, required=True)
    live_prepare.add_argument("--limit-price", type=int, required=True)
    live_prepare.add_argument("--strategy", choices=("CLOSING_BET", "MEDIUM_TERM"), required=True)
    live_prepare.add_argument("--account-alias", required=True)
    live_prepare.add_argument("--event-id")
    live_prepare.add_argument("--table")
    live_approve = sub.add_parser(
        "live-approve", help="approve one exact real-order intent by its challenge"
    )
    live_approve.add_argument("--intent-id", required=True)
    live_approve.add_argument("--challenge", required=True)
    live_approve.add_argument("--table")
    live_execute = sub.add_parser(
        "live-execute", help="submit one approved order after fresh account-risk checks"
    )
    live_execute.add_argument("--intent-id", required=True)
    live_execute.add_argument("--exchange", choices=("KRX", "NXT", "SOR"), default="KRX")
    live_execute.add_argument("--table")
    live_kill = sub.add_parser(
        "live-kill-switch", help="turn the real-order kill switch on or off"
    )
    live_kill.add_argument("--state", choices=("ON", "OFF"), required=True)
    live_kill.add_argument("--account-alias", required=True)
    live_kill.add_argument("--confirm")
    live_kill.add_argument("--table")
    live_baseline = sub.add_parser(
        "live-account-baseline",
        help="lock the current real-account holdings as protected (does not order)",
    )
    live_baseline.add_argument("--account-alias", required=True)
    live_baseline.add_argument("--exchange", choices=("KRX", "NXT", "SOR"), default="KRX")
    live_baseline.add_argument("--confirm", required=True)
    live_baseline.add_argument("--table")
    live_reconcile = sub.add_parser(
        "live-reconcile",
        help="read one broker order and reconcile cumulative fills (does not submit)",
    )
    live_reconcile.add_argument("--intent-id", required=True)
    live_reconcile.add_argument("--table")
    live_supervise = sub.add_parser(
        "live-supervise",
        help="reconcile all open orders, cancel stale remainders, and verify holdings",
    )
    live_supervise.add_argument("--account-alias", required=True)
    live_supervise.add_argument("--exchange", choices=("KRX",), default="KRX")
    live_supervise.add_argument("--max-unfilled-seconds", type=int, default=180)
    live_supervise.add_argument("--confirm", required=True)
    live_supervise.add_argument("--table")
    return parser


def _add_replay_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cases", required=True)
    parser.add_argument("--cash", type=int, default=600_000)
    parser.add_argument("--buy-fee-bps", type=float, required=True)
    parser.add_argument("--sell-fee-bps", type=float, required=True)
    parser.add_argument("--sell-tax-bps", type=float, required=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify-storage-contract":
        from .storage_contracts import run
        return run()
    if args.command == "aws-run":
        from .scheduled_execution import run_bounded

        return run_bounded()
    if args.command == "doctor":
        report = diagnose(online=args.online, aws=args.aws,
                          write_probes=args.write_probes, test_notification=args.test_notification)
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if report.ok else 1
    if args.command == "dashboard":
        from .dashboard import repository_from_environment, serve_dashboard

        serve_dashboard(
            repository_from_environment(fixture=args.fixture),
            port=args.port,
        )
        return 0
    if args.command.startswith("live-"):
        from . import live_cli

        handlers = {
            "live-prepare": live_cli.prepare,
            "live-approve": live_cli.approve,
            "live-execute": live_cli.execute,
            "live-kill-switch": live_cli.set_kill_switch,
            "live-account-baseline": live_cli.initialize_account_baseline,
            "live-reconcile": live_cli.reconcile,
            "live-supervise": live_cli.supervise,
        }
        return handlers[args.command](args)
    if args.command in {"backtest", "tune"}:
        cases = load_replay_cases(args.cases)
        if not cases:
            raise SystemExit("no replay cases")
        sessions = {case.snapshot.session for case in cases}
        if len(sessions) != 1:
            raise SystemExit("replay sessions must be evaluated separately")
        costs = TradingCosts(args.buy_fee_bps, args.sell_fee_bps, args.sell_tax_bps)
        base = StrategyConfig(session=cases[0].snapshot.session)
        if args.command == "backtest":
            summary = run_backtest(cases, starting_cash=args.cash, costs=costs, config=base)
            rendered = json.dumps(summary.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered + "\n", encoding="utf-8")
            print(rendered)
            return 0
        result = tune_strategy(
            cases,
            starting_cash=args.cash,
            costs=costs,
            base_config=base,
            policy=TuningPolicy(
                minimum_cases=args.minimum_cases,
                minimum_validation_trades=args.minimum_validation_trades,
            ),
        )
        write_tuning_result(args.output, result)
        if args.paper_champion and result.promoted:
            write_paper_champion(args.paper_champion, result, base)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "medium-analyze":
        snapshot = load_medium_term_snapshot(args.snapshot)
        decision = MediumTermEngine().evaluate(snapshot, cash=args.cash)
        ledger = JsonlLedger(args.ledger)
        try:
            ledger.append(decision)
        except DuplicateDecisionError as exc:
            raise SystemExit(f"duplicate medium-term decision: {exc}") from exc
        rendered = json.dumps(decision.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    if args.command == "daytrade-analyze":
        snapshot = load_day_trade_snapshot(args.snapshot)
        decision = DayTradeEngine().evaluate(snapshot, cash=args.cash)
        ledger = JsonlLedger(args.ledger)
        try:
            ledger.append(decision)
        except DuplicateDecisionError as exc:
            raise SystemExit(f"duplicate day-trade decision: {exc}") from exc
        rendered = json.dumps(decision.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    if args.command == "daytrade-kiwoom-scan":
        return _run_day_trade_kiwoom(args)
    if args.command != "analyze":
        raise AssertionError(args.command)

    snapshot = load_snapshot(args.snapshot)
    config = StrategyConfig(session=snapshot.session)
    decision = ClosingBetEngine(config).evaluate(snapshot, cash=args.cash)
    ledger = JsonlLedger(args.ledger)
    try:
        ledger.append(decision)
    except DuplicateDecisionError as exc:
        raise SystemExit(f"duplicate scheduled decision: {exc}") from exc

    if args.training_events:
        append_training_event(args.training_events, snapshot, decision)
    if args.report_dir:
        write_markdown_report(args.report_dir, snapshot, decision)

    rendered = json.dumps(decision.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


def _run_day_trade_kiwoom(args) -> int:
    import os
    from datetime import datetime, timedelta, timezone

    from .providers.kiwoom import Catalyst, KiwoomSnapshotBuilder
    from .providers.reliable import KiwoomRetryPolicy, ReliableKiwoomClient

    now = datetime.now(timezone(timedelta(hours=9)))
    # The catalyst file is optional: candidates come from the trading-value
    # ranking and a verified same-day catalyst only adds score.
    raw = json.loads(Path(args.catalysts).read_text(encoding="utf-8")) if args.catalysts else {}
    catalysts: dict[str, Catalyst] = {}
    for code, item in raw.items():
        if not isinstance(item, dict):
            continue
        verified_at = datetime.fromisoformat(str(item.get("verified_at", "")))
        if verified_at.tzinfo is None:
            raise ValueError(f"catalyst timezone is required: {code}")
        if (
            item.get("verified") is True
            and str(item.get("source", "")).strip()
            and verified_at.astimezone(now.tzinfo).date() == now.date()
        ):
            catalysts[str(code)] = Catalyst(
                str(item.get("theme", "")),
                str(item.get("summary", "")),
                float(item.get("score", 0.0)),
                True,
            )
    from kiwoom import get_client

    client = ReliableKiwoomClient(
        get_client(mode=os.getenv("KIWOOM_MODE", "mock"), timeout_seconds=20),
        KiwoomRetryPolicy(
            min_interval_seconds=max(0.25, float(os.getenv("KIWOOM_MIN_INTERVAL_SECONDS", "0.25"))),
            per_api_min_interval_seconds=1.0,
            max_attempts=int(os.getenv("KIWOOM_READ_MAX_ATTEMPTS", "4")),
        ),
    )
    builder = KiwoomSnapshotBuilder(client)
    snapshot = builder.build_day_trade_snapshot(
        captured_at=now,
        catalysts=catalysts,
        kospi_change_pct=builder.market_change_pct(market="0", index_code="001"),
        kosdaq_change_pct=builder.market_change_pct(market="1", index_code="101"),
        candidate_limit=args.candidate_limit,
    )
    decision = DayTradeEngine().evaluate(snapshot, cash=args.cash)
    ledger = JsonlLedger(args.ledger)
    try:
        ledger.append(decision)
    except DuplicateDecisionError as exc:
        raise SystemExit(f"duplicate day-trade decision: {exc}") from exc
    payload = decision.to_dict()
    payload.update({
        "snapshot_source": snapshot.source,
        "snapshot_quote_count": len(snapshot.quotes),
        "paper_only": True,
    })
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
