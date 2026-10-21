"""One empty-position 09:05 paper worker test. Never enable trading schedules."""
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
import hashlib

KST = timezone(timedelta(hours=9))


def stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return result


def digest(rows):
    return hashlib.sha256(json.dumps(sorted(rows, key=lambda x: x['pk']['S']), sort_keys=True).encode()).hexdigest()


def error_summary(error):
    """Keep failure stages diagnosable without leaking raw AWS messages/ARNs."""
    code = getattr(error, 'response', {}).get('Error', {}).get('Code', type(error).__name__)
    operation = getattr(error, 'operation_name', '')
    return {k: v for k, v in {'code': code, 'operation': operation}.items()
        if isinstance(v, str) and re.fullmatch('[A-Za-z0-9_]+', v)}


def require_empty_business_ledger(rows, run_at, prior_attempt_keys=()):
    """Preserve explicitly reviewed, completed earlier empty-test run leases.

    Never delete a permanent run lease to repeat a test. A business record, an
    unreviewed control key, a running attempt or this occurrence remains blocked.
    """
    allowed = set(prior_attempt_keys)
    for row in rows:
        key = row['pk']['S']
        if key.startswith('CONTROL#ALERT'):
            continue
        prefix = 'CONTROL#RUN#EXIT_0905#'
        if key not in allowed or not key.startswith(prefix):
            raise ValueError('EMPTY_BUSINESS_LEDGER_REQUIRED')
        at = stamp(key[len(prefix):])
        local = at.astimezone(KST)
        if (local.date() >= run_at.astimezone(KST).date() or local.weekday() >= 5
                or (local.hour, local.minute, local.second, local.microsecond) != (9, 5, 0, 0)
                or row.get('status') != {'S': 'COMPLETED'}
                or not re.fullmatch('[a-f0-9]{32}', row.get('owner', {}).get('S', ''))
                or not at <= stamp(row['started_at']['S']) <= at + timedelta(seconds=120)
                or not stamp(row['started_at']['S']) <= stamp(row['finished_at']['S']) <= at + timedelta(seconds=250)):
            raise ValueError('HISTORICAL_EMPTY_ATTEMPT_NOT_VERIFIED')


def validate_event(event, env, now):
    run_at = stamp(env['RUN_AT'])
    local = run_at.astimezone(KST)
    if local.weekday() >= 5 or (local.hour, local.minute, local.second, local.microsecond) != (9, 5, 0, 0):
        raise ValueError('ONLY_REGULAR_0905_TEST_ALLOWED')
    if set(event) != {'action', 'test_id'} or event['test_id'] != env['TEST_ID']:
        raise ValueError('WRONG_VERIFICATION_EVENT')
    if event['action'] == 'RUN':
        begin, seconds = run_at - timedelta(minutes=3), 60
    elif event['action'] == 'WATCH':
        begin, seconds = stamp(env['WATCH_AT']), 300
    else:
        raise ValueError('UNSUPPORTED_VERIFICATION_ACTION')
    if not begin <= now <= begin + timedelta(seconds=seconds):
        raise ValueError('OUTSIDE_VERIFICATION_WINDOW')
    return run_at


