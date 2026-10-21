from io import BytesIO
import json
import unittest
from unittest.mock import Mock, patch

from stock_automation.integration_checks import storage_probes, notification_probe


class ProbeDdb:
    def __init__(self, *, broken_duplicate=False, broken_cleanup=False):
        self.items = {}
        self.deleted = []
        self.broken_duplicate = broken_duplicate
        self.broken_cleanup = broken_cleanup

    def transact_write_items(self, TransactItems):
        if self.items and not self.broken_duplicate:
            error = RuntimeError('not printed')
            error.response = {'Error': {'Code': 'TransactionCanceledException'},
                'CancellationReasons': [{'Code': 'ConditionalCheckFailed'} for _ in TransactItems]}
            raise error
        for row in TransactItems:
            item = row['Put']['Item']; self.items[item['pk']['S']] = item

    def get_item(self, **kwargs):
        return {'Item': self.items[kwargs['Key']['pk']['S']]}

    def delete_item(self, **kwargs):
        if self.broken_cleanup:
            raise RuntimeError('not printed')
        key = kwargs['Key']['pk']['S']
        if self.items[key]['probe_owner'] != kwargs['ExpressionAttributeValues'][':owner']:
            raise RuntimeError('owner mismatch')
        self.deleted.append(key); del self.items[key]


class ProbeS3:
    def put_object(self, **kwargs): self.data = kwargs
    def get_object(self, **kwargs): return {'Body': BytesIO(self.data['Body'])}


class IntegrationCheckTests(unittest.TestCase):
    def test_successful_storage_probe_uses_only_validation_keys_and_cleans_own_ddb_items(self):
        s3 = ProbeS3(); ddb = ProbeDdb()
        checks = storage_probes({'PAPER_BUCKET': 'paper', 'PAPER_TABLE': 'paper'},
            client_factory=lambda name: {'s3': s3, 'dynamodb': ddb}[name])
        self.assertTrue(all(c.ok for c in checks))
        self.assertTrue(s3.data['Key'].startswith('validation/integration/'))
        self.assertEqual(ddb.items, {})
        self.assertEqual(len(ddb.deleted), 2)
        self.assertTrue(all(key.startswith('CONTROL#INTEGRATION_PROBE#') for key in ddb.deleted))
        self.assertNotIn('WALLET#', json.dumps(ddb.deleted))

    def test_duplicate_condition_bypass_or_cleanup_failure_is_not_reported_as_success(self):
        for ddb in (ProbeDdb(broken_duplicate=True), ProbeDdb(broken_cleanup=True)):
            checks = storage_probes({'PAPER_BUCKET':'paper','PAPER_TABLE':'paper'},
                client_factory=lambda name: ProbeS3() if name=='s3' else ddb)
            self.assertFalse(checks[-1].ok)

    def test_client_creation_failure_is_sanitized(self):
        def broken(name): raise RuntimeError('must-not-log-secret')
        checks = storage_probes({'PAPER_BUCKET':'paper','PAPER_TABLE':'paper'}, client_factory=broken)
        self.assertFalse(all(c.ok for c in checks))
        self.assertNotIn('must-not-log-secret', str(checks))

    def test_notification_is_a_single_explicit_probe_and_errors_are_sanitized(self):
        notifier = Mock()
        with patch('stock_automation.notifications.build_notifier', return_value=notifier):
            check = notification_probe({'NOTIFICATION_CHANNEL':'telegram'}, client_factory=Mock())
            self.assertTrue(check.ok)
            notifier.send.assert_called_once()
            self.assertEqual(notifier.send.call_args.args[1]['kind'], 'INTEGRATION_PROBE')
        notifier.send.side_effect = RuntimeError('must-not-log-secret')
        with patch('stock_automation.notifications.build_notifier', return_value=notifier):
            check = notification_probe({'NOTIFICATION_CHANNEL':'telegram'}, client_factory=Mock())
            self.assertFalse(check.ok)
            self.assertNotIn('must-not-log-secret', check.detail)


if __name__ == '__main__':
    unittest.main()
