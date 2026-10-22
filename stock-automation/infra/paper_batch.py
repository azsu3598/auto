"""Five dated paper sessions after verified predecessor completion.

No broker orders, ledger writes, schedule mutation, or automatic HALT reset.
The original one-session pilot and its immutable plan remain unchanged.
"""
import copy
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
import paper_pilot as p

LIMITS = {'SCAN_1450': (240, 300), 'SHORTLIST_1510': (180, 180),
          'ENTRY_1520': (59, 60), 'EQUITY_SNAPSHOT_1550': (180, 180),
          'EXIT_0905': (120, 120), 'EXIT_0910': (120, 120)}
EXPECTED = {'GATE': 'READY', 'START_PM': 'READY', 'START_AM': 'READY',
            'STOP_PM': 'STOP_REQUESTED', 'STOP_AM': 'STOP_REQUESTED',
            'REPORT_PM': 'REPORTED', 'REPORT_AM': 'REPORTED',
            **{name: 'COMPLETED' for name in p.PHASE_TIMES}}


def session_plan(batch, index):
    result = copy.deepcopy(batch['template'])
    entry, exit_day = batch['sessions'][index]['entry_date'], batch['sessions'][index]['exit_date']
    result.update(entry_date=entry, exit_date=exit_day,
                  decision_key='runs/' + entry.replace('-', '/') + '/KRX_1520/decision.json', events={})
    times = {'GATE': (9, 45), 'START_PM': (14, 40), 'STOP_PM': (16, 10),
             'REPORT_PM': (16, 15), 'START_AM': (8, 55), 'STOP_AM': (9, 25), 'REPORT_AM': (9, 40)}
    def at(day, hm):
        return datetime.fromisoformat(day + 'T%02d:%02d:00+09:00' % hm).astimezone(timezone.utc)
    for name, hm in times.items():
        result['events'][name] = {'dispatch_at': at(exit_day if name.endswith('_AM') else entry, hm).isoformat()}
    for name, hm in p.PHASE_TIMES.items():
        occurrence = at(exit_day if name.startswith('EXIT_') else entry, hm)
        result['events'][name] = {'scheduled_at': occurrence.isoformat(),
            'dispatch_at': (occurrence-timedelta(minutes=2 if name == 'EXIT_0910' else 3)).isoformat()}
    return result


def validate_batch(batch):
    if (batch.get('paper_only') is not True or batch.get('starting_cash') != '600000'
            or len(batch.get('sessions', [])) != 5 or not re.fullmatch('[a-f0-9]{32}', batch.get('batch_id', ''))):
        raise ValueError('EXACT_FIVE_PAPER_SESSIONS_REQUIRED')
    parent = batch['parent']['plan']
    p.validate_plan(parent)
    p.validate_calendar(parent)
    previous = parent['exit_date']
    ids = {batch['parent']['pilot_id'], batch['batch_id']}
    for index, slot in enumerate(batch['sessions']):
        if slot['entry_date'] != previous or slot['pilot_id'] in ids or not re.fullmatch('[a-f0-9]{32}', slot['pilot_id']):
            raise ValueError('NONCONTIGUOUS_OR_DUPLICATE_SESSION')
        ids.add(slot['pilot_id'])
        plan = session_plan(batch, index)
        p.validate_calendar(plan)
        previous = slot['exit_date']
    if batch['template']['approved_calendar'] != parent['approved_calendar']:
        raise ValueError('CALENDAR_IDENTITY_CHANGED')


class DatedECS:
    """Add only the two plan-approved dates; preserve original launch guards."""
    def __init__(self, client, plan):
        self.client, self.plan = client, plan

    def __getattr__(self, name):
        return getattr(self.client, name)

    def run_task(self, **kwargs):
        values = kwargs['overrides']['containerOverrides'][0]['environment']
        if any(x['name'] in ('PILOT_ENTRY_DATE', 'PILOT_EXIT_DATE') for x in values):
            raise ValueError('DUPLICATE_DATE_OVERRIDE')
        values.extend([{'name': 'PILOT_ENTRY_DATE', 'value': self.plan['entry_date']},
                       {'name': 'PILOT_EXIT_DATE', 'value': self.plan['exit_date']}])
        return self.client.run_task(**kwargs)


