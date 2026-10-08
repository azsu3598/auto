from __future__ import annotations

import io
import json
import unittest
import zipfile
from datetime import datetime, timedelta, timezone

from stock_automation.dart import DartClient, DartError

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 7, 15, 40, tzinfo=KST)
KEY = "k" * 40


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, *, timeout):
        self.urls.append(url)
        return self.responses.pop(0)


def corp_zip() -> bytes:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <result><list><corp_code>00126380</corp_code><corp_name>test</corp_name>
    <stock_code>005930</stock_code><modify_date>20261001</modify_date></list></result>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("CORPCODE.xml", xml)
    return buffer.getvalue()


class DartClientTests(unittest.TestCase):
    def test_parses_listed_stock_corporation_codes(self):
        client = DartClient(KEY, transport=FakeTransport([corp_zip()]))
        self.assertEqual({"005930": "00126380"}, client.corporation_codes())

    def test_classifies_blocking_risks_but_ignores_withdrawn_dilution(self):
        payload = {
            "status": "000",
            "total_page": 1,
            "list": [
                {"rcept_no": "3", "rcept_dt": "20261007", "report_nm": "유상증자결정(철회)", "corp_name": "테스트"},
                {"rcept_no": "2", "rcept_dt": "20261006", "report_nm": "전환사채권발행결정", "corp_name": "테스트"},
                {"rcept_no": "1", "rcept_dt": "20261005", "report_nm": "감사의견거절", "corp_name": "테스트"},
            ],
        }
        client = DartClient(
            KEY,
            transport=FakeTransport([json.dumps(payload).encode()]),
        )
        overlay = client.disclosure_overlay(
            stock_code="005930", corp_code="00126380", checked_at=NOW
        )
        self.assertEqual(("DILUTION_EVENT", "AUDIT_RISK"), overlay.risk_flags)
        self.assertIn("유상증자결정(철회)", overlay.catalyst)

    def test_no_data_is_successful_verified_empty_result(self):
        client = DartClient(
            KEY,
            transport=FakeTransport([json.dumps({"status": "013", "message": "조회된 데이터가 없습니다."}).encode()]),
        )
        overlay = client.disclosure_overlay(
            stock_code="005930", corp_code="00126380", checked_at=NOW
        )
        self.assertEqual((), overlay.risk_flags)
        self.assertEqual("", overlay.catalyst)

    def test_api_error_fails_closed(self):
        client = DartClient(
            KEY,
            transport=FakeTransport([json.dumps({"status": "020", "message": "요청 제한"}).encode()]),
        )
        with self.assertRaises(DartError):
            client.disclosure_overlay(
                stock_code="005930", corp_code="00126380", checked_at=NOW
            )

    def test_paginates_without_treating_partial_evidence_as_complete(self):
        pages = [
            {"status": "000", "total_page": 2, "list": [{"rcept_no": "2", "rcept_dt": "20261007", "report_nm": "사업보고서", "corp_name": "테스트"}]},
            {"status": "000", "total_page": 2, "list": [{"rcept_no": "1", "rcept_dt": "20260901", "report_nm": "유상증자결정", "corp_name": "테스트"}]},
        ]
        transport = FakeTransport([json.dumps(page).encode() for page in pages])
        overlay = DartClient(KEY, transport=transport).disclosure_overlay(
            stock_code="005930", corp_code="00126380", checked_at=NOW
        )
        self.assertEqual(("DILUTION_EVENT",), overlay.risk_flags)
        self.assertEqual(2, len(transport.urls))


if __name__ == "__main__":
    unittest.main()
