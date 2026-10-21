import contextlib
import io
import unittest
from unittest.mock import Mock, patch

from stock_automation import storage_contracts as probe
from stock_automation.cli import build_parser, main


class StorageContractScopeTests(unittest.TestCase):
    def setUp(self):
        self.raw = Mock()
        self.owner = 'a' * 32
        self.db = probe.ScopedDdb(self.raw, 'stock-automation-paper', self.owner, ['wallet', 'event'])

    def test_wrong_table_and_unknown_label_never_reach_sdk(self):
        for table, label in [('live', 'wallet'), ('stock-automation-paper', 'CONTROL#LIVE')]:
            with self.assertRaises(ValueError):
                self.db.get_item(TableName=table, Key={'pk': {'S': label}})
        self.raw.get_item.assert_not_called()
        for table, owner in [('live', self.owner), ('stock-automation-paper', '../escape')]:
            with self.assertRaises(ValueError):
                probe.ScopedDdb(self.raw, table, owner, ['wallet'])

    def test_wallet_creation_is_namespaced_owned_and_does_not_mutate_input(self):
        args = {'TableName': 'stock-automation-paper', 'Item': {'pk': {'S': 'wallet'}}, 'ConditionExpression': 'attribute_not_exists(pk)'}
        self.db.put_item(**args)
        sent = self.raw.put_item.call_args.kwargs['Item']
        self.assertEqual(sent['pk']['S'], 'CONTROL#INTEGRATION_PROBE#' + self.owner + '#wallet')
        self.assertEqual(sent['probe_owner'], {'S': self.owner})
        self.assertEqual(args['Item'], {'pk': {'S': 'wallet'}})

    def test_entire_transaction_is_validated_before_any_write(self):
        good = {'Put': {'TableName': 'stock-automation-paper', 'Item': {'pk': {'S': 'event'}}, 'ConditionExpression': 'attribute_not_exists(pk)'}}
        bad = {'Update': {'TableName': 'stock-automation-paper', 'Key': {'pk': {'S': 'WALLET#LIVE'}}, 'ConditionExpression': 'x = :x'}}
        with self.assertRaises(ValueError):
            self.db.transact_write_items(TransactItems=[good, bad])
        self.raw.transact_write_items.assert_not_called()

    def test_update_preserves_business_condition_and_adds_owner_fence(self):
        self.db.update_item(TableName='stock-automation-paper', Key={'pk': {'S': 'wallet'}},
                            ConditionExpression='available_cash >= :debit', ExpressionAttributeValues={':debit': {'N': '1'}})
        sent = self.raw.update_item.call_args.kwargs
        self.assertEqual(sent['ConditionExpression'], '(available_cash >= :debit) AND probe_owner = :probe_owner')
        self.assertEqual(sent['ExpressionAttributeValues'][':probe_owner'], {'S': self.owner})

    def test_unconditional_write_and_delete_transaction_are_blocked(self):
        with self.assertRaises(ValueError):
            self.db.put_item(TableName='stock-automation-paper', Item={'pk': {'S': 'wallet'}})
        with self.assertRaises(ValueError):
            self.db.transact_write_items(TransactItems=[{'Delete': {'TableName': 'stock-automation-paper', 'Key': {'pk': {'S': 'event'}}}}])
        self.assertEqual(self.raw.mock_calls, [])

    def test_cleanup_refuses_foreign_owner(self):
        self.raw.get_item.return_value = {'Item': {'probe_owner': {'S': 'someone-else'}}}
        with self.assertRaisesRegex(RuntimeError, 'RECONCILIATION'):
            self.db.cleanup()
        self.raw.delete_item.assert_not_called()

    def test_cleanup_uses_owner_condition_and_checks_deletion(self):
        self.raw.get_item.side_effect = [{'Item': {'probe_owner': {'S': self.owner}}}, {}, {}]
        self.db.cleanup()
        self.assertEqual(self.raw.delete_item.call_args.kwargs['ConditionExpression'], 'probe_owner = :owner')
        self.assertEqual(self.raw.delete_item.call_count, 1)

    def test_wrong_mode_or_failed_network_never_writes(self):
        with self.assertRaises(ValueError):
            probe.contracts(self.raw, {'KIWOOM_MODE': 'live'}, network_check=Mock())
        with self.assertRaisesRegex(RuntimeError, 'not-ready'):
            probe.contracts(self.raw, {'KIWOOM_MODE': 'demo', 'LIVE_ORDER_ENABLED': '0', 'BUY_FEE_BPS': '1.5', 'SELL_FEE_BPS': '1.5', 'SELL_TAX_BPS': '20'}, network_check=Mock(side_effect=RuntimeError('not-ready')))
        self.assertEqual(self.raw.mock_calls, [])

    def test_cli_requires_explicit_confirmation_before_running_probe(self):
        with contextlib.redirect_stderr(io.StringIO()), patch('stock_automation.storage_contracts.run') as run:
            with self.assertRaises(SystemExit):
                build_parser().parse_args(['verify-storage-contract'])
            run.assert_not_called()
        with patch('stock_automation.storage_contracts.run', return_value=0) as run:
            self.assertEqual(main(['verify-storage-contract', '--confirm-isolated-probe']), 0)
            run.assert_called_once_with()

    def test_run_rejects_live_mode_before_constructing_any_aws_client(self):
        with patch.dict('os.environ', {'KIWOOM_MODE': 'live', 'LIVE_ORDER_ENABLED': '1'}), patch('boto3.client') as client, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.run(), 1)
            client.assert_not_called()
