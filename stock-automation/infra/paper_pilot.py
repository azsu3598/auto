"""One dated closing-bet paper session, gated on an independent morning PASS.

All schedules are one-off. No schedule mutation, broker orders, or ledger writes
are available to this controller. The unchanged paper worker owns simulated cash.
"""
import hashlib
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
PHASE_TIMES = {'SCAN_1450': (14, 50), 'SHORTLIST_1510': (15, 10),
    'ENTRY_1520': (15, 20), 'EQUITY_SNAPSHOT_1550': (15, 50),
    'EXIT_0905': (9, 5), 'EXIT_0910': (9, 10)}


def stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return result


def digest(rows):
    return hashlib.sha256(json.dumps(sorted(rows, key=lambda r: r['pk']['S']), sort_keys=True).encode()).hexdigest()


def validate_plan(plan, now=None):
    entry, exit_day = plan['entry_date'], plan['exit_date']
    if exit_day <= entry or plan['starting_cash'] != '600000' or plan['paper_only'] is not True:
        raise ValueError('INVALID_PAPER_PLAN')
    expected = {'GATE', 'START_PM', 'STOP_PM', 'START_AM', 'STOP_AM', 'REPORT_PM', 'REPORT_AM', *PHASE_TIMES}
    if set(plan['events']) != expected:
        raise ValueError('EXACT_PILOT_EVENTS_REQUIRED')
    for name, item in plan['events'].items():
        dispatch = stamp(item['dispatch_at']).astimezone(KST)
        day = exit_day if name.endswith('_AM') or name.startswith('EXIT_') else entry
        if dispatch.date().isoformat() != day or dispatch.weekday() >= 5 or dispatch.second or dispatch.microsecond:
            raise ValueError('INVALID_PILOT_DATE')
        if name in PHASE_TIMES:
            occurrence = stamp(item['scheduled_at']).astimezone(KST)
            if (occurrence.date().isoformat() != day or (occurrence.hour, occurrence.minute) != PHASE_TIMES[name]
                    or occurrence.second or occurrence.microsecond
                    or (occurrence - dispatch).total_seconds() != (120 if name == 'EXIT_0910' else 180)):
                raise ValueError('INVALID_PHASE_OCCURRENCE')
        else:
            exact = {'GATE': (9, 25), 'START_PM': (14, 40), 'STOP_PM': (16, 10),
                'START_AM': (8, 55), 'STOP_AM': (9, 25), 'REPORT_PM': (16, 15), 'REPORT_AM': (9, 40)}[name]
            if (dispatch.hour, dispatch.minute) != exact:
                raise ValueError('INVALID_CONTROL_OCCURRENCE')
    if now is not None and not stamp(plan['events']['GATE']['dispatch_at']) <= now <= stamp(plan['events']['REPORT_AM']['dispatch_at']) + timedelta(minutes=5):
        raise ValueError('OUTSIDE_PILOT_DATES')


