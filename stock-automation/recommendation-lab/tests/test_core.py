import copy
from datetime import timedelta
import unittest

from core import DataBlocked, analyze, timestamp
from fixtures import NOW, quote, snapshot


class ResearchCoreTests(unittest.TestCase):
    def test_candidate_is_research_not_order_or_fill(self):
        result = analyze(snapshot(), now=NOW)
        self.assertEqual(result["status"], "CANDIDATES")
        self.assertEqual(result["purpose"], "RESEARCH_ONLY")
        self.assertIs(result["order_submission"], False)
        self.assertIs(result["ledger_mutation"], False)
        self.assertTrue(result["is_sample"])
        self.assertNotIn("position", result)
        self.assertNotIn("actual_entry", result)

    def test_no_trade_is_successful_rejection_with_all_cash(self):
        result = analyze(snapshot([quote(trading_value_krw=1)]), now=NOW)
        self.assertEqual(result["status"], "NO_TRADE")
        self.assertEqual(result["allocated_krw"], 0)
        self.assertEqual(result["remaining_cash_krw"], 600000)
        self.assertEqual(result["excluded"][0]["reason"], "LOW_TRADING_VALUE")

    def test_incomplete_scan_is_blocked_not_no_trade(self):
        with self.assertRaises(DataBlocked): analyze(snapshot(universe_complete=False), now=NOW)

    def test_previous_recommendation_universe_is_not_accepted(self):
        with self.assertRaises(DataBlocked): analyze(snapshot(universe_basis="PREVIOUS_RECOMMENDATIONS"), now=NOW)

    def test_naive_stale_future_and_delayed_data_block(self):
        for changes in [
            {"observed_at": NOW.replace(tzinfo=None).isoformat()},
            {"observed_at": (NOW - timedelta(seconds=91)).isoformat()},
            {"observed_at": (NOW + timedelta(seconds=3)).isoformat()},
            {"delayed": True}, {"flow_at": None}, {"technical_complete": False},
        ]:
            with self.subTest(changes=changes), self.assertRaises(DataBlocked):
                analyze(snapshot([quote(**changes)]), now=NOW)

    def test_nonfinite_boolean_prices_and_invalid_risk_levels_block(self):
        for changes in [{"price": float("nan")}, {"price": True}, {"ma20": float("inf")},
                        {"emergency_floor": 12300}, {"target1": 12000}, {"low": 12600},
                        {"levels_tick_validated": False}]:
            with self.subTest(changes=changes), self.assertRaises(DataBlocked):
                analyze(snapshot([quote(**changes)]), now=NOW)

    def test_unverified_or_expired_news_blocks(self):
        for changes in [{"verified": False}, {"url": "javascript:alert(1)"},
                        {"published_at": (NOW - timedelta(days=2)).isoformat()},
                        {"verified_at": (NOW + timedelta(seconds=3)).isoformat()}]:
            q = quote(); q["catalyst"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(DataBlocked):
                analyze(snapshot([q]), now=NOW)

    def test_foreign_flow_never_enters_screening(self):
        with self.assertRaises(DataBlocked): analyze(snapshot([quote(foreign_net=100)]), now=NOW)

    def test_unknown_venue_or_nxt_eligibility_blocks(self):
        for changes in [{"venue": "UNKNOWN"}, {"venue": "NXT", "nxt_eligible": False}, {"nxt_eligible": None}]:
            with self.subTest(changes=changes), self.assertRaises(DataBlocked):
                analyze(snapshot([quote(**changes)]), now=NOW)

    def test_verified_nxt_is_not_automatically_excluded(self):
        result = analyze(snapshot([quote(venue="NXT", nxt_eligible=True)]), now=NOW)
        self.assertEqual(result["candidates"][0]["venue"], "NXT")

    def test_duplicate_symbols_block_instead_of_double_allocation(self):
        with self.assertRaises(DataBlocked): analyze(snapshot([quote(), quote()]), now=NOW)

    def test_theme_and_correlated_group_limit(self):
        for field in ["theme", "risk_group"]:
            quotes = [quote("DEMO_A", **{field: "same"}), quote("DEMO_B", **{field: "same"})]
            result = analyze(snapshot(quotes), now=NOW)
            self.assertEqual(len(result["candidates"]), 1)

    def test_portfolio_count_capital_and_loss_limits(self):
        result = analyze(snapshot([quote("DEMO_" + str(i)) for i in range(5)]), now=NOW)
        self.assertLessEqual(len(result["candidates"]), 3)
        self.assertLessEqual(result["planned_emergency_loss_krw"], 10000)
        self.assertGreater(result["remaining_cash_krw"], 0)
        self.assertEqual(result["remaining_cash_krw"] + result["allocated_krw"], 600000)
        for c in result["candidates"]:
            self.assertEqual(c["allocation_krw"], c["entry_high"] * c["suggested_quantity"])
            self.assertLess(c["emergency_stop"], c["stop_price"])

    def test_market_shock_excludes_rather_than_forcing_recommendation(self):
        s = snapshot(); s["market"]["kospi_pct"] = -3
        result = analyze(s, now=NOW)
        self.assertEqual(result["status"], "NO_TRADE")
        self.assertEqual(result["excluded"][0]["reason"], "MARKET_SHOCK")

    def test_extensions_weak_flow_and_unfavorable_risk_are_rejected(self):
        for changes in [{"day_change_pct": 20}, {"institution_net_krw": -1},
                        {"five_min_slope": -1}, {"target1": 12600}, {"volume_ratio": 1.0}]:
            with self.subTest(changes=changes):
                result = analyze(snapshot([quote(**changes)]), now=NOW)
                self.assertEqual(result["status"], "NO_TRADE")

    def test_oldest_required_component_limits_result_expiry(self):
        q = quote(flow_at=(NOW - timedelta(seconds=85)).isoformat())
        result = analyze(snapshot([q]), now=NOW)
        self.assertLessEqual(timestamp(result["expires_at"]), NOW + timedelta(seconds=5))

    def test_input_is_not_mutated(self):
        data = snapshot(); before = copy.deepcopy(data)
        analyze(data, now=NOW); self.assertEqual(data, before)

    def test_bad_research_budgets_block(self):
        for capital in [True, 0, 700001, 600000.0]:
            with self.subTest(capital=capital), self.assertRaises(DataBlocked):
                analyze(snapshot(), now=NOW, capital=capital)


if __name__ == "__main__": unittest.main()