class Verifier:
    def __init__(self, clients, env, clock=None, sleep=time.sleep, monotonic=time.monotonic):
        self.clients, self.env = clients, env
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleep, self.monotonic = sleep, monotonic
        self.state = None

    def save(self):
        self.clients['s3'].put_object(Bucket=self.env['PAPER_BUCKET'], Key=self.env['RESULT_KEY'],
            Body=json.dumps(self.state).encode(), ContentType='application/json')

    def rows(self):
        args = {'TableName': self.env['PAPER_TABLE'], 'ConsistentRead': True, 'Limit': 200}
        rows = []
        for _ in range(10):
            response = self.clients['dynamodb'].scan(**args)
            rows.extend(row for row in response.get('Items', []) if not row['pk']['S'].startswith('CONTROL#NETWORK#'))
            if not response.get('LastEvaluatedKey'):
                return rows
            args['ExclusiveStartKey'] = response['LastEvaluatedKey']
        raise ValueError('LEDGER_SCAN_INCOMPLETE')

    def instance(self):
        vm = self.clients['ec2'].describe_instances(InstanceIds=[self.env['NAT_INSTANCE_ID']])['Reservations'][0]['Instances'][0]
        tags = {t['Key']: t['Value'] for t in vm.get('Tags', [])}
        if tags.get('Project') != 'paper-fixed-egress' or tags.get('Name') != 'stock-automation-paper-nat':
            raise ValueError('NAT_IDENTITY_CHANGED')
        return vm

    def controller(self):
        response = self.clients['lambda'].invoke(FunctionName=self.env['CONTROL_FUNCTION_ARN'],
            InvocationType='RequestResponse', Payload=json.dumps({'action': 'VERIFY_STOP', 'test_id': self.env['TEST_ID']}).encode())
        result = json.loads(response['Payload'].read())
        if response.get('FunctionError') or result.get('state') != 'STOP_REQUESTED' or not result.get('cleanup_complete'):
            raise ValueError('CONTROLLER_STOP_NOT_CONFIRMED')

    def tasks(self):
        tasks = {}
        for desired in ('RUNNING', 'STOPPED'):
            args = {'cluster': self.env['CLUSTER_ARN'], 'desiredStatus': desired, 'maxResults': 100}
            for _ in range(10):
                page = self.clients['ecs'].list_tasks(**args)
                if page['taskArns']:
                    detail = self.clients['ecs'].describe_tasks(cluster=self.env['CLUSTER_ARN'], tasks=page['taskArns'])
                    if detail.get('failures'):
                        raise ValueError('TASK_INSPECTION_FAILED')
                    tasks.update({t['taskArn']: t for t in detail['tasks']})
                if not page.get('nextToken'):
                    break
                args['nextToken'] = page['nextToken']
            else:
                raise ValueError('TASK_SCAN_INCOMPLETE')
        return list(tasks.values())

    def preflight(self, run_at):
        cf, ecs = self.clients['cloudformation'], self.clients['ecs']
        app = cf.describe_stacks(StackName='stock-automation-paper')['Stacks'][0]
        params = {p['ParameterKey']: p['ParameterValue'] for p in app['Parameters']}
        outputs = {p['OutputKey']: p['OutputValue'] for p in app['Outputs']}
        if app['StackStatus'] != 'UPDATE_COMPLETE' or outputs['TaskDefinitionArn'] != self.env['PRODUCTION_TASK_DEFINITION_ARN']:
            raise ValueError('APP_REVISION_CHANGED')
        if params['ImageUri'] != self.env['EXPECTED_IMAGE_URI'] or any(params[k] != 'DISABLED' for k in ('CoreScheduleState', 'NxtScheduleState', 'AssignPublicIp')):
            raise ValueError('APP_ISOLATION_OR_SCHEDULE_CHANGED')
        control = cf.describe_stacks(StackName='stock-automation-paper-control')['Stacks'][0]
        if {p['ParameterKey']: p['ParameterValue'] for p in control['Parameters']}['ScheduleState'] != 'DISABLED':
            raise ValueError('CONTROL_SCHEDULE_CHANGED')
        if {p['OutputKey']: p['OutputValue'] for p in control['Outputs']}['ControlFunctionArn'] != self.env['CONTROL_FUNCTION_ARN']:
            raise ValueError('CONTROL_FUNCTION_CHANGED')
        network = cf.describe_stacks(StackName='stock-automation-paper-network')['Stacks'][0]
        if {p['OutputKey']: p['OutputValue'] for p in network['Outputs']}['StartScheduleState'] != 'DISABLED':
            raise ValueError('NETWORK_SCHEDULE_CHANGED')
        production = ecs.describe_task_definition(taskDefinition=self.env['PRODUCTION_TASK_DEFINITION_ARN'])['taskDefinition']
        diagnostic = ecs.describe_task_definition(taskDefinition=self.env['TASK_DEFINITION_ARN'])['taskDefinition']
        container = production['containerDefinitions'][0]
        trial = diagnostic['containerDefinitions'][0]
        task_env = {p['name']: p['value'] for p in container['environment']}
        if (container['image'] != self.env['EXPECTED_IMAGE_URI'] or container['user'] != '65534:65534'
                or not container['readonlyRootFilesystem'] or container.get('command') != ['aws-run']
                or task_env.get('KIWOOM_MODE') != 'demo' or task_env.get('LIVE_ORDER_ENABLED') != '0'):
            raise ValueError('TASK_SAFETY_CHANGED')
        if any(diagnostic.get(k) != production.get(k) for k in ('taskRoleArn', 'executionRoleArn', 'cpu', 'memory', 'networkMode', 'volumes')):
            raise ValueError('DIAGNOSTIC_TASK_CONFIGURATION_CHANGED')
        if {k: v for k, v in trial.items() if k not in ('entryPoint', 'command')} != {k: v for k, v in container.items() if k not in ('entryPoint', 'command')}:
            raise ValueError('DIAGNOSTIC_CONTAINER_CHANGED')
        if (trial.get('entryPoint') != ['python'] or len(trial.get('command', [])) != 2 or trial['command'][0] != '-c'
                or hashlib.sha256(trial['command'][1].encode()).hexdigest() != self.env['BOOTSTRAP_SHA256']):
            raise ValueError('PREWARM_SOURCE_CHANGED')
        cluster = ecs.describe_clusters(clusters=[self.env['CLUSTER_ARN']])['clusters'][0]
        if cluster['runningTasksCount'] or cluster['pendingTasksCount']:
            raise ValueError('EXISTING_TASK_PRESENT')
        rows = self.rows()
        if digest(rows) != self.state['baseline_digest']:
            raise ValueError('LEDGER_CHANGED_BEFORE_TEST')
        # No outbox, wallet, position, decision or equity record may be touched.
        # Reviewed earlier completed test leases remain permanent and unchanged.
        require_empty_business_ledger(rows, run_at, self.state.get('prior_attempt_keys', ()))
        vm = self.instance()
        proof = json.loads(self.clients['s3'].get_object(Bucket=self.env['PAPER_BUCKET'], Key='control/network/current.json')['Body'].read())
        start = stamp(self.env['START_AT'])
        now = self.clock()
        if (vm['State']['Name'] != 'running' or vm['SourceDestCheck']
                or not start <= vm['LaunchTime'] <= run_at
                or proof['state'] != 'READY' or proof['instance_id'] != self.env['NAT_INSTANCE_ID']
                or stamp(proof['launch_time']) != vm['LaunchTime']
                or not vm['LaunchTime'] <= stamp(proof['ready_at']) <= now < stamp(proof['expires_at'])
                or stamp(proof['expires_at']) > vm['LaunchTime'] + timedelta(minutes=120)):
            raise ValueError('CURRENT_BOOT_NOT_READY')
        self.state['launch_time'] = vm['LaunchTime'].isoformat()
        self.save()
        return container['name']

    def verify_task(self, task, run_at, container_name):
        if task['lastStatus'] != 'STOPPED' or [c.get('exitCode') for c in task['containers']] != [0]:
            raise ValueError('WORKER_NOT_SUCCESSFUL')
        stream = 'paper/' + container_name + '/' + task['taskArn'].rsplit('/', 1)[-1]
        lines = []
        for _ in range(6):
            response = self.clients['logs'].get_log_events(logGroupName=self.env['APP_LOG_GROUP'], logStreamName=stream, startFromHead=True, limit=500)
            lines = [r['message'] for r in response['events']]
            if lines:
                break
            self.sleep(2)
        parsed = []
        for line in lines:
            try:
                parsed.append(json.loads(line))
            except ValueError:
                continue
        if len([p for p in parsed if p.get('status') == 'EXIT_REVIEW_COMPLETE' and p.get('results') == []]) != 1:
            raise ValueError('EMPTY_EXIT_WORKER_LOG_NOT_VERIFIED')
        if any(p.get('status') in ('RUN_FAILED', 'RUN_REJECTED', 'RUN_TIMED_OUT', 'SKIPPED') for p in parsed):
            raise ValueError('WORKER_REJECTION_PRESENT')
        occurrence = run_at.astimezone(timezone.utc).isoformat()
        key = 'CONTROL#RUN#EXIT_0905#' + occurrence
        lease = self.clients['dynamodb'].get_item(TableName=self.env['PAPER_TABLE'], Key={'pk': {'S': key}}, ConsistentRead=True).get('Item', {})
        if (lease.get('status') != {'S': 'COMPLETED'} or not re.fullmatch('[a-f0-9]{32}', lease.get('owner', {}).get('S', ''))
                or not run_at <= stamp(lease['started_at']['S']) <= run_at + timedelta(seconds=120)
                or not stamp(lease['started_at']['S']) <= stamp(lease['finished_at']['S']) <= run_at + timedelta(seconds=250)):
            raise ValueError('REAL_WORKER_ATTEMPT_NOT_COMPLETED')
        if digest([row for row in self.rows() if row['pk']['S'] != key]) != self.state['baseline_digest']:
            raise ValueError('UNEXPECTED_LEDGER_CHANGE')
        self.state['worker_attempt_key'] = key
        self.state['checks'] = ['pinned_image_and_schedules_off', 'empty_business_ledger', 'current_boot_ready',
            'real_0905_worker_exit_zero', 'empty_exit_log', 'real_attempt_completed', 'no_business_ledger_change']
        self.state['normal_time_worker_verified'] = True

    def cleanup(self):
        ecs = self.clients['ecs']
        inventory_error = None
        try:
            tasks = self.tasks()
        except Exception as error:
            # A denied inventory read must not skip the independent bounded
            # controller/host stop. Preserve FAILED until reconciliation.
            inventory_error = error
            self.state['cleanup_inventory_error'] = error_summary(error)
            tasks = []
        active_own_tasks = [task for task in tasks
            if task.get('startedBy') == self.env['TEST_ID'] and task['lastStatus'] != 'STOPPED']
        for task in active_own_tasks:
            if task.get('startedBy') == self.env['TEST_ID'] and task['lastStatus'] != 'STOPPED':
                ecs.stop_task(cluster=self.env['CLUSTER_ARN'], task=task['taskArn'], reason='Bounded normal-time paper verification cleanup')
        vm = self.instance()
        expected_launch = self.state.get('launch_time')
        if expected_launch and stamp(expected_launch) != vm['LaunchTime']:
            raise ValueError('CLEANUP_BOOT_CHANGED')
        if vm['State']['Name'] == 'stopped':
            if inventory_error or active_own_tasks:
                raise ValueError('TASK_CLEANUP_NOT_CONFIRMED')
            return
        # If preflight never completed, require this test's control-start lease
        # and the planned boot window before touching the existing NAT.
        if not expected_launch:
            key = 'CONTROL#NETWORK#START#manual-' + self.env['TEST_ID']
            lease = self.clients['dynamodb'].get_item(TableName=self.env['PAPER_TABLE'], Key={'pk': {'S': key}}, ConsistentRead=True).get('Item')
            if not lease or not stamp(self.env['START_AT']) <= vm['LaunchTime'] <= stamp(self.env['RUN_AT']):
                raise ValueError('CLEANUP_BOOT_NOT_OWNED')
        try:
            self.controller()
        finally:
            current = self.instance()
            if current['LaunchTime'] != vm['LaunchTime']:
                raise ValueError('CLEANUP_BOOT_CHANGED')
            if current['State']['Name'] != 'stopped':
                self.clients['ec2'].stop_instances(InstanceIds=[self.env['NAT_INSTANCE_ID']])
        deadline = self.monotonic() + 75
        while self.monotonic() < deadline:
            current = self.instance()
            if current['LaunchTime'] != vm['LaunchTime']:
                raise ValueError('CLEANUP_BOOT_CHANGED')
            if current['State']['Name'] == 'stopped':
                if inventory_error:
                    raise ValueError('TASK_INVENTORY_REQUIRES_RECONCILIATION')
                return
            self.sleep(3)
        raise ValueError('NAT_STOP_NOT_CONFIRMED')

    def notify(self, status):
        raw = self.clients['secretsmanager'].get_secret_value(SecretId=self.env['TELEGRAM_SECRET_ARN'])
        credentials = json.loads(raw['SecretString'])
        body = json.dumps({'chat_id': credentials['chat_id'],
            'text': '[SABU PAPER] 09:05 worker test: ' + status + '. Trading schedules remain OFF.'}).encode()
        request = urllib.request.Request('https://api.telegram.org/bot' + credentials['bot_token'] + '/sendMessage', data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=6) as response:
            if json.loads(response.read()).get('ok') is not True:
                raise ValueError('NOTIFICATION_REJECTED')

    def handle(self, event):
        run_at = validate_event(event, self.env, self.clock())
        self.state = json.loads(self.clients['s3'].get_object(Bucket=self.env['PAPER_BUCKET'], Key=self.env['RESULT_KEY'])['Body'].read())
        if (self.state.get('test_id') != self.env['TEST_ID'] or self.state.get('occurrence') != self.env['RUN_AT']
                or self.state.get('task_definition') != self.env['TASK_DEFINITION_ARN']):
            raise ValueError('WRONG_TEST_MARKER')
        if self.state.get('status') in ('PASSED', 'FAILED'):
            return {'status': 'ALREADY_FINAL'}
        reason, passed = 'UNRECONCILED_OR_MISSING_RUN', False
        try:
            if event['action'] != 'RUN' or self.state.get('status') != 'ARMED':
                raise ValueError(reason)
            self.state.update(status='RUNNING', started_at=self.clock().isoformat())
            self.save()
            container = self.preflight(run_at)
            # Preserve the original scheduled occurrence. The deployed parent and
            # worker still enforce their real clocks and normal phase deadlines.
            response = self.clients['ecs'].run_task(cluster=self.env['CLUSTER_ARN'], taskDefinition=self.env['TASK_DEFINITION_ARN'],
                count=1, launchType='FARGATE', platformVersion='LATEST', clientToken=self.env['TEST_ID'], startedBy=self.env['TEST_ID'],
                networkConfiguration={'awsvpcConfiguration': {'subnets': self.env['SUBNET_IDS'].split(','),
                    'securityGroups': self.env['SECURITY_GROUP_IDS'].split(','), 'assignPublicIp': 'DISABLED'}},
                overrides={'containerOverrides': [{'name': container, 'environment': [
                    {'name': 'RUN_PHASE', 'value': 'EXIT_0905'}, {'name': 'SCHEDULED_AT', 'value': self.env['RUN_AT']}]}]})
            if response.get('failures') or len(response.get('tasks', [])) != 1:
                raise ValueError('TASK_LAUNCH_NOT_CONFIRMED')
            task_arn = response['tasks'][0]['taskArn']
            self.state['task_arn'] = task_arn
            self.save()
            deadline = self.monotonic() + 480
            while self.monotonic() < deadline:
                detail = self.clients['ecs'].describe_tasks(cluster=self.env['CLUSTER_ARN'], tasks=[task_arn])
                if detail.get('failures'):
                    raise ValueError('TASK_INSPECTION_FAILED')
                task = detail['tasks'][0]
                if task['lastStatus'] == 'STOPPED':
                    break
                self.sleep(4)
            else:
                raise ValueError('TASK_BOUND_EXCEEDED')
            self.verify_task(task, run_at, container)
            passed, reason = True, 'NORMAL_TIME_EMPTY_EXIT_VERIFIED'
        except Exception as error:
            reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Z0-9_]+', str(error)) else type(error).__name__
            self.state['worker_error'] = error_summary(error)
        self.state['worker_reason'] = reason
        try:
            self.cleanup()
            self.state['cleanup_complete'] = True
        except Exception as error:
            passed, reason = False, 'CLEANUP_REQUIRES_RECONCILIATION'
            self.state['cleanup_complete'] = False
            self.state['cleanup_error'] = error_summary(error)
        status = 'PASSED' if passed else 'FAILED'
        self.state.update(status=status, reason=reason, checked_at=self.clock().isoformat(), trading_schedules_changed=False)
        self.save()
        try:
            self.notify(status)
            self.state['notification_accepted'] = True
        except Exception:
            self.state['notification_accepted'] = False
        self.save()
        return {'status': status, 'reason': reason, 'trading_schedules_changed': False}


def handler(event, context):
    import boto3
    from botocore.config import Config
    try:
        validate_event(event, os.environ, datetime.now(timezone.utc))
        clients = {name: boto3.client(name, config=Config(connect_timeout=3, read_timeout=230 if name == 'lambda' else 8,
            retries={'max_attempts': 0 if name == 'lambda' else 1})) for name in
            ('s3', 'ec2', 'ecs', 'dynamodb', 'cloudformation', 'lambda', 'logs', 'secretsmanager')}
        result = Verifier(clients, os.environ).handle(event)
    except Exception:
        result = {'status': 'VERIFICATION_REJECTED_OR_FAILED', 'trading_schedules_changed': False}
    print(json.dumps(result))
    return result