class Pilot:
    def __init__(self, clients, env, clock=None, sleep=time.sleep, monotonic=time.monotonic):
        self.clients, self.env = clients, env
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleep, self.monotonic = sleep, monotonic

    def get(self, key, optional=False):
        try:
            return json.loads(self.clients['s3'].get_object(Bucket=self.env['PAPER_BUCKET'], Key=key)['Body'].read())
        except Exception as error:
            if optional and getattr(error, 'response', {}).get('Error', {}).get('Code') in ('NoSuchKey', '404'):
                return None
            raise

    def key(self, name):
        return self.env['RESULT_PREFIX'] + '/' + name + '.json'

    def save(self, name, value, create=False):
        args = {'Bucket': self.env['PAPER_BUCKET'], 'Key': self.key(name),
            'Body': json.dumps(value).encode(), 'ContentType': 'application/json'}
        if create:
            args['IfNoneMatch'] = '*'
        self.clients['s3'].put_object(**args)

    def rows(self):
        args = {'TableName': self.env['PAPER_TABLE'], 'ConsistentRead': True, 'Limit': 200}
        rows = []
        for _ in range(10):
            response = self.clients['dynamodb'].scan(**args)
            rows.extend(response.get('Items', []))
            if not response.get('LastEvaluatedKey'):
                return rows
            args['ExclusiveStartKey'] = response['LastEvaluatedKey']
        raise ValueError('LEDGER_SCAN_INCOMPLETE')

    def proof(self, plan):
        proof = self.get(plan['morning_result_key'])
        if (proof.get('status') != 'PASSED' or proof.get('normal_time_worker_verified') is not True
                or proof.get('cleanup_complete') is not True or proof.get('test_id') != plan['morning_test_id']
                or proof.get('occurrence') != plan['morning_occurrence']
                or proof.get('task_definition') != plan['morning_task_definition']
                or stamp(proof['checked_at']) > self.clock()
                or stamp(proof['checked_at']) < stamp(plan['morning_occurrence'])):
            raise ValueError('MORNING_PASS_NOT_VERIFIED')
        key = 'CONTROL#RUN#EXIT_0905#' + stamp(plan['morning_occurrence']).astimezone(timezone.utc).isoformat()
        lease = self.clients['dynamodb'].get_item(TableName=self.env['PAPER_TABLE'], Key={'pk': {'S': key}}, ConsistentRead=True).get('Item', {})
        at = stamp(plan['morning_occurrence'])
        if (proof.get('worker_attempt_key') != key or lease.get('status') != {'S': 'COMPLETED'}
                or not re.fullmatch('[a-f0-9]{32}', lease.get('owner', {}).get('S', ''))
                or not at <= stamp(lease['started_at']['S']) <= at + timedelta(seconds=120)
                or not stamp(lease['started_at']['S']) <= stamp(lease['finished_at']['S']) <= at + timedelta(seconds=250)):
            raise ValueError('MORNING_ATTEMPT_NOT_VERIFIED')
        return proof, key

    def configuration(self, plan):
        for stack_name, expected in plan['stack_parameters'].items():
            stack = self.clients['cloudformation'].describe_stacks(StackName=stack_name)['Stacks'][0]
            if stack['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'):
                raise ValueError('STACK_NOT_STABLE')
            actual = {p['ParameterKey']: p['ParameterValue'] for p in stack['Parameters']}
            if any(actual.get(k) != v for k, v in expected.items()):
                raise ValueError('APP_CONFIGURATION_CHANGED')
        for schedule in plan['regular_schedules']:
            actual = self.clients['scheduler'].get_schedule(Name=schedule['name'], GroupName='default')
            if actual['Arn'] != schedule['arn'] or actual['State'] != 'DISABLED':
                raise ValueError('REGULAR_SCHEDULE_NOT_DISABLED')
        ecs = self.clients['ecs']
        production = ecs.describe_task_definition(taskDefinition=plan['production_task_definition'])['taskDefinition']
        trial = ecs.describe_task_definition(taskDefinition=self.env['TASK_DEFINITION_ARN'])['taskDefinition']
        if digest_task(production) != plan['production_task_hash']:
            raise ValueError('PRODUCTION_TASK_CHANGED')
        for name in ('taskRoleArn', 'executionRoleArn', 'cpu', 'memory', 'networkMode', 'volumes'):
            if trial.get(name) != production.get(name):
                raise ValueError('PILOT_ISOLATION_CHANGED')
        original, warm = production['containerDefinitions'][0], trial['containerDefinitions'][0]
        a = {k: v for k, v in original.items() if k not in ('command', 'entryPoint', 'environment')}
        b = {k: v for k, v in warm.items() if k not in ('command', 'entryPoint', 'environment')}
        env = {x['name']: x['value'] for x in warm['environment']}
        expected_env = {x['name']: x['value'] for x in original['environment']}
        expected_env.update(PILOT_ENTRY_DATE=plan['entry_date'], PILOT_EXIT_DATE=plan['exit_date'])
        if (a != b or env != expected_env or env['KIWOOM_MODE'] != 'demo' or env['LIVE_ORDER_ENABLED'] != '0'
                or env['STARTING_CASH'] != '600000' or warm.get('entryPoint') != ['python']
                or len(warm.get('command', [])) != 2 or warm['command'][0] != '-c'
                or hashlib.sha256(warm['command'][1].encode()).hexdigest() != plan['bootstrap_sha256']):
            raise ValueError('PAPER_CONTAINER_CHANGED')

    def gate(self, plan):
        proof, attempt = self.proof(plan)
        self.configuration(plan)
        rows = [r for r in self.rows() if not r['pk']['S'].startswith('CONTROL#NETWORK#') and r['pk']['S'] != attempt]
        if any(not r['pk']['S'].startswith('CONTROL#ALERT') for r in rows) or digest(rows) != proof['baseline_digest']:
            raise ValueError('EMPTY_BASELINE_CHANGED')
        vm = self.clients['ec2'].describe_instances(InstanceIds=[self.env['NAT_INSTANCE_ID']])['Reservations'][0]['Instances'][0]
        cluster = self.clients['ecs'].describe_clusters(clusters=[self.env['CLUSTER_ARN']])['clusters'][0]
        if vm['State']['Name'] != 'stopped' or cluster['runningTasksCount'] or cluster['pendingTasksCount']:
            raise ValueError('MORNING_CLEANUP_NOT_CURRENT')
        self.save('ready', {'status': 'READY', 'pilot_id': self.env['PILOT_ID'],
            'plan_sha256': self.env['PLAN_SHA256'], 'morning_proof_sha256': hashlib.sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest(),
            'checked_at': self.clock().isoformat()}, create=True)
        return 'READY'

    def require_ready(self, plan):
        ready = self.get(self.key('ready'))
        if (ready.get('status') != 'READY' or ready.get('pilot_id') != self.env['PILOT_ID']
                or ready.get('plan_sha256') != self.env['PLAN_SHA256']):
            raise ValueError('PILOT_NOT_READY')
        self.proof(plan)
        self.configuration(plan)

    def controller(self, action, window, at):
        response = self.clients['lambda'].invoke(FunctionName=self.env['CONTROL_FUNCTION_ARN'], InvocationType='RequestResponse',
            Payload=json.dumps({'action': action, 'window': window, 'scheduled_at': at}).encode())
        result = json.loads(response['Payload'].read())
        expected = 'READY' if action == 'START' else 'STOP_REQUESTED'
        if response.get('FunctionError') or result.get('state') != expected or (action == 'STOP' and result.get('cleanup_complete') is not True):
            raise ValueError('CONTROLLER_NOT_CONFIRMED')
        return expected

    def run(self, name, item, plan):
        cluster = self.clients['ecs'].describe_clusters(clusters=[self.env['CLUSTER_ARN']])['clusters'][0]
        if cluster['runningTasksCount'] or cluster['pendingTasksCount']:
            raise ValueError('EXISTING_TASK_PRESENT')
        # Entry also requires the two earlier real workers to have completed.
        if name in ('SHORTLIST_1510', 'ENTRY_1520'):
            prerequisites = ['SCAN_1450'] + (['SHORTLIST_1510'] if name == 'ENTRY_1520' else [])
            for phase in prerequisites:
                if (self.get(self.key(phase), optional=True) or {}).get('status') != 'COMPLETED':
                    raise ValueError('PREREQUISITE_NOT_COMPLETED')
        ecs = self.clients['ecs']
        token = hashlib.sha256((self.env['PILOT_ID'] + name).encode()).hexdigest()[:32]
        response = ecs.run_task(cluster=self.env['CLUSTER_ARN'], taskDefinition=self.env['TASK_DEFINITION_ARN'],
            count=1, launchType='FARGATE', platformVersion='LATEST', clientToken=token, startedBy=self.env['PILOT_ID'],
            networkConfiguration={'awsvpcConfiguration': {'subnets': self.env['SUBNET_IDS'].split(','),
                'securityGroups': self.env['SECURITY_GROUP_IDS'].split(','), 'assignPublicIp': 'DISABLED'}},
            overrides={'containerOverrides': [{'name': 'stock-automation', 'environment': [
                {'name': 'RUN_PHASE', 'value': name}, {'name': 'SCHEDULED_AT', 'value': item['scheduled_at']},
                {'name': 'DISPATCHED_AT', 'value': item['dispatch_at']}]}]})
        if response.get('failures') or len(response.get('tasks', [])) != 1:
            raise ValueError('TASK_LAUNCH_NOT_CONFIRMED')
        task_arn = response['tasks'][0]['taskArn']
        deadline = self.monotonic() + 660
        try:
            while self.monotonic() < deadline:
                result = ecs.describe_tasks(cluster=self.env['CLUSTER_ARN'], tasks=[task_arn])
                if result.get('failures') or len(result.get('tasks', [])) != 1:
                    raise ValueError('TASK_INSPECTION_FAILED')
                task = result['tasks'][0]
                if task['lastStatus'] == 'STOPPED':
                    break
                self.sleep(3)
            else:
                raise ValueError('TASK_BOUND_EXCEEDED')
            if [c.get('exitCode') for c in task['containers']] != [0]:
                raise ValueError('PAPER_WORKER_NOT_SUCCESSFUL')
            occurrence = stamp(item['scheduled_at']).astimezone(timezone.utc).isoformat()
            lease = self.clients['dynamodb'].get_item(TableName=self.env['PAPER_TABLE'],
                Key={'pk': {'S': 'CONTROL#RUN#' + name + '#' + occurrence}}, ConsistentRead=True).get('Item', {})
            if lease.get('status') != {'S': 'COMPLETED'}:
                raise ValueError('REAL_ATTEMPT_NOT_COMPLETED')
            return 'COMPLETED'
        except Exception:
            ecs.stop_task(cluster=self.env['CLUSTER_ARN'], task=task_arn, reason='Bounded one-session paper pilot cleanup')
            raise

    def report(self, name):
        rows = self.rows()
        open_count = sum(r['pk']['S'].startswith('OPEN#CLOSING_BET#') for r in rows)
        entry = self.get(self.key('ENTRY_1520'), optional=True) or {}
        exit_result = self.get(self.key('EXIT_0910'), optional=True) or {}
        # Worker COMPLETED proves execution, not a purchase or a successful exit.
        self.notify(name + ': entry_worker=' + entry.get('status', 'NO_RECORD')
            + '; exit_worker=' + exit_result.get('status', 'NO_RECORD') + '; open_positions=' + str(open_count)
            + ('. RECONCILIATION_REQUIRED.' if name == 'REPORT_AM' and open_count else '.'))
        return 'RECONCILIATION_REQUIRED' if name == 'REPORT_AM' and open_count else 'REPORTED'

    def notify(self, message):
        raw = self.clients['secretsmanager'].get_secret_value(SecretId=self.env['TELEGRAM_SECRET_ARN'])
        credentials = json.loads(raw['SecretString'])
        body = json.dumps({'chat_id': credentials['chat_id'], 'text': '[SABU PAPER PILOT] ' + message}).encode()
        request = urllib.request.Request('https://api.telegram.org/bot' + credentials['bot_token'] + '/sendMessage', data=body,
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=6) as response:
            if json.loads(response.read()).get('ok') is not True:
                raise ValueError('NOTIFICATION_REJECTED')

    def handle(self, event):
        raw = self.clients['s3'].get_object(Bucket=self.env['PAPER_BUCKET'], Key=self.env['PLAN_KEY'])['Body'].read()
        if hashlib.sha256(raw).hexdigest() != self.env['PLAN_SHA256']:
            raise ValueError('PLAN_HASH_MISMATCH')
        plan = json.loads(raw)
        validate_plan(plan, self.clock())
        if set(event) != {'action', 'pilot_id'} or event['pilot_id'] != self.env['PILOT_ID'] or event['action'] not in plan['events']:
            raise ValueError('WRONG_PILOT_EVENT')
        name = event['action']; item = plan['events'][name]
        if not stamp(item['dispatch_at']) <= self.clock() <= stamp(item['dispatch_at']) + timedelta(seconds=60):
            raise ValueError('OUTSIDE_DISPATCH_WINDOW')
        if self.get(self.key(name), optional=True) is not None:
            return {'status': 'ALREADY_ATTEMPTED', 'phase': name}
        state = {'status': 'RUNNING', 'pilot_id': self.env['PILOT_ID'], 'started_at': self.clock().isoformat()}
        self.save(name, state, create=True)
        try:
            if name == 'GATE':
                status = self.gate(plan)
            elif name.startswith('REPORT_'):
                status = self.report(name)
            elif name.startswith('STOP_'):
                # Cleanup never depends on READY or PASS; an own start attempt
                # is required, including one with an ambiguous start response.
                if self.get(self.key('START_' + name[-2:]), optional=True) is None:
                    status = 'NO_OWN_START'
                else:
                    status = self.controller('STOP', 'morning' if name.endswith('_AM') else 'afternoon', item['dispatch_at'])
            else:
                self.require_ready(plan)
                if name.startswith('START_'):
                    status = self.controller('START', 'morning' if name.endswith('_AM') else 'afternoon', item['dispatch_at'])
                else:
                    status = self.run(name, item, plan)
            state['status'] = status
        except Exception as error:
            reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Z0-9_]+', str(error)) else type(error).__name__
            state.update(status='BLOCKED_OR_FAILED', reason=reason)
        state['finished_at'] = self.clock().isoformat()
        self.save(name, state)
        if name == 'GATE' or state['status'] == 'BLOCKED_OR_FAILED':
            try:
                self.notify(name + ': ' + state['status'] + '. ' + state.get('reason', 'One dated paper session only; regular schedules remain OFF.'))
            except Exception:
                pass
        return {'status': state['status'], 'phase': name}


def digest_task(task):
    # SDK dates/metadata differ between JSON files and live reads. Hash only the
    # runtime configuration, including every environment and secret reference.
    names = ('taskDefinitionArn', 'family', 'revision', 'networkMode', 'cpu', 'memory', 'taskRoleArn',
        'executionRoleArn', 'volumes', 'containerDefinitions', 'requiresCompatibilities', 'runtimePlatform')
    return hashlib.sha256(json.dumps({k: task.get(k) for k in names}, sort_keys=True).encode()).hexdigest()


def handler(event, context):
    import boto3
    from botocore.config import Config
    try:
        clients = {name: boto3.client(name, config=Config(connect_timeout=3, read_timeout=230 if name == 'lambda' else 8,
            retries={'max_attempts': 0 if name == 'lambda' else 1})) for name in
            ('s3', 'ec2', 'ecs', 'dynamodb', 'cloudformation', 'lambda', 'scheduler', 'secretsmanager')}
        result = Pilot(clients, os.environ).handle(event)
    except Exception:
        result = {'status': 'PILOT_REJECTED_OR_FAILED'}
    print(json.dumps(result))
    return result
