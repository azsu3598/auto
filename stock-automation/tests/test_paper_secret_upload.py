import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


SPEC = importlib.util.spec_from_file_location(
    "paper_secret_upload", Path(__file__).resolve().parents[1] / "tools" / "upload_paper_secrets.py"
)
upload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upload)


class NotFound(Exception):
    response = {"Error": {"Code": "ResourceNotFoundException"}}


class PaperSecretUploadTests(unittest.TestCase):
    def test_preflight_requires_operator_and_all_names_missing(self):
        sts = Mock()
        sts.get_caller_identity.return_value = {"Arn": "arn:aws:iam::000000000000:user/stock-paper-operator"}
        secrets = Mock()
        secrets.describe_secret.side_effect = NotFound
        upload.preflight(sts, secrets)
        self.assertEqual([c.kwargs['SecretId'] for c in secrets.describe_secret.call_args_list], list(upload.NAMES))
        secrets.create_secret.assert_not_called()

    def test_root_identity_cannot_create_or_read_secrets(self):
        sts, secrets = Mock(), Mock()
        sts.get_caller_identity.return_value = {"Arn": "arn:aws:iam::000000000000:root"}
        with self.assertRaises(upload.UploadError):
            upload.preflight(sts, secrets)
        secrets.describe_secret.assert_not_called()

    def test_existing_or_denied_secret_stops_before_creation(self):
        for error in (None, RuntimeError('fake-sensitive-error')):
            sts, secrets = Mock(), Mock()
            sts.get_caller_identity.return_value = {"Arn": "arn:aws:iam::000000000000:user/stock-paper-operator"}
            secrets.describe_secret.side_effect = error
            with self.assertRaises(upload.UploadError) as raised:
                upload.preflight(sts, secrets)
            self.assertNotIn('fake-sensitive-error', str(raised.exception))
            secrets.create_secret.assert_not_called()

    def test_payload_contract_excludes_extra_vault_fields(self):
        raw = json.dumps({'bot_token': '123:fake_token', 'chat_id': '123', 'unwanted': 'omit'})
        payloads = upload.build_payloads('fake_key', 'fake_secret', 'a' * 40, raw)
        self.assertEqual(payloads[0], {'app_key_mock': 'fake_key', 'app_secret_mock': 'fake_secret'})
        self.assertEqual(payloads[1], {'dart_api_key': 'a' * 40})
        self.assertEqual(payloads[2], {'bot_token': '123:fake_token', 'chat_id': '123'})

    def test_invalid_input_is_rejected_without_echoing_values(self):
        for args in (('', 'fake', 'a' * 40, '{}'), ('fake', 'fake', 'bad_dart', '{}'),
                     ('fake', 'fake', 'a' * 40, 'not-json'),
                     ('fake', 'fake', 'a' * 40, '{"bot_token":"123:fake", "chat_id":"-1"}')):
            with self.assertRaises(upload.UploadError) as raised:
                upload.build_payloads(*args)
            self.assertNotIn('bad_dart', str(raised.exception))

    def test_creation_only_uses_named_secrets_default_encryption_no_rotation(self):
        secrets, progress = Mock(), Mock()
        payloads = ({'test': 'fake1'}, {'test': 'fake2'}, {'test': 'fake3'})
        upload.create_all(secrets, payloads, progress=progress)
        self.assertEqual([c.kwargs['Name'] for c in secrets.create_secret.call_args_list], list(upload.NAMES))
        self.assertEqual(len({c.kwargs['ClientRequestToken'] for c in secrets.create_secret.call_args_list}), 3)
        for call, expected in zip(secrets.create_secret.call_args_list, payloads):
            self.assertEqual(json.loads(call.kwargs['SecretString']), expected)
            self.assertNotIn('KmsKeyId', call.kwargs)
            self.assertNotIn('AddReplicaRegions', call.kwargs)
        secrets.put_secret_value.assert_not_called()
        secrets.delete_secret.assert_not_called()
        self.assertNotIn('fake1', str(progress.call_args_list))

    def test_partial_failure_preserves_success_and_stops_remaining_calls(self):
        secrets, progress = Mock(), Mock()
        secrets.create_secret.side_effect = [{}, RuntimeError('fake_token'), {}]
        with self.assertRaises(upload.UploadError) as raised:
            upload.create_all(secrets, ({}, {}, {}), progress=progress)
        self.assertNotIn('fake_token', str(raised.exception))
        self.assertEqual(secrets.create_secret.call_count, 2)
        self.assertEqual(progress.call_count, 1)
        secrets.delete_secret.assert_not_called()

    def test_without_create_flag_is_preview_and_does_not_prompt(self):
        with patch.object(upload.getpass, 'getpass') as prompt, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(upload.main([]), 0)
        prompt.assert_not_called()

    def test_noninteractive_execution_never_prompts_or_creates(self):
        with patch.object(upload.sys.stdin, 'isatty', return_value=False), \
             patch.object(upload.getpass, 'getpass') as prompt, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(upload.main(['--create']), 1)
        prompt.assert_not_called()


if __name__ == '__main__':
    unittest.main()
