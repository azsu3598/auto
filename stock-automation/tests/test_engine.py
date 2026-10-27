from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_automation.config import StrategyConfig
from stock_automation.engine import ClosingBetEngine
from stock_automation.ledger import DuplicateDecisionError, JsonlLedger
from stock_automation.models import DecisionType, MarketSnapshot, Quote, Session

KST = timezone(timedelta(hours=9))


def quote(**overrides) -> Quote:
    values = dict(
        code="123456",
        name="테스트",
        observed_at=datetime(2026, 10, 6, 15, 20, tzinfo=KST),
        price=20_000,
        open_price=19_000,
        high_price=20_100,
        low_price=18_900,
        volume=1_800_000,
        trading_value=36_000_000_000,
        previous_volume=1_000_000,
        day_change_pct=5.0,
        ma5=19_400,
        ma20=18_900,
        ma120=17_000,
        five_min_ma20=19_700,
        five_min_ma20_slope=0.4,
        support_price=19_400,
        nxt_eligible=False,
        theme="robot",
        catalyst="confirmed contract",
        catalyst_score=0.8,
        catalyst_verified=True,
        market="KOSPI",
        institution_net=500_000_000,
        program_net=300_000_000,
        best_ask=20_000,
        best_bid=19_990,
        total_ask_size=100_000,
        total_bid_size=90_000,
    )
    values.update(overrides)
    return Quote(**values)


def snapshot(*quotes: Quote, session: Session = Session.KRX_1520, delayed: bool = False):
    return MarketSnapshot(
        captured_at=datetime(2026, 10, 6, 15, 20, 30, tzinfo=KST),
        session=session,
        kospi_change_pct=0.2,
        kosdaq_change_pct=0.5,
        quotes=tuple(quotes),
        source="fixture",
        delayed=delayed,
    )


