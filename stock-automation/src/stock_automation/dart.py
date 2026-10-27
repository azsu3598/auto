from __future__ import annotations

import io
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

# Disclosure risk flags that block a new entry. Keep equal to
# MediumTermEngine.BLOCKING_RISKS; a test checks both stay the same.
BLOCKING_RISK_FLAGS = frozenset({
    "AUDIT_RISK",
    "CAPITAL_IMPAIRMENT",
    "DELISTING_RISK",
    "DILUTION_EVENT",
    "EARNINGS_INVALIDATED",
    "GOING_CONCERN",
    "TRADING_HALT_RISK",
})


class DartError(RuntimeError):
    pass


class HttpTransport(Protocol):
    def get(self, url: str, *, timeout: float) -> bytes: ...


class UrllibTransport:
    def get(self, url: str, *, timeout: float) -> bytes:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "stock-automation/0.1"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()


@dataclass(frozen=True, slots=True)
class DartDisclosure:
    receipt_no: str
    receipt_date: str
    report_name: str
    corporation_name: str


@dataclass(frozen=True, slots=True)
class DartOverlay:
    checked_at: datetime
    risk_flags: tuple[str, ...]
    catalyst: str
    disclosures: tuple[DartDisclosure, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_at": self.checked_at.isoformat(),
            "risk_flags": list(self.risk_flags),
            "catalyst": self.catalyst,
            "disclosures": [
                {
                    "receipt_no": row.receipt_no,
                    "receipt_date": row.receipt_date,
                    "report_name": row.report_name,
                    "corporation_name": row.corporation_name,
                }
                for row in self.disclosures
            ],
        }


class DartClient:
    BASE_URL = "https://opendart.fss.or.kr/api"
    _CANCELLATION_WORDS = ("철회", "취소", "해제")
    _RISK_PATTERNS = (
        (("감사의견거절", "감사범위제한", "감사보고서 제출 지연"), "AUDIT_RISK"),
        (("계속기업 불확실", "회생절차", "파산"), "GOING_CONCERN"),
        (("상장폐지", "관리종목"), "DELISTING_RISK"),
        (("매매거래정지", "거래정지"), "TRADING_HALT_RISK"),
        (("자본잠식",), "CAPITAL_IMPAIRMENT"),
        (("유상증자", "전환사채", "신주인수권부사채", "교환사채"), "DILUTION_EVENT"),
        (("영업정지", "부도", "횡령", "배임"), "EARNINGS_INVALIDATED"),
    )

    def __init__(
        self,
        api_key: str,
        *,
        transport: HttpTransport | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if len(api_key.strip()) != 40:
            raise ValueError("OpenDART API key must be 40 characters")
        self.api_key = api_key.strip()
        self.transport = transport or UrllibTransport()
        self.timeout_seconds = timeout_seconds

    def corporation_codes(self) -> dict[str, str]:
        raw = self.transport.get(
            self._url("corpCode.xml", crtfc_key=self.api_key),
            timeout=self.timeout_seconds,
        )
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                names = archive.namelist()
                if not names:
                    raise DartError("OpenDART corporation-code ZIP is empty")
                root = ET.fromstring(archive.read(names[0]))
        except (zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
            raise DartError("invalid OpenDART corporation-code response") from exc
        mapping: dict[str, str] = {}
        for row in root.findall("list"):
            stock_code = (row.findtext("stock_code") or "").strip()
            corp_code = (row.findtext("corp_code") or "").strip()
            if len(stock_code) == 6 and len(corp_code) == 8:
                mapping[stock_code] = corp_code
        if not mapping:
            raise DartError("OpenDART corporation-code map contains no listed stocks")
        return mapping

    def disclosure_overlay(
        self,
        *,
        stock_code: str,
        corp_code: str,
        checked_at: datetime,
        lookback_days: int = 90,
    ) -> DartOverlay:
        if checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        end = checked_at.date()
        start = end - timedelta(days=lookback_days)
        rows = self._disclosures(corp_code=corp_code, start=start, end=end)
        flags: list[str] = []
        for row in rows:
            normalized = row.report_name.replace(" ", "")
            if any(word in normalized for word in self._CANCELLATION_WORDS):
                continue
            for patterns, flag in self._RISK_PATTERNS:
                if any(pattern.replace(" ", "") in normalized for pattern in patterns):
                    flags.append(flag)
        recent = rows[:3]
        catalyst = " / ".join(row.report_name for row in recent)
        return DartOverlay(
            checked_at=checked_at,
            risk_flags=tuple(dict.fromkeys(flags)),
            catalyst=catalyst,
            disclosures=tuple(recent),
        )

    def overlays(
        self,
        stock_codes: tuple[str, ...],
        *,
        corporation_codes: dict[str, str],
        checked_at: datetime,
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        missing = [code for code in stock_codes if code not in corporation_codes]
        if missing:
            raise DartError(f"OpenDART corporation code missing for: {','.join(missing[:5])}")
        for stock_code in stock_codes:
            result[stock_code] = self.disclosure_overlay(
                stock_code=stock_code,
                corp_code=corporation_codes[stock_code],
                checked_at=checked_at,
            ).to_dict()
        return result

    def _disclosures(self, *, corp_code: str, start: date, end: date) -> list[DartDisclosure]:
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "last_reprt_at": "N",
            "sort": "date",
            "sort_mth": "desc",
            "page_count": "100",
        }
        rows: list[dict[str, Any]] = []
        total_page = 1
        for page in range(1, 11):
            payload = self._json("list.json", **params, page_no=str(page))
            status = str(payload.get("status", ""))
            if page == 1 and status == "013":
                return []
            if status != "000":
                raise DartError(
                    f"OpenDART disclosure query failed: {status} {payload.get('message', '')}"
                )
            try:
                total_page = int(payload.get("total_page", 1))
            except (TypeError, ValueError) as exc:
                raise DartError("invalid OpenDART total_page") from exc
            page_rows = payload.get("list", [])
            if not isinstance(page_rows, list):
                raise DartError("invalid OpenDART disclosure list")
            rows.extend(page_rows)
            if page >= total_page:
                break
        if total_page > 10:
            raise DartError("OpenDART disclosure result exceeds safe pagination limit")
        return [
            DartDisclosure(
                receipt_no=str(row.get("rcept_no", "")),
                receipt_date=str(row.get("rcept_dt", "")),
                report_name=str(row.get("report_nm", "")),
                corporation_name=str(row.get("corp_name", "")),
            )
            for row in rows
        ]

    def _json(self, endpoint: str, **params: str) -> dict[str, Any]:
        raw = self.transport.get(self._url(endpoint, **params), timeout=self.timeout_seconds)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DartError("invalid OpenDART JSON response") from exc
        if not isinstance(value, dict):
            raise DartError("OpenDART response must be a JSON object")
        return value

    def _url(self, endpoint: str, **params: str) -> str:
        return f"{self.BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
