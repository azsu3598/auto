from __future__ import annotations

import json
from dataclasses import replace
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_automation.config import StrategyConfig
from stock_automation.dart import BLOCKING_RISK_FLAGS
from unittest.mock import patch

from stock_automation.engine import ClosingBetEngine
from stock_automation.learning import TunableParameters, apply_parameters
from stock_automation.medium_term import MediumTermEngine
from stock_automation.risk import build_position_plan
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
        # 3% of the price: closing-v0.4 ATR stops equal the old fixed-ratio stops here.
        atr14=600.0,
        # The Kiwoom path always fills these; the values equal the old fallbacks
        # (5-minute MA20, daily volume ratio) so default scores are unchanged.
        vwap=19_700,
        five_min_volume_ratio=1.8,
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
        # Verified: 0.8 * 6 + 4. closing-v0.4: an unverified theme score adds nothing.
        self.assertAlmostEqual(8.8, verified.score - unverified.score)
        self.assertAlmostEqual(0.0, unverified.score - missing.score)
        self.assertIn("CATALYST_CONFIRMED", verified.reasons)
        self.assertNotIn("CATALYST_CONFIRMED", unverified.reasons)
        self.assertIn("CATALYST_UNKNOWN", unverified.risks)
        self.assertIn("CATALYST_UNKNOWN", missing.risks)
        decision = engine.evaluate(snapshot(quote(catalyst="", catalyst_score=0.0)), cash=600_000)
        self.assertEqual(DecisionType.BUY, decision.decision)

    def test_dart_risk_disclosure_blocks_entry(self):
        engine = ClosingBetEngine()
        for flag in sorted(BLOCKING_RISK_FLAGS):
            risky = quote(warnings=(f"DART_{flag}",))
            self.assertEqual("DART_RISK_DISCLOSURE", engine.rejection_reason(snapshot(risky), risky))
            self.assertEqual(DecisionType.NO_TRADE, engine.evaluate(snapshot(risky), cash=600_000).decision)
        # Only blocking DART flags reject; other warnings keep their old meaning.
        for warnings in (("DART_OTHER",), ("AUDIT_RISK",), ("CATALYST_UNKNOWN",)):
            kept = quote(warnings=warnings)
            self.assertIsNone(engine.rejection_reason(snapshot(kept), kept))

    def test_missing_dart_check_blocks_entry(self):
        engine = ClosingBetEngine()
        unchecked = quote(warnings=("DART_NOT_CHECKED",))
        self.assertEqual("DART_NOT_CHECKED", engine.rejection_reason(snapshot(unchecked), unchecked))
        self.assertEqual(
            DecisionType.NO_TRADE, engine.evaluate(snapshot(unchecked), cash=600_000).decision
        )

    def test_closing_bet_blocks_the_same_risks_as_medium_term(self):
        self.assertEqual(set(BLOCKING_RISK_FLAGS), MediumTermEngine.BLOCKING_RISKS)

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


