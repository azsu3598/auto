"""Explicit, isolated storage contracts; never execute a strategy or submit orders.

Run only in the reviewed paper task. Every DynamoDB key is rewritten into a
unique CONTROL#INTEGRATION_PROBE namespace. No production wallet is reachable.
The clock and scheduled worker are not patched or called.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import re
import uuid


class ScopedDdb:
    def __init__(self, client, table, owner, labels):
        if table != 'stock-automation-paper' or not re.fullmatch('[a-f0-9]{32}', owner):
            raise ValueError('PAPER_PROBE_CONFIGURATION_REQUIRED')
        if not labels or any(not isinstance(label, str) or not label for label in labels):
            raise ValueError('EXPLICIT_PROBE_LABELS_REQUIRED')
        self.client, self.table, self.owner = client, table, owner
        self.keys = {label: 'CONTROL#INTEGRATION_PROBE#' + owner + '#' + label for label in labels}

    def prepare(self, args, operation):
        result = deepcopy(args)
        if result.get('TableName') != self.table:
            raise ValueError('PROBE_TABLE_ESCAPE')
        field = 'Item' if operation == 'Put' else 'Key'
        raw_key = result[field]['pk']['S']
        if raw_key not in self.keys:
            raise ValueError('PROBE_KEY_ESCAPE')
        result[field]['pk']['S'] = self.keys[raw_key]
        if operation == 'Put':
            if 'probe_owner' in result['Item']:
                raise ValueError('RESERVED_PROBE_OWNER')
            result['Item']['probe_owner'] = {'S': self.owner}
            if result.get('ConditionExpression') != 'attribute_not_exists(pk)':
                raise ValueError('PROBE_CREATE_CONDITION_REQUIRED')
        elif operation == 'Update':
            values = result.setdefault('ExpressionAttributeValues', {})
            if ':probe_owner' in values or not result.get('ConditionExpression'):
                raise ValueError('PROBE_UPDATE_CONDITION_REQUIRED')
            result['ConditionExpression'] = '(' + result['ConditionExpression'] + ') AND probe_owner = :probe_owner'
            values[':probe_owner'] = {'S': self.owner}
        return result

    def put_item(self, **args):
        return self.client.put_item(**self.prepare(args, 'Put'))

    def get_item(self, **args):
        return self.client.get_item(**self.prepare(args, 'Get'))

    def update_item(self, **args):
        return self.client.update_item(**self.prepare(args, 'Update'))

    def transact_write_items(self, *, TransactItems):
        prepared = []
        for action in TransactItems:
            if len(action) != 1 or next(iter(action)) not in ('Put', 'Update'):
                raise ValueError('PROBE_TRANSACTION_OPERATION_NOT_ALLOWED')
            operation = next(iter(action))
            prepared.append({operation: self.prepare(action[operation], operation)})
        return self.client.transact_write_items(TransactItems=prepared)

    def cleanup(self):
        failures = []
        for key in self.keys.values():
            try:
                args = {'TableName': self.table, 'Key': {'pk': {'S': key}}}
                item = self.client.get_item(**args, ConsistentRead=True).get('Item')
                if not item:
                    continue
                if item.get('probe_owner') != {'S': self.owner}:
                    raise ValueError('PROBE_CLEANUP_OWNER_MISMATCH')
                self.client.delete_item(**args, ConditionExpression='probe_owner = :owner',
                                        ExpressionAttributeValues={':owner': {'S': self.owner}})
                if self.client.get_item(**args, ConsistentRead=True).get('Item'):
                    raise ValueError('PROBE_CLEANUP_NOT_EMPTY')
            except Exception:
                failures.append(key)
        if failures:
            raise RuntimeError('PROBE_CLEANUP_REQUIRES_RECONCILIATION')


def contracts(raw_ddb, env, *, network_check):
    from stock_automation.aws_runtime import _load_or_create_wallet, _wallet_entry_action, _wallet_exit_action
    from stock_automation.backtest import TradingCosts
    from stock_automation.runtime_safety import RuntimeRejected, acquire_attempt, finish_attempt
    if env.get('KIWOOM_MODE') != 'demo' or env.get('LIVE_ORDER_ENABLED') != '0':
        raise ValueError('PAPER_ONLY_REQUIRED')
    if (float(env['BUY_FEE_BPS']), float(env['SELL_FEE_BPS']), float(env['SELL_TAX_BPS'])) != (1.5, 1.5, 20.0):
        raise ValueError('REVIEWED_COST_CONFIGURATION_REQUIRED')
    network_check()
    now = datetime.now(timezone.utc)
    occurrence = now.isoformat()
    phase = 'INTEGRATION_STORAGE_ONLY'
    attempt_label = 'CONTROL#RUN#' + phase + '#' + occurrence
    wallets = ('CLOSING_KRX', 'MEDIUM_TERM', 'DAY_TRADE')
    labels = [*wallets, attempt_label, 'ENTRY_EVENT', 'OVERDRAW_EVENT', 'PARTIAL_EVENT', 'FINAL_EVENT', 'OVERSALE_EVENT']
    scoped = ScopedDdb(raw_ddb, env['PAPER_TABLE'], uuid.uuid4().hex, labels)
    table = env['PAPER_TABLE']
    checks = ['current_boot_network_and_egress']
    costs = TradingCosts(buy_fee_bps=1.5, sell_fee_bps=1.5, sell_tax_bps=20.0)
    def require(condition, code):
        if not condition:
            raise RuntimeError(code)
        checks.append(code)
    def read(label):
        return scoped.get_item(TableName=table, Key={'pk': {'S': label}}, ConsistentRead=True).get('Item', {})
    def number(item, key):
        return int(item[key]['N'])
    def event(label):
        return {'Put': {'TableName': table, 'Item': {'pk': {'S': label}, 'kind': {'S': 'STORAGE_CONTRACT_ONLY'}},
                        'ConditionExpression': 'attribute_not_exists(pk)'}}
    try:
        for label, cash in zip(wallets, (600000, 700000, 500000)):
            require(_load_or_create_wallet(scoped, table, label, cash, now) == cash, 'create_' + label)
        require(_load_or_create_wallet(scoped, table, wallets[0], 999999, now) == 600000, 'existing_cash_never_reset')
        before_other = [read(label) for label in wallets[1:]]
        attempt = acquire_attempt(scoped, table, phase, occurrence, now)
        require(read(attempt_label)['status']['S'] == 'RUNNING', 'attempt_running')
        try:
            finish_attempt(scoped, table, (attempt[0], 'wrong-owner'), 'COMPLETED', now)
        except Exception as error:
            require(getattr(error, 'response', {}).get('Error', {}).get('Code') == 'ConditionalCheckFailedException', 'wrong_attempt_owner_rejected')
        else:
            raise RuntimeError('WRONG_OWNER_ACCEPTED')
        finish_attempt(scoped, table, attempt, 'COMPLETED', now)
        require(read(attempt_label)['status']['S'] == 'COMPLETED', 'attempt_completed')
        try:
            acquire_attempt(scoped, table, phase, occurrence, now)
        except RuntimeRejected as error:
            require(str(error) == 'DUPLICATE_OR_UNRECONCILED_ATTEMPT', 'duplicate_completed_attempt_rejected')
        else:
            raise RuntimeError('DUPLICATE_ATTEMPT_ACCEPTED')
        entry = _wallet_entry_action(table, wallets[0], price=20000, quantity=2, costs=costs, now=now)
        actions = [entry, event('ENTRY_EVENT')]
        scoped.transact_write_items(TransactItems=actions)
        item = read(wallets[0])
        require((number(item, 'available_cash'), number(item, 'invested_principal'), number(item, 'fees_taxes')) == (559994, 40000, 6), 'atomic_wallet_debit_and_fee')
        try:
            scoped.transact_write_items(TransactItems=actions)
        except Exception as error:
            require(getattr(error, 'response', {}).get('Error', {}).get('Code') == 'TransactionCanceledException', 'duplicate_event_transaction_rejected')
            require([r.get('Code') for r in error.response.get('CancellationReasons', [])] == ['None', 'ConditionalCheckFailed'], 'duplicate_event_condition_verified')
        else:
            raise RuntimeError('DUPLICATE_EVENT_ACCEPTED')
        require(read(wallets[0]) == item, 'duplicate_event_no_second_debit')
        overdraw = _wallet_entry_action(table, wallets[0], price=1000000, quantity=1, costs=costs, now=now)
        try:
            scoped.transact_write_items(TransactItems=[overdraw, event('OVERDRAW_EVENT')])
        except Exception as error:
            require(getattr(error, 'response', {}).get('Error', {}).get('Code') == 'TransactionCanceledException', 'overdraw_transaction_rejected')
            require([r.get('Code') for r in error.response.get('CancellationReasons', [])] == ['ConditionalCheckFailed', 'None'], 'overdraw_condition_verified')
        else:
            raise RuntimeError('OVERDRAW_ACCEPTED')
        require(read(wallets[0]) == item and not read('OVERDRAW_EVENT'), 'failed_transaction_has_no_partial_write')
        partial, _ = _wallet_exit_action(table, wallets[0], entry_price=20000, exit_price=22000, quantity=1, costs=costs, now=now)
        scoped.transact_write_items(TransactItems=[partial, event('PARTIAL_EVENT')])
        item = read(wallets[0])
        require((number(item, 'available_cash'), number(item, 'invested_principal'), number(item, 'realized_pnl'), number(item, 'fees_taxes')) == (581947, 20000, 1950, 53), 'partial_credit_principal_and_costs')
        final, _ = _wallet_exit_action(table, wallets[0], entry_price=20000, exit_price=21000, quantity=1, costs=costs, now=now)
        scoped.transact_write_items(TransactItems=[final, event('FINAL_EVENT')])
        item = read(wallets[0])
        require((number(item, 'available_cash'), number(item, 'invested_principal'), number(item, 'realized_pnl'), number(item, 'fees_taxes')) == (602902, 0, 2902, 98), 'final_credit_and_cash_reconciliation')
        try:
            scoped.transact_write_items(TransactItems=[final, event('OVERSALE_EVENT')])
        except Exception as error:
            require(getattr(error, 'response', {}).get('Error', {}).get('Code') == 'TransactionCanceledException', 'excess_exit_transaction_rejected')
            require([r.get('Code') for r in error.response.get('CancellationReasons', [])] == ['ConditionalCheckFailed', 'None'], 'excess_exit_condition_verified')
        else:
            raise RuntimeError('EXCESS_EXIT_ACCEPTED')
        require(read(wallets[0]) == item and not read('OVERSALE_EVENT'), 'excess_exit_has_no_partial_write')
        require([read(label) for label in wallets[1:]] == before_other, 'other_strategy_wallets_unchanged')
    finally:
        scoped.cleanup()
    checks.append('owned_probe_records_removed')
    return {'ok': True, 'checks': checks, 'scope': 'ISOLATED_STORAGE_CONTRACT',
            'normal_time_worker_verified': False, 'broker_calls': False, 'production_wallet_writes': False}


def run():
    import boto3
    import urllib.request
    from botocore.config import Config
    from stock_automation.runtime_safety import verify_network
    try:
        if os.environ.get('KIWOOM_MODE') != 'demo' or os.environ.get('LIVE_ORDER_ENABLED') != '0':
            raise ValueError('PAPER_ONLY_REQUIRED')
        config = Config(connect_timeout=3, read_timeout=8, retries={'max_attempts': 1})
        s3, ec2, ddb = (boto3.client(service, config=config) for service in ('s3', 'ec2', 'dynamodb'))
        def probe():
            with urllib.request.urlopen('https://checkip.amazonaws.com', timeout=5) as response:
                return response.read(65).decode('ascii').strip()
        result = contracts(ddb, os.environ, network_check=lambda: verify_network(
            s3=s3, ec2=ec2, env=os.environ, now=datetime.now(timezone.utc), egress_probe=probe))
        print(json.dumps(result), flush=True)
        return 0
    except Exception as error:
        report = {'ok': False, 'kind': 'ISOLATED_STORAGE_CONTRACT', 'error_type': type(error).__name__}
        if re.fullmatch('[A-Za-z_]{1,90}', str(error)):
            report['reason'] = str(error)
        print(json.dumps(report), flush=True)
        return 1