class ClosingBetEngineTests(unittest.TestCase):
    def test_empty_verified_universe_is_recorded_as_no_trade(self):
        current = datetime(2026, 10, 7, 15, 20, tzinfo=KST)
        snapshot = MarketSnapshot(
            captured_at=current,
            session=Session.KRX_1520,
            kospi_change_pct=0.0,
            kosdaq_change_pct=0.0,
            quotes=(),
            source="KIWOOM_REST",
            delayed=False,
        )
        decision = ClosingBetEngine().evaluate(snapshot, cash=600_000)
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)
        self.assertEqual(("MARKET_DATA_UNAVAILABLE",), decision.reason_codes)
        self.assertIn("시세 자료", decision.notes)

    def test_empty_prior_screen_is_not_reported_as_missing_market_data(self):
        current = datetime(2026, 10, 7, 15, 20, tzinfo=KST)
        empty = MarketSnapshot(
            captured_at=current,
            session=Session.KRX_1520,
            kospi_change_pct=0.0,
            kosdaq_change_pct=0.0,
            quotes=(),
            source="KIWOOM_REST",
            delayed=False,
        )
        decision = ClosingBetEngine().evaluate(
            empty, cash=600_000, prior_screen_empty=True
        )
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)
        self.assertEqual(("NO_QUALIFYING_CANDIDATE",), decision.reason_codes)
        self.assertIn("후보 선별", decision.notes)

    def test_quotes_filtered_out_are_reported_as_no_qualifying_candidate(self):
        decision = ClosingBetEngine().evaluate(
            snapshot(quote(trading_value=1_000_000_000)), cash=600_000
        )
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)
        self.assertEqual(("NO_QUALIFYING_CANDIDATE",), decision.reason_codes)
        self.assertIn("선별·위험 기준", decision.notes)

    def test_selects_one_paper_position_with_bounded_risk(self):
        decision = ClosingBetEngine().evaluate(snapshot(quote()), cash=600_000)
        self.assertEqual(DecisionType.BUY, decision.decision)
        self.assertIsNotNone(decision.position)
        self.assertLessEqual(
            (decision.position.entry_price - decision.position.emergency_stop)
            * decision.position.quantity,
            10_000,
        )
        self.assertLessEqual(decision.position.invested_amount, 240_000)
        self.assertIn("PAPER_EXECUTION_ONLY", decision.reason_codes)

    def test_krx_strategy_excludes_nxt_eligible_stock(self):
        decision = ClosingBetEngine().evaluate(
            snapshot(quote(nxt_eligible=True)), cash=600_000
        )
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)

    def test_nxt_session_can_be_explicitly_enabled(self):
        q = quote(
            nxt_eligible=True,
            observed_at=datetime(2026, 10, 6, 19, 55, tzinfo=KST),
        )
        snap = MarketSnapshot(
            captured_at=datetime(2026, 10, 6, 19, 55, 30, tzinfo=KST),
            session=Session.NXT_1955,
            kospi_change_pct=0.2,
            kosdaq_change_pct=0.5,
            quotes=(q,),
            source="fixture",
        )
        engine = ClosingBetEngine(StrategyConfig(session=Session.NXT_1955))
        self.assertEqual(DecisionType.BUY, engine.evaluate(snap, cash=600_000).decision)

    def test_rejects_stale_quote(self):
        old = quote(observed_at=datetime(2026, 10, 6, 15, 10, tzinfo=KST))
        decision = ClosingBetEngine().evaluate(snapshot(old), cash=600_000)
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)

    def test_rejection_reasons_name_first_failed_filter_per_code(self):
        engine = ClosingBetEngine()
        snap = snapshot(
            quote(code="000001"),
            quote(code="000002", trading_value=1_000_000_000),
            # An unverified catalyst only lowers the score; it is not a rejection.
            quote(code="000003", catalyst_verified=False),
            quote(code="000004", observed_at=datetime(2026, 10, 6, 15, 10, tzinfo=KST)),
            quote(code="000005", nxt_eligible=True),
            # Fails both volume ratio and RSI; the earlier gate is reported.
            quote(code="000006", volume=500_000, rsi14=86.0),
        )
        self.assertEqual(
            {
                "000002": "LOW_TRADING_VALUE",
                "000004": "STALE_QUOTE",
                "000005": "NXT_ELIGIBLE_EXCLUDED",
                "000006": "LOW_VOLUME_RATIO",
            },
            engine.rejection_reasons(snap),
        )

    def test_rejection_reasons_match_ranking_membership(self):
        engine = ClosingBetEngine()
        snap = snapshot(
            quote(code="000001", theme="a"),
            quote(code="000002", theme="b", rsi14=86.0, vwap=19_700),
        )
        rejected = engine.rejection_reasons(snap)
        ranked = {c.quote.code for c in engine.rank_candidates(snap)}
        self.assertEqual({"000002"}, set(rejected))
        self.assertEqual({"000001"}, ranked)
        self.assertEqual("RSI_OUT_OF_RANGE", rejected["000002"])

    def test_rejection_reasons_fail_closed_on_delayed_snapshot(self):
        with self.assertRaisesRegex(ValueError, "delayed"):
            ClosingBetEngine().rejection_reasons(snapshot(quote(), delayed=True))

    def test_keeps_only_one_candidate_per_theme(self):
        first = quote(code="111111", name="A", theme="battery")
        second = quote(code="222222", name="B", theme="battery", trading_value=30_000_000_000)
        decision = ClosingBetEngine().evaluate(snapshot(first, second), cash=600_000)
        self.assertEqual(1, len(decision.candidates))

    def test_append_only_ledger_rejects_duplicate_schedule(self):
        decision = ClosingBetEngine().evaluate(snapshot(quote()), cash=600_000)
        with tempfile.TemporaryDirectory() as directory:
            ledger = JsonlLedger(Path(directory) / "events.jsonl")
            ledger.append(decision)
            with self.assertRaises(DuplicateDecisionError):
                ledger.append(decision)
            self.assertEqual(1, len(ledger.read_all()))

    def test_delayed_snapshot_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "delayed"):
            ClosingBetEngine().evaluate(snapshot(quote(), delayed=True), cash=600_000)

    def test_overheated_rsi_is_rejected(self):
        decision = ClosingBetEngine().evaluate(
            snapshot(quote(rsi14=86.0, vwap=19_700)), cash=600_000
        )
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)

    def test_catalyst_is_scored_not_required(self):
        engine = ClosingBetEngine()
        verified = engine.rank_candidates(snapshot(quote()))[0]
        unverified = engine.rank_candidates(snapshot(quote(catalyst_verified=False)))[0]
        missing = engine.rank_candidates(snapshot(quote(catalyst="", catalyst_score=0.0)))[0]
        # Verified: 0.8 * 6 + 4; unverified keeps only the theme score; none adds nothing.
        self.assertAlmostEqual(4.0, verified.score - unverified.score)
        self.assertAlmostEqual(4.8, unverified.score - missing.score)
        self.assertIn("CATALYST_CONFIRMED", verified.reasons)
        self.assertNotIn("CATALYST_CONFIRMED", unverified.reasons)
        self.assertIn("CATALYST_UNKNOWN", unverified.risks)
        self.assertIn("CATALYST_UNKNOWN", missing.risks)
        decision = engine.evaluate(snapshot(quote(catalyst="", catalyst_score=0.0)), cash=600_000)
        self.assertEqual(DecisionType.BUY, decision.decision)

    def test_score_is_normalized_to_one_hundred(self):
        strong = quote(
            rsi14=64.0,
            vwap=19_600,
            five_min_volume_ratio=3.0,
            last_hour_return_pct=2.0,
            higher_lows=True,
            breakout_level=19_850,
            breakout_holds=True,
            recent_resistance=19_850,
        )
        candidate = ClosingBetEngine().rank_candidates(snapshot(strong))[0]
        self.assertGreaterEqual(candidate.score, 0.0)
        self.assertLessEqual(candidate.score, 100.0)

    def test_breakout_hold_receives_higher_chart_score(self):
        breakout = quote(
            code="111111",
            name="돌파",
            theme="robot",
            rsi14=64.0,
            vwap=19_600,
            five_min_volume_ratio=1.8,
            last_hour_return_pct=1.2,
            higher_lows=True,
            breakout_level=19_850,
            breakout_holds=True,
            recent_resistance=19_850,
        )
        plain = quote(
            code="222222",
            name="평범",
            theme="battery",
            rsi14=64.0,
            vwap=19_600,
            five_min_volume_ratio=1.1,
            last_hour_return_pct=0.1,
            higher_lows=False,
            breakout_level=20_300,
            breakout_holds=False,
            recent_resistance=20_200,
        )
        decision = ClosingBetEngine().evaluate(snapshot(plain, breakout), cash=600_000)
        self.assertEqual("111111", decision.candidates[0].quote.code)

    def test_market_specific_crash_rejects_only_exposed_market(self):
        kosdaq_quote = quote(market="KOSDAQ")
        kospi_quote = quote(code="222222", name="코스피", theme="battery", market="KOSPI")
        snap = MarketSnapshot(
            captured_at=datetime(2026, 10, 6, 15, 20, 30, tzinfo=KST),
            session=Session.KRX_1520,
            kospi_change_pct=0.2,
            kosdaq_change_pct=-3.2,
            quotes=(kosdaq_quote, kospi_quote),
            source="fixture",
        )
        ranked = ClosingBetEngine().rank_candidates(snap)
        self.assertEqual(["222222"], [candidate.quote.code for candidate in ranked])

    def test_weak_market_reduces_score_and_records_risk(self):
        normal = ClosingBetEngine().rank_candidates(snapshot(quote()))[0]
        weak_snapshot = MarketSnapshot(
            captured_at=datetime(2026, 10, 6, 15, 20, 30, tzinfo=KST),
            session=Session.KRX_1520,
            kospi_change_pct=-2.0,
            kosdaq_change_pct=0.5,
            quotes=(quote(),),
            source="fixture",
        )
        weak = ClosingBetEngine().rank_candidates(weak_snapshot)[0]
        self.assertLess(weak.score, normal.score)
        self.assertIn("MARKET_WEAKNESS", weak.risks)


if __name__ == "__main__":
    unittest.main()