class ClosingV04Tests(unittest.TestCase):
    """closing-v0.4: ATR stops, verified-only catalyst points, missing intraday data."""

    def test_large_atr_sizes_the_position_from_the_wider_stop(self):
        decision = ClosingBetEngine().evaluate(snapshot(quote(atr14=1_200.0)), cash=600_000)
        self.assertEqual(DecisionType.BUY, decision.decision)
        self.assertEqual(19_400, decision.position.stop_price)  # 0.5 * ATR below 20,000
        self.assertEqual(18_800, decision.position.emergency_stop)
        self.assertEqual(8, decision.position.quantity)
        self.assertLessEqual(
            (decision.position.entry_price - decision.position.emergency_stop)
            * decision.position.quantity,
            10_000,
        )

    def test_stop_wider_than_the_limit_is_recorded_as_stop_too_wide(self):
        # A lone too-wide candidate is filtered before ranking, so nothing qualifies.
        q = quote(support_price=18_800)
        engine = ClosingBetEngine()
        self.assertEqual({q.code: "STOP_TOO_WIDE"}, engine.rejection_reasons(snapshot(q)))
        decision = engine.evaluate(snapshot(q), cash=600_000)
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)
        self.assertEqual(("NO_QUALIFYING_CANDIDATE",), decision.reason_codes)
        self.assertIsNone(decision.position)
        self.assertEqual(600_000, decision.remaining_cash)

    def test_too_wide_top_scorer_is_skipped_for_the_next_candidate(self):
        engine = ClosingBetEngine()
        wide = quote(code="111111", theme="robot", support_price=18_800)
        normal = quote(code="222222", theme="bio", trading_value=12_000_000_000)
        # Without the stop check the wide quote outranks the normal one.
        unfiltered = {
            c.quote.code: c.score
            for c in (engine._score_quote(snapshot(wide), replace(wide, support_price=19_400)),
                      engine._score_quote(snapshot(normal), normal))
        }
        self.assertGreater(unfiltered["111111"], unfiltered["222222"])
        snap = snapshot(wide, normal)
        self.assertEqual({"111111": "STOP_TOO_WIDE"}, engine.rejection_reasons(snap))
        self.assertEqual(["222222"], [c.quote.code for c in engine.rank_candidates(snap)])
        decision = engine.evaluate(snap, cash=600_000)
        self.assertEqual(DecisionType.BUY, decision.decision)
        self.assertEqual("222222", decision.position.code)
        self.assertLessEqual(
            (decision.position.entry_price - decision.position.emergency_stop)
            * decision.position.quantity,
            10_000,
        )

    def test_missing_atr_is_a_hard_filter(self):
        engine = ClosingBetEngine()
        for atr14 in (None, 0.0):
            q = quote(atr14=atr14)
            self.assertEqual("ATR_UNAVAILABLE", engine.rejection_reason(snapshot(q), q))
            decision = engine.evaluate(snapshot(q), cash=600_000)
            self.assertEqual(DecisionType.NO_TRADE, decision.decision)
            self.assertIsNone(decision.position)

    def test_unverified_theme_score_adds_no_points(self):
        engine = ClosingBetEngine()
        strong = engine.rank_candidates(
            snapshot(quote(catalyst_verified=False, catalyst_score=1.0))
        )[0]
        none = engine.rank_candidates(
            snapshot(quote(catalyst_verified=False, catalyst_score=0.0))
        )[0]
        self.assertAlmostEqual(none.score, strong.score)

    def test_verified_catalyst_keeps_its_points(self):
        engine = ClosingBetEngine()
        verified = engine.rank_candidates(snapshot(quote(catalyst_score=1.0)))[0]
        missing = engine.rank_candidates(snapshot(quote(catalyst="", catalyst_score=0.0)))[0]
        self.assertAlmostEqual(6.0 + 4.0, verified.score - missing.score)

    def test_missing_vwap_earns_no_vwap_points(self):
        engine = ClosingBetEngine()
        known = engine.rank_candidates(snapshot(quote()))[0]
        unknown = engine.rank_candidates(snapshot(quote(vwap=None)))[0]
        # The hard filter still checks the 5-minute MA20 in place of the VWAP.
        self.assertAlmostEqual(5.0, known.score - unknown.score)
        self.assertIn("ABOVE_VWAP", known.reasons)
        self.assertNotIn("ABOVE_VWAP", unknown.reasons)
        self.assertIn("VWAP_UNKNOWN", unknown.risks)
        self.assertNotIn("VWAP_UNKNOWN", known.risks)

    def test_missing_intraday_volume_does_not_reuse_the_daily_ratio(self):
        engine = ClosingBetEngine()
        flat = engine.rank_candidates(snapshot(quote(five_min_volume_ratio=1.0)))[0]
        unknown = engine.rank_candidates(snapshot(quote(five_min_volume_ratio=None)))[0]
        self.assertAlmostEqual(flat.score, unknown.score)
        self.assertIn("INTRADAY_VOLUME_UNKNOWN", unknown.risks)
        self.assertNotIn("INTRADAY_VOLUME_UNKNOWN", flat.risks)


def market(snap: MarketSnapshot, kospi: float) -> MarketSnapshot:
    return replace(snap, kospi_change_pct=kospi)


def engine_at(score: float, snap: MarketSnapshot) -> ClosingBetEngine:
    """An engine whose minimum_score puts the snapshot's top quote at ``score`` on a 60 scale.

    Scores come from the full formula, so the test moves the threshold instead:
    "score 65" means 5 points above minimum_score, as with the default of 60.
    """
    actual = ClosingBetEngine().rank_candidates(snap)[0].score
    return ClosingBetEngine(StrategyConfig(minimum_score=actual - (score - 60.0)))


