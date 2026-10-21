"""Observe one existing NAT timer trial. Never start a host or a trading task."""
import json
import os
from datetime import datetime, timezone
import urllib.request


def stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return result


def evaluate(event, marker, vm, env, now):
    """An API stop, early stop, different boot or missing event is never a pass."""
    if marker.get('test_id') != env['TEST_ID'] or marker.get('instance_id') != env['NAT_INSTANCE_ID']:
        raise ValueError('WRONG_TEST_MARKER')
    if marker.get('status') in ('PASSED', 'FAILED'):
        return 'ALREADY_FINAL'
    if marker.get('status') != 'ARMED':
        raise ValueError('TEST_NOT_ARMED')
    if vm['LaunchTime'] != stamp(marker['launch_time']):
        raise ValueError('BOOT_CHANGED')
    if marker.get('timer_seconds') != 7200 or marker.get('timer_active') is not True:
        raise ValueError('TIMER_PROOF_MISSING')
    if event.get('source') != 'aws.ec2':
        # The independent timeout only records failure; absence of a STOPPED event
        # is not retrospective evidence that the two-hour timer worked.
        if event.get('action') != 'TIMEOUT' or now < stamp(env['CHECK_AT']):
            raise ValueError('UNSUPPORTED_OR_EARLY_EVENT')
        return 'MISSING_STOP_EVENT'
    if (event.get('detail-type') != 'EC2 Instance State-change Notification'
            or event.get('detail', {}).get('instance-id') != env['NAT_INSTANCE_ID']
            or event.get('detail', {}).get('state') != 'stopped'):
        raise ValueError('UNRELATED_EVENT')
    event_time = stamp(event['time'])
    elapsed = (event_time - stamp(marker['boot_time'])).total_seconds()
    if not stamp(marker['armed_at']) <= event_time <= now:
        raise ValueError('EVENT_OUTSIDE_TEST')
    if not 7200 <= elapsed <= 7500:
        return 'STOP_OUTSIDE_120_MINUTE_WINDOW'
    if vm['State']['Name'] != 'stopped':
        return 'HOST_NOT_STOPPED'
    if vm.get('StateReason', {}).get('Code') != 'Client.InstanceInitiatedShutdown':
        return 'STOP_WAS_NOT_FROM_OS'
    return 'PASSED'


def notify(secrets, env, code):
    raw = secrets.get_secret_value(SecretId=env['TELEGRAM_SECRET_ARN'])
    credentials = json.loads(raw['SecretString'])
    data = json.dumps({'chat_id': credentials['chat_id'],
        'text': '[SABU 모의환경] 120분 자동정지 시험: ' + code + '. 매매 예약은 꺼져 있습니다.'}).encode()
    request = urllib.request.Request('https://api.telegram.org/bot' + credentials['bot_token'] + '/sendMessage',
        data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=6) as response:
        if json.loads(response.read()).get('ok') is not True:
            raise ValueError('NOTIFICATION_REJECTED')


def handle(event, *, clients, env, now):
    ec2, s3 = clients['ec2'], clients['s3']
    marker = json.loads(s3.get_object(Bucket=env['PAPER_BUCKET'], Key=env['RESULT_KEY'])['Body'].read())
    vm = ec2.describe_instances(InstanceIds=[env['NAT_INSTANCE_ID']])['Reservations'][0]['Instances'][0]
    tags = {t['Key']: t['Value'] for t in vm.get('Tags', [])}
    if tags.get('Project') != 'paper-fixed-egress' or tags.get('Name') != 'stock-automation-paper-nat':
        raise ValueError('HOST_IDENTITY_CHANGED')
    reason = evaluate(event, marker, vm, env, now)
    if reason == 'ALREADY_FINAL':
        return {'status': 'ALREADY_FINAL'}
    status = 'PASSED' if reason == 'PASSED' else 'FAILED'
    # Cleanup precedes storage and notification: neither can leave a failed trial
    # running. A different boot was rejected above and is never stopped here.
    if status == 'FAILED' and vm['State']['Name'] not in ('stopped', 'stopping'):
        ec2.stop_instances(InstanceIds=[env['NAT_INSTANCE_ID']])
    marker.update(status=status, reason=reason, checked_at=now.isoformat(),
        event_time=event.get('time'), state_reason=vm.get('StateReason', {}).get('Code'))
    s3.put_object(Bucket=env['PAPER_BUCKET'], Key=env['RESULT_KEY'],
        Body=json.dumps(marker).encode(), ContentType='application/json')
    try:
        notify(clients['secretsmanager'], env, status)
    except Exception:
        print(json.dumps({'status': 'NOTIFICATION_FAILED', 'paper_only': True}))
    return {'status': status, 'reason': reason, 'paper_only': True}


def handler(event, context):
    import boto3
    from botocore.config import Config
    clients = {name: boto3.client(name, config=Config(connect_timeout=3, read_timeout=8,
        retries={'max_attempts': 1})) for name in ('ec2', 's3', 'secretsmanager')}
    try:
        result = handle(event, clients=clients, env=os.environ, now=datetime.now(timezone.utc))
    except Exception:
        print(json.dumps({'status': 'TIMER_CHECK_REJECTED_OR_FAILED', 'paper_only': True}))
        raise ValueError('TIMER_CHECK_REJECTED_OR_FAILED') from None
    print(json.dumps(result))
    return result
