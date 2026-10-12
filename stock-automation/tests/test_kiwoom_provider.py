from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from stock_automation.models import Session
from stock_automation.providers.kiwoom import Catalyst, KiwoomSnapshotBuilder

KST = timezone(timedelta(hours=9))


class Response:
    def __init__(self, body):
        self.body = body
        self.continuation = SimpleNamespace(cont_yn="N", next_key=None)


class FakeClient:
    def fetch_page(self, *, api_id, path, body, cont_yn=None, next_key=None):
        if api_id == "ka10099":
            if body["mrkt_tp"] == "0":
                return Response({"return_code": 0, "list": [{"code": "123456", "name": "테스트", "nxtEnable": "N"}]})
            return Response({"return_code": 0, "list": []})
        if api_id == "ka10032":
            return Response({
                "return_code": 0,
                "trde_prica_upper": [{
                    "stk_cd": "123456", "stk_nm": "테스트", "cur_prc": "+20000",
                    "flu_rt": "+5.00", "now_trde_qty": "1800000",
                    "pred_trde_qty": "1000000", "trde_prica": "36000",
                }],
            })
        if api_id == "ka10007":
            asks = {f"sel_{i}bid_req": "100" for i in range(1, 11)}
            bids = {f"buy_{i}bid_req": "90" for i in range(1, 11)}
            return Response({
                "return_code": 0, "stk_nm": "테스트", "stk_cd": "123456",
                "date": "20261006", "tm": "152030", "cur_prc": "+20000",
                "open_pric": "+19000", "high_pric": "+20100", "low_pric": "+18900",
                "trde_qty": "1800000", "trde_prica": "36000",
                "pred_trde_qty": "1000000", "flu_rt": "+5.00",
                "sel_1bid": "+20010", "buy_1bid": "+20000", **asks, **bids,
            })
        if api_id == "ka10001":
            return Response({
                "return_code": 0, "stk_cd": "123456", "stk_nm": "테스트",
                "cur_prc": "+20000", "mac": "8000", "per": "12.0",
                "pbr": "1.5", "roe": "14.0", "sale_amt": "12000",
                "bus_pro": "1100", "cup_nga": "800",
            })
        if api_id == "ka10081":
            rows = []
            for index in range(140):
                close = 20_000 - index * 10
                rows.append({
                    "dt": f"{20261006-index:08d}", "cur_prc": str(close),
                    "open_pric": str(close - 100), "high_pric": str(close + 100),
                    "low_pric": str(close - 300), "trde_qty": "1000000",
                    "trde_prica": "20000",
                })
            return Response({"return_code": 0, "stk_dt_pole_chart_qry": rows})
        if api_id == "ka10080":
            rows = []
            for index in range(25):
                close = 19_500 + index * 20
                rows.append({
                    "cntr_tm": f"2026100613{index:02d}00", "cur_prc": str(close),
                    "open_pric": str(close - 10), "high_pric": str(close + 20),
                    "low_pric": str(close - 20), "trde_qty": "1000",
                })
            return Response({"return_code": 0, "stk_min_pole_chart_qry": rows})
        if api_id == "ka90001":
            return Response({
                "return_code": 0,
                "thema_grp": [
                    {
                        "thema_grp_cd": "T01", "thema_nm": "로봇", "flu_rt": "+3.20",
                        "rising_stk_num": "8", "fall_stk_num": "2",
                    }
                ],
            })
        if api_id == "ka90002":
            return Response({
                "return_code": 0,
                "thema_comp_stk": [{"stk_cd": "123456", "stk_nm": "테스트"}],
            })
        if api_id == "ka90009":
            return Response({
                "return_code": 0,
                "frgnr_orgn_trde_upper": [{
                    "orgn_netprps_stk_cd": "123456",
                    "orgn_netprps_amt": "+12",
                    "orgn_netslmt_stk_cd": "654321",
                    "orgn_netslmt_amt": "7",
                }],
            })
        if api_id == "ka90004":
            return Response({
                "return_code": 0,
                "stk_prm_trde_prst": [{
                    "stk_cd": "123456", "netprps_prica": "+35",
                }],
            })
        raise AssertionError(api_id)


class LaterQuoteClient(FakeClient):
    def fetch_page(self, *, api_id, path, body, cont_yn=None, next_key=None):
        response = super().fetch_page(
            api_id=api_id, path=path, body=body, cont_yn=cont_yn, next_key=next_key
        )
        if api_id == "ka10007":
            response.body["tm"] = "152100"
        return response


class MixedSessionClient(FakeClient):
    def fetch_page(self, *, api_id, path, body, cont_yn=None, next_key=None):
        response = super().fetch_page(
            api_id=api_id, path=path, body=body, cont_yn=cont_yn, next_key=next_key
        )
        if api_id == "ka10080":
            response.body["stk_min_pole_chart_qry"].append({
                "cntr_tm": "20261005153000",
                "cur_prc": "100000",
                "open_pric": "100000",
                "high_pric": "100000",
                "low_pric": "100000",
                "trde_qty": "999999999",
            })
        return response


class FlowFailureClient(FakeClient):
    def fetch_page(self, *, api_id, path, body, cont_yn=None, next_key=None):
        if api_id in {"ka90009", "ka90004"}:
            raise RuntimeError("optional flow API unavailable")
        return super().fetch_page(
            api_id=api_id, path=path, body=body, cont_yn=cont_yn, next_key=next_key
        )


