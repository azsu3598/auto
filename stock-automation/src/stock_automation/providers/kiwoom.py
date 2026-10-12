from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from ..indicators import Bar, atr, compute_features, rsi, sma
from ..medium_term import MediumTermQuote, MediumTermSnapshot
from ..models import MarketSnapshot, Quote, Session

KST = timezone(timedelta(hours=9))


class ApiResponse(Protocol):
    body: dict[str, Any]
    continuation: Any


class KiwoomClient(Protocol):
    def fetch_page(
        self,
        *,
        api_id: str,
        path: str,
        body: dict[str, str],
        cont_yn: str | None = None,
        next_key: str | None = None,
    ) -> ApiResponse: ...


@dataclass(frozen=True, slots=True)
class Catalyst:
    theme: str
    summary: str
    score: float
    verified: bool = False


def _number(value: Any, *, signed: bool = False) -> float:
    if value is None or value == "":
        return 0.0
    text = str(value).strip().replace(",", "")
    if not signed:
        text = text.lstrip("+-")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"invalid numeric API value: {value!r}") from exc


def _records(value: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, (list, tuple)):
            result.append(dict(zip(keys, item)))
    return result


def _optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class KiwoomSnapshotBuilder:
    """Builds a fail-closed engine snapshot from documented Kiwoom REST endpoints.

    News/theme classification is intentionally injected. Missing catalyst evidence gets
    score zero and will be rejected by the strategy engine.
    """

    def __init__(self, client: KiwoomClient, *, max_pages: int = 10) -> None:
        self.client = client
        self.max_pages = max_pages

    def build(
        self,
        *,
        captured_at: datetime,
        session: Session,
        catalysts: dict[str, Catalyst],
        kospi_change_pct: float,
        kosdaq_change_pct: float,
        candidate_limit: int = 60,
        candidate_codes: tuple[str, ...] | None = None,
    ) -> MarketSnapshot:
        if captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        masters = self._stock_master()
        exchange = "1" if session == Session.KRX_1520 else "2"
        ranked = self._trading_value_top(exchange)
        if candidate_codes is not None:
            allowed_codes = {str(code).replace("_NX", "").strip() for code in candidate_codes}
            ranked = [
                row for row in ranked
                if str(row.get("stk_cd", "")).replace("_NX", "").strip() in allowed_codes
            ]
        ranked = ranked[:candidate_limit]
        institution_flow: dict[str, int] = {}
        program_flow: dict[str, int] = {}
        if ranked:
            try:
                institution_flow = self._institution_flow(
                    exchange=exchange,
                    date=captured_at.strftime("%Y%m%d"),
                )
            except (ValueError, RuntimeError, TimeoutError, ConnectionError, OSError):
                institution_flow = {}
            try:
                program_flow = self._program_flow(
                    exchange=exchange,
                    date=captured_at.strftime("%Y%m%d"),
                )
            except (ValueError, RuntimeError, TimeoutError, ConnectionError, OSError):
                program_flow = {}
        quotes: list[Quote] = []
        for row in ranked:
            code = str(row.get("stk_cd", "")).replace("_NX", "").strip()
            if not code or code not in masters:
                continue
            try:
                quote = self._build_quote(
                    code=code,
                    ranked=row,
                    master=masters[code],
                    captured_at=captured_at,
                    session=session,
                    catalyst=catalysts.get(code, Catalyst("", "", 0.0, False)),
                    institution_net=institution_flow.get(code),
                    program_net=program_flow.get(code),
                )
            except (KeyError, ValueError):
                continue
            quotes.append(quote)
        # Collection can take longer than a few seconds.  The market snapshot
        # reference must represent the newest verified quote, otherwise quotes
        # fetched later than the caller's start time look incorrectly "future"
        # and are rejected by the freshness gate.
        snapshot_at = max((quote.observed_at for quote in quotes), default=captured_at)
        snapshot_at = max(captured_at, snapshot_at)
        return MarketSnapshot(
            captured_at=snapshot_at,
            session=session,
            kospi_change_pct=kospi_change_pct,
            kosdaq_change_pct=kosdaq_change_pct,
            quotes=tuple(quotes),
            source="KIWOOM_REST",
            delayed=False,
        )

    def theme_context(self, *, session: Session, max_themes: int = 12) -> dict[str, Catalyst]:
        """Use Kiwoom theme breadth as a chart-confirmation context, not a news claim."""
        exchange = "1" if session == Session.KRX_1520 else "2"
        group_keys = (
            "thema_grp_cd", "thema_nm", "stk_num", "flu_sig", "flu_rt",
            "rising_stk_num", "fall_stk_num", "dt_prft_rt", "main_stk",
        )
        groups = self._list(
            "ka90001",
            "/api/dostk/thme",
            {
                "qry_tp": "0",
                "date_tp": "1",
                "flu_pl_amt_tp": "3",
                "stex_tp": exchange,
                "stk_cd": "",
                "thema_nm": "",
            },
            "thema_grp",
            group_keys,
            page_limit=1,
        )
        groups.sort(key=lambda row: _number(row.get("flu_rt"), signed=True), reverse=True)
        component_keys = (
            "stk_cd", "stk_nm", "cur_prc", "flu_sig", "pred_pre", "flu_rt",
            "acc_trde_qty", "sel_bid", "sel_req", "buy_bid", "buy_req", "dt_prft_rt_n",
        )
        result: dict[str, Catalyst] = {}
        for group in groups[:max_themes]:
            change = _number(group.get("flu_rt"), signed=True)
            rising = int(_number(group.get("rising_stk_num")))
            falling = int(_number(group.get("fall_stk_num")))
            if change <= 0 or rising <= falling:
                continue
            group_code = str(group.get("thema_grp_cd", "")).strip()
            group_name = str(group.get("thema_nm", "")).strip() or group_code
            if not group_code:
                continue
            breadth = rising / max(1, rising + falling)
            score = min(1.0, max(0.0, change / 6.0 * 0.7 + breadth * 0.3))
            components = self._list(
                "ka90002",
                "/api/dostk/thme",
                {"thema_grp_cd": group_code, "stex_tp": exchange, "date_tp": "2"},
                "thema_comp_stk",
                component_keys,
                page_limit=1,
            )
            for component in components:
                code = str(component.get("stk_cd", "")).replace("_NX", "").strip()
                if not code:
                    continue
                current = result.get(code)
                if current is None or score > current.score:
                    result[code] = Catalyst(
                        theme=group_name,
                        summary=(
                            f"키움 테마 강도 확인: {group_name} {change:+.2f}%, "
                            f"상승 {rising}/하락 {falling}"
                        ),
                        score=score,
                        verified=False,
                    )
        return result

    def historical_five_minute_bars(
        self,
        *,
        code: str,
        base_date: str,
        exchange: str = "KRX",
    ) -> tuple[Bar, ...]:
        api_code = f"{code}_NX" if exchange.upper() == "NXT" else code
        rows = self._list(
            "ka10080",
            "/api/dostk/chart",
            {
                "stk_cd": api_code,
                "tic_scope": "5",
                "upd_stkpc_tp": "1",
                "base_dt": base_date.replace("-", ""),
            },
            "stk_min_pole_chart_qry",
            ("cur_prc", "trde_qty", "cntr_tm", "open_pric", "high_pric", "low_pric"),
            page_limit=3,
        )
        date_prefix = base_date.replace("-", "")
        bars = []
        for row in rows:
            timestamp = str(row.get("cntr_tm", ""))
            if not timestamp.startswith(date_prefix):
                continue
            bars.append(
                Bar(
                    timestamp=timestamp,
                    open=_number(row.get("open_pric")),
                    high=_number(row.get("high_pric")),
                    low=_number(row.get("low_pric")),
                    close=_number(row.get("cur_prc")),
                    volume=_number(row.get("trde_qty")),
                )
            )
        return tuple(sorted(bars, key=lambda bar: bar.timestamp))

    def build_medium_term_snapshot(
        self,
        *,
        captured_at: datetime,
        disclosure_overlays: dict[str, dict[str, Any]],
        candidate_limit: int = 40,
    ) -> MediumTermSnapshot:
        """Build a separate 20–40 day universe from current KRX liquidity ranks.

        Kiwoom supplies daily charts and basic valuation/profit figures. Corporate
        disclosure safety is injected separately and remains mandatory in the engine.
        Missing or malformed disclosure evidence therefore cannot create a paper buy.
        """
        if captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        masters = self._stock_master()
        ranked = self._trading_value_top("1")[:candidate_limit]
        quotes = []
        for row in ranked:
            code = str(row.get("stk_cd", "")).replace("_NX", "").strip()
            master = masters.get(code)
            if not code or master is None:
                continue
            try:
                quotes.append(
                    self._build_medium_term_quote(
                        code=code,
                        ranked=row,
                        master=master,
                        captured_at=captured_at,
                        disclosure=disclosure_overlays.get(code, {}),
                    )
                )
            except (KeyError, ValueError):
                continue
        return MediumTermSnapshot(
            captured_at=captured_at,
            quotes=tuple(quotes),
            source="KIWOOM_REST+DISCLOSURE_OVERLAY",
            delayed=False,
        )

    def medium_term_candidate_codes(self, candidate_limit: int = 40) -> tuple[str, ...]:
        """Return KRX liquidity-ranked listed codes for pre-fetching disclosures."""
        masters = self._stock_master()
        codes: list[str] = []
        for row in self._trading_value_top("1"):
            code = str(row.get("stk_cd", "")).replace("_NX", "").strip()
            master = masters.get(code)
            if not code or master is None:
                continue
            if str(master.get("nxtEnable", "")).strip().upper() in {"Y", "1", "TRUE"}:
                continue
            codes.append(code)
            if len(codes) >= candidate_limit:
                break
        return tuple(codes)

    def _build_medium_term_quote(
        self,
        *,
        code: str,
        ranked: dict[str, Any],
        master: dict[str, Any],
        captured_at: datetime,
        disclosure: dict[str, Any],
    ) -> MediumTermQuote:
        basic = self._single("ka10001", "/api/dostk/stkinfo", {"stk_cd": code})
        daily = self._list(
            "ka10081",
            "/api/dostk/chart",
            {"stk_cd": code, "base_dt": captured_at.strftime("%Y%m%d"), "upd_stkpc_tp": "1"},
            "stk_dt_pole_chart_qry",
            ("cur_prc", "trde_qty", "trde_prica", "dt", "open_pric", "high_pric", "low_pric"),
            page_limit=4,
        )
        if len(daily) < 130:
            raise ValueError("at least 130 daily bars are required")
        bars = sorted(
            (
                Bar(
                    timestamp=str(row.get("dt", "")),
                    open=_number(row.get("open_pric")),
                    high=_number(row.get("high_pric")),
                    low=_number(row.get("low_pric")),
                    close=_number(row.get("cur_prc")),
                    volume=_number(row.get("trde_qty")),
                )
                for row in daily
            ),
            key=lambda bar: bar.timestamp,
        )
        closes = [bar.close for bar in bars]
        volumes = [bar.volume for bar in bars]
        price = int(_number(basic.get("cur_prc", ranked.get("cur_prc", closes[-1]))))
        ma20 = sma(closes, 20)
        ma60 = sma(closes, 60)
        ma120 = sma(closes, 120)
        support_candidates = [
            int(ma20), int(ma60), int(ma120),
            *(int(bar.low) for bar in bars[-20:]),
        ]
        supports = [value for value in support_candidates if 0 < value < price]
        if not supports:
            raise ValueError("daily support is unavailable")
        resistance_candidates = [bar.high for bar in bars[-60:-1] if bar.high > price]
        resistance = int(min(resistance_candidates)) if resistance_candidates else None
        prior_volume = sum(volumes[-21:-1]) / 20.0
        checked_at = _optional_datetime(disclosure.get("checked_at"))
        disclosure_checked = bool(
            checked_at
            and 0 <= (captured_at - checked_at).total_seconds() <= 3 * 24 * 60 * 60
        )
        raw_risk_flags = disclosure.get("risk_flags", ())
        if not isinstance(raw_risk_flags, (list, tuple)):
            raise ValueError("disclosure risk_flags must be a list")
        risk_flags = tuple(str(item) for item in raw_risk_flags)

        return MediumTermQuote(
            code=code,
            name=str(basic.get("stk_nm") or master.get("name") or ranked.get("stk_nm") or code),
            observed_at=captured_at,
            price=price,
            trading_value=int(_number(ranked.get("trde_prica")) * 1_000_000),
            market_cap=int(_number(basic.get("mac")) * 100_000_000),
            nxt_eligible=str(master.get("nxtEnable", "")).strip().upper() in {"Y", "1", "TRUE"},
            ma20=ma20,
            ma60=ma60,
            ma120=ma120,
            ma20_slope_5d=ma20 - sma(closes[:-5], 20),
            ma60_slope_10d=ma60 - sma(closes[:-10], 60),
            rsi14=rsi(closes),
            atr14=atr(bars),
            volume_ratio20=(volumes[-1] / prior_volume) if prior_volume > 0 else 0.0,
            return20_pct=(price / closes[-21] - 1.0) * 100.0,
            return60_pct=(price / closes[-61] - 1.0) * 100.0,
            support_price=max(supports),
            resistance_price=resistance,
            per=_number(basic.get("per"), signed=True),
            pbr=_number(basic.get("pbr"), signed=True),
            roe=_number(basic.get("roe"), signed=True),
            sales=int(_number(basic.get("sale_amt"), signed=True) * 100_000_000),
            operating_profit=int(_number(basic.get("bus_pro"), signed=True) * 100_000_000),
            net_income=int(_number(basic.get("cup_nga"), signed=True) * 100_000_000),
            fundamental_source="KIWOOM_KA10001_VENDOR",
            fundamental_observed_at=captured_at,
            disclosure_checked=disclosure_checked,
            risk_flags=risk_flags,
            catalyst=str(disclosure.get("catalyst", "")),
        )

    def _build_quote(
        self,
        *,
        code: str,
        ranked: dict[str, Any],
        master: dict[str, Any],
        captured_at: datetime,
        session: Session,
        catalyst: Catalyst,
        institution_net: int | None,
        program_net: int | None,
    ) -> Quote:
        api_code = f"{code}_NX" if session == Session.NXT_1955 else code
        condition = self._single(
            "ka10007", "/api/dostk/mrkcond", {"stk_cd": api_code}
        )
        daily = self._list(
            "ka10081",
            "/api/dostk/chart",
            {"stk_cd": api_code, "base_dt": captured_at.strftime("%Y%m%d"), "upd_stkpc_tp": "1"},
            "stk_dt_pole_chart_qry",
            ("cur_prc", "trde_qty", "trde_prica", "dt", "open_pric", "high_pric", "low_pric"),
            page_limit=2,
        )
        minutes = self._list(
            "ka10080",
            "/api/dostk/chart",
            {"stk_cd": api_code, "tic_scope": "5", "upd_stkpc_tp": "1", "base_dt": captured_at.strftime("%Y%m%d")},
            "stk_min_pole_chart_qry",
            ("cur_prc", "trde_qty", "cntr_tm", "open_pric", "high_pric", "low_pric"),
            page_limit=1,
        )
        if len(daily) < 20 or len(minutes) < 21:
            raise ValueError("insufficient chart history")

        daily_sorted = sorted(daily, key=lambda row: str(row.get("dt", "")))
        five_rows = sorted(minutes, key=lambda row: str(row.get("cntr_tm", "")))
        daily_bars = [
            Bar(
                timestamp=str(row.get("dt", "")),
                open=_number(row.get("open_pric")),
                high=_number(row.get("high_pric")),
                low=_number(row.get("low_pric")),
                close=_number(row.get("cur_prc")),
                volume=_number(row.get("trde_qty")),
            )
            for row in daily_sorted
        ]
        date_prefix = captured_at.strftime("%Y%m%d")
        five_bars = [
            Bar(
                timestamp=str(row.get("cntr_tm", "")),
                open=_number(row.get("open_pric")),
                high=_number(row.get("high_pric")),
                low=_number(row.get("low_pric")),
                close=_number(row.get("cur_prc")),
                volume=_number(row.get("trde_qty")),
            )
            for row in five_rows
            if str(row.get("cntr_tm", "")).startswith(date_prefix)
        ]
        if len(five_bars) < 25:
            raise ValueError("at least 25 same-session five-minute bars are required")
        technical = compute_features(daily_bars, five_bars)

        price = int(_number(condition.get("cur_prc", ranked.get("cur_prc"))))
        observed_at = self._observed_at(condition, captured_at)
        recent_lows = [int(bar.low) for bar in daily_bars[-5:]]
        support_inputs = [
            int(technical.ma5),
            int(technical.five_min_ma20),
            int(technical.vwap),
            int(technical.breakout_level or 0),
            *recent_lows,
        ]
        valid_support = [value for value in support_inputs if 0 < value < price]
        if not valid_support:
            raise ValueError("support level unavailable")

        total_ask = sum(int(_number(condition.get(f"sel_{i}bid_req"))) for i in range(1, 11))
        total_bid = sum(int(_number(condition.get(f"buy_{i}bid_req"))) for i in range(1, 11))
        warnings: list[str] = []
        if not total_ask and not total_bid:
            warnings.append("ORDERBOOK_UNKNOWN")
        if not catalyst.summary:
            warnings.append("CATALYST_UNKNOWN")
        if institution_net is None:
            warnings.append("INSTITUTION_FLOW_NOT_CONFIRMED")
        if program_net is None:
            warnings.append("PROGRAM_FLOW_NOT_CONFIRMED")

        return Quote(
            code=code,
            name=str(condition.get("stk_nm") or master.get("name") or ranked.get("stk_nm") or code),
            observed_at=observed_at,
            price=price,
            open_price=int(_number(condition.get("open_pric"))),
            high_price=int(_number(condition.get("high_pric"))),
            low_price=int(_number(condition.get("low_pric"))),
            volume=int(_number(condition.get("trde_qty", ranked.get("now_trde_qty")))),
            # ka10007/ka10032 document trde_prica in KRW millions.
            trading_value=int(
                _number(condition.get("trde_prica", ranked.get("trde_prica")))
                * 1_000_000
            ),
            previous_volume=int(_number(condition.get("pred_trde_qty", ranked.get("pred_trde_qty")))),
            day_change_pct=_number(condition.get("flu_rt", ranked.get("flu_rt")), signed=True),
            ma5=technical.ma5,
            ma20=technical.ma20,
            ma120=technical.ma120,
            five_min_ma20=technical.five_min_ma20,
            five_min_ma20_slope=technical.five_min_ma20_slope,
            support_price=max(valid_support),
            nxt_eligible=str(master.get("nxtEnable", "")).strip().upper() in {"Y", "1", "TRUE"},
            theme=catalyst.theme,
            catalyst=catalyst.summary,
            catalyst_score=max(0.0, min(1.0, catalyst.score)),
            catalyst_verified=catalyst.verified,
            market=str(master.get("_market", "")),
            institution_net=institution_net,
            program_net=program_net,
            best_ask=int(_number(condition.get("sel_1bid"))) or None,
            best_bid=int(_number(condition.get("buy_1bid"))) or None,
            total_ask_size=total_ask or None,
            total_bid_size=total_bid or None,
            warnings=tuple(warnings),
            ma60=technical.ma60,
            rsi14=technical.rsi14,
            atr14=technical.atr14,
            recent_resistance=technical.recent_resistance,
            vwap=technical.vwap,
            five_min_volume_ratio=technical.five_min_volume_ratio,
            last_hour_return_pct=technical.last_hour_return_pct,
            higher_lows=technical.higher_lows,
            breakout_level=technical.breakout_level,
            breakout_holds=technical.breakout_holds,
        )

    def _stock_master(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        keys = (
            "code", "name", "listCount", "auditInfo", "regDay", "lastPrice",
            "state", "marketCode", "marketName", "upName", "upSizeName",
            "orderWarning", "companyClassName", "nxtEnable",
        )
        for market in ("0", "10"):
            rows = self._list(
                "ka10099", "/api/dostk/stkinfo", {"mrkt_tp": market}, "list", keys
            )
            for row in rows:
                code = str(row.get("code", "")).strip()
                if code:
                    normalized = dict(row)
                    normalized["_market"] = "KOSPI" if market == "0" else "KOSDAQ"
                    result[code] = normalized
        return result

    def _institution_flow(self, *, exchange: str, date: str) -> dict[str, int]:
        keys = (
            "for_netslmt_stk_cd", "for_netslmt_stk_nm", "for_netslmt_amt",
            "for_netslmt_qty", "for_netprps_stk_cd", "for_netprps_stk_nm",
            "for_netprps_amt", "for_netprps_qty", "orgn_netslmt_stk_cd",
            "orgn_netslmt_stk_nm", "orgn_netslmt_amt", "orgn_netslmt_qty",
            "orgn_netprps_stk_cd", "orgn_netprps_stk_nm", "orgn_netprps_amt",
            "orgn_netprps_qty",
        )
        rows = self._list(
            "ka90009",
            "/api/dostk/rkinfo",
            {
                "mrkt_tp": "000",
                "amt_qty_tp": "1",
                "qry_dt_tp": "1",
                "stex_tp": exchange,
                "date": date,
            },
            "frgnr_orgn_trde_upper",
            keys,
            page_limit=2,
        )
        result: dict[str, int] = {}
        for row in rows:
            sell_code = str(row.get("orgn_netslmt_stk_cd", "")).replace("_NX", "").strip()
            buy_code = str(row.get("orgn_netprps_stk_cd", "")).replace("_NX", "").strip()
            if sell_code:
                result[sell_code] = -abs(
                    int(_number(row.get("orgn_netslmt_amt"), signed=True) * 10_000_000)
                )
            if buy_code:
                result[buy_code] = abs(
                    int(_number(row.get("orgn_netprps_amt"), signed=True) * 10_000_000)
                )
        return result

    def _program_flow(self, *, exchange: str, date: str) -> dict[str, int]:
        keys = (
            "stk_cd", "stk_nm", "cur_prc", "flu_sig", "pred_pre",
            "buy_cntr_qty", "buy_cntr_amt", "sel_cntr_qty", "sel_cntr_amt",
            "netprps_prica", "all_trde_rt",
        )
        result: dict[str, int] = {}
        for market_type in ("P00101", "P10102"):
            rows = self._list(
                "ka90004",
                "/api/dostk/stkinfo",
                {"dt": date, "mrkt_tp": market_type, "stex_tp": exchange},
                "stk_prm_trde_prst",
                keys,
            )
            for row in rows:
                code = str(row.get("stk_cd", "")).replace("_NX", "").strip()
                if code:
                    result[code] = int(
                        _number(row.get("netprps_prica"), signed=True) * 1_000_000
                    )
        return result

    def _trading_value_top(self, exchange: str) -> list[dict[str, Any]]:
        keys = (
            "stk_cd", "now_rank", "pred_rank", "stk_nm", "cur_prc",
            "pred_pre_sig", "pred_pre", "flu_rt", "sel_bid", "buy_bid",
            "now_trde_qty", "pred_trde_qty", "trde_prica",
        )
        return self._list(
            "ka10032",
            "/api/dostk/rkinfo",
            {"mrkt_tp": "000", "mang_stk_incls": "0", "stex_tp": exchange},
            "trde_prica_upper",
            keys,
        )

    def _single(self, api_id: str, path: str, body: dict[str, str]) -> dict[str, Any]:
        response = self.client.fetch_page(api_id=api_id, path=path, body=body)
        self._check_response(response.body)
        return response.body

    def _list(
        self,
        api_id: str,
        path: str,
        body: dict[str, str],
        result_key: str,
        keys: tuple[str, ...],
        *,
        page_limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cont_yn = None
        next_key = None
        limit = min(self.max_pages, page_limit or self.max_pages)
        for _ in range(limit):
            response = self.client.fetch_page(
                api_id=api_id,
                path=path,
                body=body,
                cont_yn=cont_yn,
                next_key=next_key,
            )
            self._check_response(response.body)
            rows.extend(_records(response.body.get(result_key), keys))
            cont_yn = getattr(response.continuation, "cont_yn", None)
            next_key = getattr(response.continuation, "next_key", None)
            if cont_yn != "Y":
                break
        return rows

    @staticmethod
    def _check_response(body: dict[str, Any]) -> None:
        code = body.get("return_code")
        if code not in (None, 0, "0"):
            raise ValueError(f"Kiwoom API error {code}: {body.get('return_msg', '')}")

    @staticmethod
    def _observed_at(body: dict[str, Any], fallback: datetime) -> datetime:
        date = str(body.get("date", "")).strip()
        time = str(body.get("tm", "")).strip().zfill(6)
        if len(date) == 8 and len(time) == 6 and date.isdigit() and time.isdigit():
            return datetime.strptime(date + time, "%Y%m%d%H%M%S").replace(tzinfo=KST)
        return fallback
