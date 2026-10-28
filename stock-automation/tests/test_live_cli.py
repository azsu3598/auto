import os
import unittest
from types import SimpleNamespace
from unittest import mock

from stock_automation import live_cli


class Response:
    def __init__(self, body, cont_yn="N"):
        self.body = body
        self.continuation = SimpleNamespace(cont_yn=cont_yn, next_key="NEXT" if cont_yn == "Y" else None)


class QuoteClient:
    def __init__(self, body):
        self.body = body

    def fetch_page(self, **kwargs):
        return Response(self.body)


class AccountClient:
    def __init__(self, numbers):
        self.numbers = numbers
        self.calls = 0

    def fetch_page(self, **kwargs):
        index = self.calls
        self.calls += 1
        more = "Y" if index + 1 < len(self.numbers) else "N"
        return Response({"return_code": 0, "acctNo": self.numbers[index]}, more)


ACCOUNT_ENV = {
    "KIWOOM_ACCOUNT_NUMBER": "1234-5678",
    "LIVE_ACCOUNT_FINGERPRINT_SALT": "s" * 16,
}


class LiveCliSafetyTests(unittest.TestCase):
    def test_quote_without_broker_time_is_rejected(self):
        client = QuoteClient({"return_code": 0, "cur_prc": "+10000"})
        with self.assertRaisesRegex(RuntimeError, "quote time"):
            live_cli._current_quote(client, "123456")

    def test_quote_time_comes_from_broker_response(self):
        client = QuoteClient({"return_code": 0, "cur_prc": "-10000", "date": "20261007", "tm": "152001"})
        observed_at, price = live_cli._current_quote(client, "123456")
        self.assertEqual(10_000, price)
        self.assertEqual("2026-10-07T15:20:01+09:00", observed_at.isoformat())

    def test_fingerprint_requires_the_broker_token_to_use_exactly_the_configured_account(self):
        with mock.patch.dict(os.environ, ACCOUNT_ENV):
            fingerprint = live_cli._verified_account_fingerprint(AccountClient(["12345678"]), "main")
            self.assertEqual(live_cli._account_fingerprint(), fingerprint)
            with self.assertRaisesRegex(RuntimeError, "broker account"):
                live_cli._verified_account_fingerprint(AccountClient(["87654321"]), "main")
            with self.assertRaisesRegex(RuntimeError, "broker account"):
                live_cli._verified_account_fingerprint(AccountClient(["12345678", "99999999"]), "main")
            with self.assertRaisesRegex(RuntimeError, "broker account"):
                live_cli._verified_account_fingerprint(AccountClient([""]), "main")


if __name__ == "__main__":
    unittest.main()