class ClosingV05TierTests(unittest.TestCase):
    """closing-v0.5: FULL / CONDITIONAL tiers; CONDITIONAL buys at half size."""

    def evaluate(self, engine: ClosingBetEngine, snap: MarketSnapshot):
        with patch(
            "stock_automation.engine.build_position_plan", wraps=build_position_plan
        ) as sizing:
            decision = engine.evaluate(snap, cash=600_000)
        return decision, sizing

    def test_full_tier_buys_at_normal_size(self):
        snap = market(snapshot(quote()), -0.5)
        decision, sizing = self.evaluate(engine_at(65.0, snap), snap)
        self.assertEqual(DecisionType.BUY, decision.decision)
        self.assertEqual("FULL", decision.candidates[0].tier)
        self.assertEqual(
            ("TOP_SCORE_SELECTED", "TIER_FULL", "PAPER_EXECUTION_ONLY"), decision.reason_codes
        )
        self.assertEqual(10_000, sizing.call_args.kwargs["max_loss"])
        self.assertAlmostEqual(0.40, sizing.call_args.kwargs["max_allocation_pct"])
        self.assertEqual(11, decision.position.quantity)  # unchanged from closing-v0.4

    def test_unverified_catalyst_is_conditional_at_half_size(self):
        snap = snapshot(quote(catalyst_verified=False))
        decision, sizing = self.evaluate(engine_at(65.0, snap), snap)
        self.assertEqual(DecisionType.BUY, decision.decision)
        self.assertEqual("CONDITIONAL", decision.candidates[0].tier)
        self.assertEqual(("CATALYST_UNKNOWN",), decision.candidates[0].tier_reasons)
        self.assertIn("TIER_CONDITIONAL", decision.reason_codes)
        self.assertEqual(5_000, sizing.call_args.kwargs["max_loss"])
        self.assertAlmostEqual(0.20, sizing.call_args.kwargs["max_allocation_pct"])
        p = decision.position
        self.assertLessEqual((p.entry_price - p.emergency_stop) * p.quantity, 5_000)
        self.assertLessEqual(p.invested_amount, 120_000)
        self.assertIn("CATALYST_UNKNOWN", decision.notes)
        self.assertIn("max loss 5,000 KRW", decision.notes)
        self.assertEqual("CONDITIONAL", decision.to_dict()["candidates"][0]["tier"])

    def test_weak_market_is_conditional(self):
        snap = market(snapshot(quote()), -1.5)
        decision, sizing = self.evaluate(engine_at(65.0, snap), snap)
        self.assertEqual("CONDITIONAL", decision.candidates[0].tier)
        self.assertEqual(("MARKET_WEAKNESS",), decision.candidates[0].tier_reasons)
        self.assertIn("TIER_CONDITIONAL", decision.reason_codes)
        self.assertEqual(5_000, sizing.call_args.kwargs["max_loss"])

    def test_score_within_the_margin_is_conditional(self):
        snap = snapshot(quote())
        decision, _ = self.evaluate(engine_at(55.0, snap), snap)
        self.assertEqual(DecisionType.BUY, decision.decision)
        self.assertEqual(("SCORE_BELOW_MINIMUM",), decision.candidates[0].tier_reasons)
        self.assertIn("TIER_CONDITIONAL", decision.reason_codes)

    def test_score_below_the_conditional_threshold_is_no_trade(self):
        snap = snapshot(quote())
        decision, _ = self.evaluate(engine_at(49.0, snap), snap)
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)
        self.assertEqual(("NO_QUALIFYING_CANDIDATE",), decision.reason_codes)
        self.assertEqual("", decision.candidates[0].tier)
        self.assertIsNone(decision.position)

    def test_full_is_selected_over_a_higher_scoring_conditional(self):
        full = quote(
            code="111111",
            theme="robot",
            institution_net=None,
            program_net=None,
            five_min_volume_ratio=1.0,
            recent_resistance=20_100,  # under 1.2% room: -8
        )
        conditional = quote(code="222222", theme="bio", catalyst_verified=False)
        snap = snapshot(full, conditional)
        engine = engine_at(61.0, snapshot(full))
        ranked = {c.quote.code: c for c in engine.rank_candidates(snap)}
        self.assertEqual("FULL", ranked["111111"].tier)
        self.assertEqual("CONDITIONAL", ranked["222222"].tier)
        self.assertGreater(ranked["222222"].score, ranked["111111"].score)
        decision = engine.evaluate(snap, cash=600_000)
        self.assertEqual("111111", decision.position.code)
        self.assertIn("TIER_FULL", decision.reason_codes)

    def test_conditional_size_below_one_share_is_position_size_zero(self):
        def expensive(**overrides):
            return quote(
                price=148_000, open_price=140_600, high_price=148_740, low_price=139_860,
                ma5=143_560, ma20=139_860, ma120=125_800, five_min_ma20=145_780,
                support_price=143_560, atr14=4_440.0, vwap=145_780,
                best_ask=148_000, best_bid=147_900, **overrides,
            )
        # Half allocation is 120,000 KRW, under one 148,000 KRW share.
        decision = ClosingBetEngine().evaluate(
            snapshot(expensive(catalyst_verified=False)), cash=600_000
        )
        self.assertEqual("CONDITIONAL", decision.candidates[0].tier)
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)
        self.assertEqual(("POSITION_SIZE_ZERO",), decision.reason_codes)
        full = ClosingBetEngine().evaluate(snapshot(expensive()), cash=600_000)
        self.assertEqual(DecisionType.BUY, full.decision)
        self.assertEqual(1, full.position.quantity)

    def test_hard_filter_rejection_gets_no_tier(self):
        engine = ClosingBetEngine(StrategyConfig(minimum_score=0.0))
        q = quote(vwap=20_500)  # below the VWAP
        snap = snapshot(q)
        self.assertEqual({q.code: "BELOW_VWAP"}, engine.rejection_reasons(snap))
        self.assertIsNone(engine._score_quote(snap, q))
        self.assertEqual((), engine.rank_candidates(snap))
        decision = engine.evaluate(snap, cash=600_000)
        self.assertEqual(DecisionType.NO_TRADE, decision.decision)
        self.assertEqual((), decision.candidates)

    def test_conditional_threshold_follows_the_learned_minimum_score(self):
        base = StrategyConfig()
        learned = apply_parameters(
            base,
            TunableParameters(
                minimum_score=55.0,
                minimum_close_strength=base.minimum_close_strength,
                minimum_volume_ratio=base.minimum_volume_ratio,
                maximum_day_gain_pct=base.maximum_day_gain_pct,
                maximum_ma5_distance_pct=base.maximum_ma5_distance_pct,
            ),
        )
        self.assertEqual(10.0, learned.conditional_score_margin)
        engine = ClosingBetEngine(learned)
        self.assertEqual("FULL", engine._tier(55.0, True, 0.2)[0])
        self.assertEqual("CONDITIONAL", engine._tier(45.0, True, 0.2)[0])
        self.assertEqual("", engine._tier(44.99, True, 0.2)[0])
        self.assertEqual("", ClosingBetEngine(base)._tier(45.0, True, 0.2)[0])

    def test_tier_is_visible_in_ledger_report_dashboard_and_alert(self):
        from stock_automation.dashboard import _event_reasons
        from stock_automation.notifications import _render_trade_message
        from stock_automation.reporting import append_training_event, write_markdown_report

        snap = snapshot(quote(catalyst_verified=False))
        decision = engine_at(65.0, snap).evaluate(snap, cash=600_000)
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "events.csv"
            append_training_event(csv_path, snap, decision)
            self.assertIn("TIER_CONDITIONAL", csv_path.read_text(encoding="utf-8"))
            report = write_markdown_report(directory, snap, decision).read_text(encoding="utf-8")
        self.assertIn("- 추천 등급: CONDITIONAL (CATALYST_UNKNOWN)", report)
        payload = decision.to_dict()
        labels = _event_reasons({}, payload, payload["position"])
        self.assertEqual(["종가배팅 종합점수 1위", "조건부 등급(절반 크기)", "재료 미확인"], labels[:3])
        alert = _render_trade_message(
            "[모의매수] 테스트",
            {"reason_codes": ["TOP_SCORE_SELECTED", "TIER_CONDITIONAL", "CATALYST_UNKNOWN"]},
            maximum_characters=1_000,
        )
        self.assertIn("사유: 종가배팅 종합점수 1위, 조건부 등급(절반 크기), 재료 미확인", alert)


if __name__ == "__main__":
    unittest.main()