class KiwoomProviderTests(unittest.TestCase):
    def test_optional_flow_failure_is_unknown_instead_of_estimated(self):
        snapshot = KiwoomSnapshotBuilder(FlowFailureClient()).build(
            captured_at=datetime(2026, 10, 6, 15, 20, 30, tzinfo=KST),
            session=Session.KRX_1520,
            catalysts={"123456": Catalyst("robot", "confirmed contract", 0.8, True)},
            kospi_change_pct=0.2,
            kosdaq_change_pct=0.5,
        )
        quote = snapshot.quotes[0]
        self.assertIsNone(quote.institution_net)
        self.assertIsNone(quote.program_net)
        self.assertIn("INSTITUTION_FLOW_NOT_CONFIRMED", quote.warnings)
        self.assertIn("PROGRAM_FLOW_NOT_CONFIRMED", quote.warnings)

    def test_entry_can_revalidate_only_the_recorded_shortlist(self):
        snapshot = KiwoomSnapshotBuilder(FakeClient()).build(
            captured_at=datetime(2026, 10, 6, 15, 20, 30, tzinfo=KST),
            session=Session.KRX_1520,
            catalysts={},
            kospi_change_pct=0.2,
            kosdaq_change_pct=0.5,
            candidate_codes=(),
        )
        self.assertEqual((), snapshot.quotes)

    def test_snapshot_cutoff_advances_to_latest_verified_quote(self):
        started_at = datetime(2026, 10, 6, 15, 20, 0, tzinfo=KST)
        snapshot = KiwoomSnapshotBuilder(LaterQuoteClient()).build(
            captured_at=started_at,
            session=Session.KRX_1520,
            catalysts={"123456": Catalyst("robot", "confirmed contract", 0.8, True)},
            kospi_change_pct=0.2,
            kosdaq_change_pct=0.5,
        )
        self.assertEqual(datetime(2026, 10, 6, 15, 21, tzinfo=KST), snapshot.captured_at)

    def test_medium_term_candidate_codes_are_pre_filtered_for_nxt(self):
        codes = KiwoomSnapshotBuilder(FakeClient()).medium_term_candidate_codes(40)
        self.assertEqual(("123456",), codes)

    def test_builds_current_quote_from_documented_endpoints(self):
        builder = KiwoomSnapshotBuilder(FakeClient())
        snapshot = builder.build(
            captured_at=datetime(2026, 10, 6, 15, 20, 30, tzinfo=KST),
            session=Session.KRX_1520,
            catalysts={"123456": Catalyst("robot", "confirmed contract", 0.8, True)},
            kospi_change_pct=0.2,
            kosdaq_change_pct=0.5,
        )
        self.assertEqual(1, len(snapshot.quotes))
        quote = snapshot.quotes[0]
        self.assertEqual(20_000, quote.price)
        self.assertEqual(20_010, quote.best_ask)
        self.assertEqual(36_000_000_000, quote.trading_value)
        self.assertGreater(quote.five_min_ma20_slope, 0)
        self.assertFalse(quote.nxt_eligible)
        self.assertEqual("confirmed contract", quote.catalyst)
        self.assertTrue(quote.catalyst_verified)
        self.assertEqual("KOSPI", quote.market)
        self.assertEqual(120_000_000, quote.institution_net)
        self.assertEqual(35_000_000, quote.program_net)

    def test_same_session_vwap_excludes_previous_day_bars(self):
        snapshot = KiwoomSnapshotBuilder(MixedSessionClient()).build(
            captured_at=datetime(2026, 10, 6, 15, 20, 30, tzinfo=KST),
            session=Session.KRX_1520,
            catalysts={"123456": Catalyst("robot", "confirmed contract", 0.8, True)},
            kospi_change_pct=0.2,
            kosdaq_change_pct=0.5,
        )
        self.assertLess(snapshot.quotes[0].vwap, 21_000)

    def test_builds_chart_context_from_kiwoom_theme_breadth(self):
        context = KiwoomSnapshotBuilder(FakeClient()).theme_context(session=Session.KRX_1520)
        self.assertIn("123456", context)
        self.assertEqual("로봇", context["123456"].theme)
        self.assertIn("상승 8/하락 2", context["123456"].summary)
        self.assertGreater(context["123456"].score, 0)
        self.assertFalse(context["123456"].verified)

    def test_builds_separate_medium_term_snapshot_with_documented_units(self):
        captured_at = datetime(2026, 10, 6, 17, 0, tzinfo=KST)
        result = KiwoomSnapshotBuilder(FakeClient()).build_medium_term_snapshot(
            captured_at=captured_at,
            disclosure_overlays={
                "123456": {
                    "checked_at": captured_at.isoformat(),
                    "risk_flags": [],
                    "catalyst": "실적 추세 확인",
                }
            },
        )

        self.assertEqual(1, len(result.quotes))
        quote = result.quotes[0]
        self.assertEqual(36_000_000_000, quote.trading_value)
        self.assertEqual(800_000_000_000, quote.market_cap)
        self.assertEqual(1_200_000_000_000, quote.sales)
        self.assertTrue(quote.disclosure_checked)
        self.assertGreater(quote.ma20_slope_5d, 0)


if __name__ == "__main__":
    unittest.main()
