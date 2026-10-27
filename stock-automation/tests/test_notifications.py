from __future__ import annotations

import json
import unittest

from stock_automation.notifications import (
    KAKAO_MEMO_URL,
    KAKAO_TOKEN_URL,
    KakaoMemoNotifier,
    SnsEmailNotifier,
    TelegramNotifier,
    build_notifier,
)


class FakeSecrets:
    def __init__(self, payload):
        self.payload = payload
        self.puts = []

    def get_secret_value(self, **kwargs):
        return {"SecretString": json.dumps(self.payload)}

    def put_secret_value(self, **kwargs):
        self.puts.append(kwargs)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post_form(self, url, fields, *, headers=None):
        self.calls.append((url, fields, headers or {}))
        return self.responses.pop(0)


class FakeSns:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)


class NotificationTests(unittest.TestCase):
    def test_telegram_sends_private_trade_message(self):
        secrets = FakeSecrets({"bot_token": "123:secret", "chat_id": "998877"})
        transport = FakeTransport([{"ok": True, "result": {"message_id": 1}}])
        notifier = TelegramNotifier(secrets, "telegram-secret", transport=transport)

        notifier.send(
            "[모의매수] 테스트",
            {"stock": "테스트", "entry_price": 10_000, "quantity": 20},
        )

        url, fields, headers = transport.calls[0]
        self.assertEqual("https://api.telegram.org/bot123:secret/sendMessage", url)
        self.assertEqual("998877", fields["chat_id"])
        self.assertIn("매수가: 10,000", fields["text"])
        self.assertEqual("true", fields["protect_content"])
        self.assertEqual({}, headers)
        self.assertIn("실제 계좌 주문이 아닙니다", fields["text"])

    def test_telegram_explains_exit_action_and_reasons_in_korean(self):
        secrets = FakeSecrets({"bot_token": "123:secret", "chat_id": "998877"})
        transport = FakeTransport([{"ok": True}])
        TelegramNotifier(secrets, "telegram-secret", transport=transport).send(
            "[모의매매] 테스트 SCHEDULED_EXIT",
            {
                "action": "SCHEDULED_EXIT",
                "execution_price": 10_200,
                "execution_quantity": 20,
                "realized_pnl": 3_573,
                "reason_codes": ["NEXT_SESSION_0910", "UNMAPPED_CODE"],
            },
        )
        text = transport.calls[0][1]["text"]
        self.assertTrue(text.startswith("[모의매매] 테스트 예정 시각 청산(가상매도)"))
        self.assertIn("구분: 예정 시각 청산(가상매도)", text)
        self.assertIn("사유: 다음 거래일 09:10 청산, UNMAPPED_CODE", text)
        self.assertIn("손익: 3,573", text)
        self.assertNotIn("SCHEDULED_EXIT", text)

    def test_telegram_rejects_incomplete_secret(self):
        notifier = TelegramNotifier(
            FakeSecrets({"bot_token": "only-token"}),
            "telegram-secret",
            transport=FakeTransport([]),
        )
        with self.assertRaisesRegex(RuntimeError, "bot_token and chat_id"):
            notifier.send("test", {})

    def test_kakao_refreshes_and_persists_rotated_refresh_token(self):
        secrets = FakeSecrets(
            {
                "rest_api_key": "rest-key",
                "client_secret": "client-secret",
                "refresh_token": "old-refresh",
                "link_url": "https://example.com",
            }
        )
        transport = FakeTransport(
            [
                {"access_token": "access", "refresh_token": "new-refresh"},
                {"result_code": 0},
            ]
        )
        notifier = KakaoMemoNotifier(secrets, "kakao-secret", transport=transport)

        notifier.send("[모의매도] 테스트", {"execution_price": 10_500})

        self.assertEqual(KAKAO_TOKEN_URL, transport.calls[0][0])
        self.assertEqual(KAKAO_MEMO_URL, transport.calls[1][0])
        self.assertEqual(1, len(secrets.puts))
        rotated = json.loads(secrets.puts[0]["SecretString"])
        self.assertEqual("new-refresh", rotated["refresh_token"])

    def test_builder_prefers_free_telegram_channel(self):
        notifier = build_notifier(
            "telegram",
            FakeSecrets({"bot_token": "x", "chat_id": "1"}),
            "secret",
        )
        self.assertIsInstance(notifier, TelegramNotifier)
        self.assertIsNone(build_notifier("disabled", FakeSecrets({}), None))

    def test_email_sns_fallback_is_retained(self):
        sns = FakeSns()
        notifier = build_notifier(
            "email",
            FakeSecrets({}),
            None,
            sns_client=sns,
            sns_topic_arn="arn:aws:sns:ap-northeast-2:123:paper",
        )
        self.assertIsInstance(notifier, SnsEmailNotifier)
        notifier.send("[모의매수] 테스트", {"stock": "테스트"})
        self.assertEqual(1, len(sns.messages))
        self.assertEqual("[모의매수] 테스트", sns.messages[0]["Subject"])


if __name__ == "__main__":
    unittest.main()