class Batch(p.Pilot):
    def root_key(self, name):
        return self.root_prefix + '/' + name + '.json'

    def save_root(self, name, value, create=False):
        args = {'Bucket': self.env['PAPER_BUCKET'], 'Key': self.root_key(name),
                'Body': json.dumps(value).encode(), 'ContentType': 'application/json'}
        if create:
            args['IfNoneMatch'] = '*'
        self.clients['s3'].put_object(**args)

    def load(self):
        raw = self.clients['s3'].get_object(Bucket=self.env['PAPER_BUCKET'], Key=self.env['PLAN_KEY'])['Body'].read()
        if hashlib.sha256(raw).hexdigest() != self.env['PLAN_SHA256']:
            raise ValueError('BATCH_PLAN_HASH_MISMATCH')
        batch = json.loads(raw)
        validate_batch(batch)
        if batch['batch_id'] != self.env['PILOT_ID']:
            raise ValueError('WRONG_BATCH_ID')
        self.batch = batch
        self.root_prefix = self.env['RESULT_PREFIX']
        return batch

    def configuration(self, plan):
        # The registered task's two default dates remain the first session's.
        # RunTask supplies the approved current pair explicitly, without changing
        # command, image, secrets, phase clock, or runtime limits.
        review = copy.deepcopy(plan)
        review.update(entry_date=self.batch['sessions'][0]['entry_date'],
                      exit_date=self.batch['sessions'][0]['exit_date'])
        super().configuration(review)

    def idle(self):
        vm = self.clients['ec2'].describe_instances(InstanceIds=[self.env['NAT_INSTANCE_ID']])['Reservations'][0]['Instances'][0]
        cluster = self.clients['ecs'].describe_clusters(clusters=[self.env['CLUSTER_ARN']])['clusters'][0]
        if vm['State']['Name'] != 'stopped' or cluster['runningTasksCount'] or cluster['pendingTasksCount']:
            raise ValueError('PREVIOUS_CLEANUP_NOT_CURRENT')

    def halted(self):
        if self.get(self.root_key('STOP'), optional=True) is not None:
            raise ValueError('BATCH_MANUALLY_STOPPED')
        if self.get(self.root_key('HALT'), optional=True) is not None:
            raise ValueError('BATCH_NEW_ENTRIES_HALTED')

    def wallet(self, *, allow_uncreated=False):
        rows = self.rows()
        if any(r['pk']['S'].startswith(('OPEN#', 'PENDING#')) for r in rows):
            raise ValueError('UNRECONCILED_OPEN_OR_PENDING_STATE')
        wallets = [r for r in rows if r['pk']['S'].startswith('WALLET#')]
        if not wallets and allow_uncreated:
            return rows
        if len(wallets) != 1 or wallets[0]['pk']['S'] != 'WALLET#CLOSING_BET#KRX_1520':
            raise ValueError('ISOLATED_PAPER_WALLET_REQUIRED')
        wallet = wallets[0]
        if (wallet.get('initial_cash') != {'N': '600000'} or wallet.get('invested_principal') != {'N': '0'}
                or not re.fullmatch('[0-9]+', wallet.get('available_cash', {}).get('N', ''))):
            raise ValueError('PAPER_WALLET_NOT_RECONCILED')
        # Preserve cash and realized results. Never reset it to the initial sum.
        return rows

    def ledger_digest(self, rows):
        return p.digest([r for r in rows if not r['pk']['S'].startswith(('CONTROL#NETWORK#', 'CONTROL#ALERT'))])

    def completed(self, prefix, pilot_id, plan, require_digest=False):
        if self.get(prefix+'/STOP.json', optional=True) is not None:
            raise ValueError('PREDECESSOR_MANUALLY_STOPPED')
        reports = {}
        for name, expected in EXPECTED.items():
            marker = self.get(prefix+'/'+name+'.json', optional=True) or {}
            at = p.stamp(plan['events'][name]['dispatch_at'])
            if marker.get('status') != expected or marker.get('pilot_id') != pilot_id:
                raise ValueError('PREDECESSOR_NOT_COMPLETED')
            if not at <= p.stamp(marker['started_at']) <= p.stamp(marker['finished_at']) <= min(self.clock(), at+timedelta(seconds=900)):
                raise ValueError('PREDECESSOR_TIME_INVALID')
            reports[name] = marker
        for name, (late, duration) in LIMITS.items():
            at = p.stamp(plan['events'][name]['scheduled_at'])
            key = 'CONTROL#RUN#'+name+'#'+at.astimezone(timezone.utc).isoformat()
            lease = self.clients['dynamodb'].get_item(TableName=self.env['PAPER_TABLE'],
                Key={'pk': {'S': key}}, ConsistentRead=True).get('Item', {})
            if (lease.get('status') != {'S': 'COMPLETED'}
                    or not re.fullmatch('[a-f0-9]{32}', lease.get('owner', {}).get('S', ''))
                    or not at <= p.stamp(lease['started_at']['S']) <= at+timedelta(seconds=late)
                    or not p.stamp(lease['started_at']['S']) <= p.stamp(lease['finished_at']['S']) <= at+timedelta(seconds=late+duration+10)):
                raise ValueError('PREDECESSOR_REAL_LEASE_NOT_VERIFIED')
        artifact = self.get(plan['decision_key'])
        if artifact.get('decision') not in ('BUY', 'NO_TRADE') or not artifact.get('idempotency_key'):
            raise ValueError('PREDECESSOR_DECISION_MISSING')
        record = self.clients['dynamodb'].get_item(TableName=self.env['PAPER_TABLE'],
            Key={'pk': {'S': artifact['idempotency_key']}}, ConsistentRead=True).get('Item', {})
        if json.loads(record.get('payload_json', {}).get('S', '{}')) != artifact:
            raise ValueError('PREDECESSOR_DECISION_LEDGER_DIFFERS')
        detail = reports['REPORT_AM'].get('report', {})
        if detail.get('decision') != artifact['decision'] or detail.get('open_positions') != 0 or detail.get('network_stopped_and_idle') is not True:
            raise ValueError('PREDECESSOR_FINAL_REPORT_NOT_CLEAN')
        rows = self.wallet(allow_uncreated=reports['REPORT_AM'].get('report', {}).get('decision') == 'NO_TRADE')
        if require_digest and reports['REPORT_AM'].get('ledger_digest') != self.ledger_digest(rows):
            raise ValueError('LEDGER_CHANGED_AFTER_REPORT')
        self.idle()

    def predecessor(self, index):
        if index == 0:
            parent = self.batch['parent']
            return parent['prefix'], parent['pilot_id'], parent['plan'], False
        slot = self.batch['sessions'][index-1]
        return (self.root_prefix+'/sessions/'+slot['entry_date'], slot['pilot_id'],
                session_plan(self.batch, index-1), True)

    def gate(self, plan):
        self.halted()
        armed = self.get(self.root_key('ARMED'))
        if armed.get('status') != 'ARMED' or armed.get('plan_sha256') != self.env['PLAN_SHA256']:
            raise ValueError('BATCH_NOT_ARMED')
        self.proof(plan)
        self.configuration(plan)
        self.completed(*self.predecessor(self.index))
        self.save('ready', {'status': 'READY', 'pilot_id': self.env['PILOT_ID'],
            'plan_sha256': self.env['PLAN_SHA256'], 'checked_at': self.clock().isoformat()}, create=True)
        return 'READY'

    def require_ready(self, plan):
        # A phase failure halts new entry but does not suppress the scheduled
        # risk review/exit for an already-created virtual position. Manual STOP
        # fences all launches; cleanup and reports remain independently callable.
        if self.action not in ('START_AM', 'EXIT_0905', 'EXIT_0910'):
            self.halted()
        elif self.get(self.root_key('STOP'), optional=True) is not None:
            raise ValueError('BATCH_MANUALLY_STOPPED')
        super().require_ready(plan)

    def run(self, name, item, plan):
        original = self.clients['ecs']
        self.clients['ecs'] = DatedECS(original, plan)
        try:
            return super().run(name, item, plan)
        finally:
            self.clients['ecs'] = original

    def handle(self, event):
        batch = self.load()
        if event == {'action': 'DEPLOYMENT_CHECK', 'batch_id': batch['batch_id']}:
            if self.clock() >= p.stamp(session_plan(batch, 0)['events']['GATE']['dispatch_at']):
                raise ValueError('DEPLOYMENT_REVIEW_WINDOW_CLOSED')
            self.halted()
            plan = session_plan(batch, 0)
            self.configuration(plan)
            self.proof(plan)
            self.rows()
            self.idle()
            self.get(self.root_key('ARMED'), optional=True)
            parent = batch['parent']
            if self.get(parent['prefix']+'/STOP.json', optional=True) is not None:
                raise ValueError('PREDECESSOR_MANUALLY_STOPPED')
            raw = self.clients['s3'].get_object(Bucket=self.env['PAPER_BUCKET'], Key=parent['plan_key'])['Body'].read()
            if hashlib.sha256(raw).hexdigest() != parent['plan_sha256'] or json.loads(raw) != parent['plan']:
                raise ValueError('PARENT_IMMUTABLE_PLAN_CHANGED')
            if (self.get(parent['prefix']+'/ARMED.json') or {}).get('plan_sha256') != parent['plan_sha256']:
                raise ValueError('PARENT_NOT_ARMED')
            self.get(parent['prefix']+'/REPORT_AM.json', optional=True)
            return {'status': 'DEPLOYMENT_VERIFIED', 'paper_only': True, 'mutations': False,
                    'predecessor_success': 'PENDING_REAL_EXECUTION'}
        if set(event) != {'action', 'batch_id', 'scheduled_at'} or event['batch_id'] != batch['batch_id'] or event['action'] not in EXPECTED:
            raise ValueError('WRONG_BATCH_EVENT')
        name = event['action']
        occurrence = p.stamp(event['scheduled_at'])
        matches = [(i, session_plan(batch, i)) for i in range(5)
            if p.stamp(session_plan(batch, i)['events'][name]['dispatch_at']) == occurrence]
        if len(matches) != 1:
            raise ValueError('OUTSIDE_APPROVED_FIVE_SESSIONS')
        if not occurrence <= self.clock() <= occurrence+timedelta(seconds=60):
            raise ValueError('OUTSIDE_DISPATCH_WINDOW')
        self.index, plan = matches[0]
        self.action = name
        slot = batch['sessions'][self.index]
        self.env = dict(self.env, PILOT_ID=slot['pilot_id'],
                        RESULT_PREFIX=self.root_prefix+'/sessions/'+slot['entry_date'])
        if self.get(self.key(name), optional=True) is not None:
            return {'status': 'ALREADY_ATTEMPTED', 'phase': name}
        state = {'status': 'RUNNING', 'pilot_id': slot['pilot_id'], 'started_at': self.clock().isoformat()}
        self.save(name, state, create=True)
        try:
            if name == 'GATE':
                status = self.gate(plan)
            elif name.startswith('REPORT_'):
                status = self.report(name, plan)
                state['report'] = self.report_detail
                if name == 'REPORT_AM' and status == 'REPORTED':
                    self.wallet()
                    state['ledger_digest'] = self.ledger_digest(self.rows())
            elif name.startswith('STOP_'):
                status = 'NO_OWN_START' if self.get(self.key('START_'+name[-2:]), optional=True) is None else self.controller(
                    'STOP', 'morning' if name.endswith('_AM') else 'afternoon', plan['events'][name]['dispatch_at'])
            else:
                self.require_ready(plan)
                status = self.controller('START', 'morning' if name.endswith('_AM') else 'afternoon', plan['events'][name]['dispatch_at']) if name.startswith('START_') else self.run(name, plan['events'][name], plan)
            state['status'] = status
            if status == 'RECONCILIATION_REQUIRED':
                self.save_root('HALT', {'status': 'NEW_ENTRIES_HALTED', 'phase': name, 'at': self.clock().isoformat()}, create=True)
        except Exception as error:
            reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Z0-9_]+', str(error)) else type(error).__name__
            state.update(status='BLOCKED_OR_FAILED', reason=reason)
            if self.get(self.root_key('HALT'), optional=True) is None:
                self.save_root('HALT', {'status': 'NEW_ENTRIES_HALTED', 'phase': name, 'reason': reason,
                    'at': self.clock().isoformat()}, create=True)
        state['finished_at'] = self.clock().isoformat()
        self.save(name, state)
        if name == 'GATE' or state['status'] in ('BLOCKED_OR_FAILED', 'RECONCILIATION_REQUIRED'):
            try:
                self.notify(slot['entry_date']+' '+name+': '+state['status']+'. '+state.get('reason', 'Bounded five-session paper batch.'))
            except Exception:
                pass
        return {'status': state['status'], 'phase': name, 'entry_date': slot['entry_date']}


def handler(event, context):
    import boto3
    from botocore.config import Config
    try:
        clients = {name: boto3.client(name, config=Config(connect_timeout=3,
            read_timeout=230 if name == 'lambda' else 8, retries={'max_attempts': 0 if name == 'lambda' else 1}))
            for name in ('s3', 'ec2', 'ecs', 'dynamodb', 'cloudformation', 'lambda', 'scheduler', 'secretsmanager')}
        result = Batch(clients, os.environ).handle(event)
    except Exception as error:
        result = {'status': 'BATCH_REJECTED_OR_FAILED'}
        for key, value in (('error_code', getattr(error, 'response', {}).get('Error', {}).get('Code', type(error).__name__)),
                           ('operation', getattr(error, 'operation_name', ''))):
            if isinstance(value, str) and re.fullmatch('[A-Za-z0-9_]+', value):
                result[key] = value
        if isinstance(error, ValueError) and re.fullmatch('[A-Z0-9_]+', str(error)):
            result['reason'] = str(error)
    print(json.dumps(result))
    return result
