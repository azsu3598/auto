import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


SPEC = importlib.util.spec_from_file_location(
    "telegram_setup", Path(__file__).resolve().parents[1] / "tools" / "setup_telegram.py"
)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)

# Deliberately fake test-only credentials and identities.
TOKEN = "123:fake_test_token"
USERNAME = "example_test_bot"


def update(chat_id=123, chat_type="private", text="/start"):
    return {"message": {"chat": {"id": chat_id, "type": chat_type},
                        "from": {"id": chat_id, "is_bot": False}, "text": text}}


class TelegramSetupTests(unittest.TestCase):
    def test_register_only_queries_and_stores_notifier_contract(self):
        vault = Mock()
        api = Mock(side_effect=[{"is_bot": True, "username": USERNAME}, [update(), update()]])
        setup.register(TOKEN, USERNAME, vault, api=api)
        self.assertEqual([c.args[1] for c in api.call_args_list], ["getMe", "getUpdates"])
        service, account, raw = vault.set_password.call_args.args
        self.assertEqual((service, account), (setup.SERVICE, setup.ACCOUNT))
        self.assertEqual(json.loads(raw), {"bot_token": TOKEN, "chat_id": "123"})

    def test_wrong_bot_does_not_read_updates_or_store(self):
        api, vault = Mock(return_value={"is_bot": True, "username": "wrong_bot"}), Mock()
        with self.assertRaises(setup.SetupError):
            setup.register(TOKEN, USERNAME, vault, api=api)
        self.assertEqual(api.call_count, 1)
        vault.set_password.assert_not_called()

    def test_missing_start_groups_and_ambiguous_chats_are_rejected(self):
        for updates in ([], [update(chat_type="group")], [update(text="hello")],
                        [update(123), update(456)], [update(text="/start@other_bot")],
                        [{"message": {"chat": {"id": 123, "type": "private"}}}]):
            with self.subTest(updates=updates), self.assertRaises(setup.SetupError):
                setup.find_private_chat(updates, USERNAME)

    def test_bot_addressed_start_is_supported(self):
        self.assertEqual(setup.find_private_chat([update(text=f"/start@{USERNAME} param")], USERNAME), "123")

    def test_invalid_token_never_calls_api(self):
        api = Mock()
        with self.assertRaises(setup.SetupError):
            setup.register("bad/token", USERNAME, Mock(), api=api)
        api.assert_not_called()

    def test_transport_errors_do_not_reveal_token(self):
        connection = Mock()
        connection.request.side_effect = OSError(TOKEN)
        with patch.object(setup.http.client, "HTTPSConnection", return_value=connection):
            with self.assertRaises(setup.SetupError) as raised:
                setup.telegram_get(TOKEN, "getMe")
        self.assertNotIn(TOKEN, str(raised.exception))
        connection.close.assert_called_once()

    def test_native_context_keeps_certificate_and_hostname_verification(self):
        import ssl
        context = setup.secure_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_certificate_dns_and_timeout_errors_are_distinguished_and_redacted(self):
        import socket
        import ssl
        for error, expected in (
            (ssl.SSLCertVerificationError(TOKEN), "인증서"),
            (socket.gaierror(TOKEN), "서버 주소"),
            (TimeoutError(TOKEN), "시간이 초과"),
        ):
            connection = Mock()
            connection.request.side_effect = error
            with patch.object(setup.http.client, "HTTPSConnection", return_value=connection):
                with self.assertRaises(setup.SetupError) as raised:
                    setup.telegram_get(TOKEN, "getMe")
            self.assertIn(expected, str(raised.exception))
            self.assertNotIn(TOKEN, str(raised.exception))

    def test_http_response_and_redirect_do_not_reveal_body(self):
        for status in (301, 401, 409):
            connection = Mock()
            response = connection.getresponse.return_value
            response.status = status
            response.read.return_value = TOKEN.encode()
            with patch.object(setup.http.client, "HTTPSConnection", return_value=connection):
                with self.assertRaises(setup.SetupError) as raised:
                    setup.telegram_get(TOKEN, "getUpdates")
            self.assertNotIn(TOKEN, str(raised.exception))
            response.read.assert_not_called()

    def test_updates_use_no_offset_or_mutating_method(self):
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = b'{"ok": true, "result": []}'
        with patch.object(setup.http.client, "HTTPSConnection", return_value=connection):
            self.assertEqual(setup.telegram_get(TOKEN, "getUpdates"), [])
        self.assertEqual(connection.request.call_args.args, ("GET", f"/bot{TOKEN}/getUpdates?limit=100&timeout=0"))
        with self.assertRaises(setup.SetupError):
            setup.telegram_get(TOKEN, "sendMessage")

    def test_vault_failure_redacts_secret(self):
        vault = Mock()
        vault.set_password.side_effect = RuntimeError(TOKEN)
        api = Mock(side_effect=[{"is_bot": True, "username": USERNAME}, [update()]])
        with self.assertRaises(setup.SetupError) as raised:
            setup.register(TOKEN, USERNAME, vault, api=api)
        self.assertNotIn(TOKEN, str(raised.exception))

    def test_noninteractive_execution_does_not_prompt_or_read_credentials(self):
        output = io.StringIO()
        with patch.object(setup.sys.stdin, "isatty", return_value=False), \
             patch.object(setup.getpass, "getpass") as prompt, contextlib.redirect_stdout(output):
            self.assertEqual(setup.main(["--bot-username", USERNAME]), 1)
        prompt.assert_not_called()
        self.assertNotIn(TOKEN, output.getvalue())


if __name__ == "__main__":
    unittest.main()
