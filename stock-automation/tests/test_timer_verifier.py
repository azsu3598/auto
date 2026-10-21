import importlib.util
import io
import json
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
v = module('timer_verifier', ROOT/'infra/paper_timer_verifier.py')
builder = module('timer_template', ROOT/'tools/build_timer_verification_template.py')
BOOT = datetime(2026, 10, 19, 11, 0, tzinfo=timezone.utc)


class TimerVerifierTests(unittest.TestCase):
    def setUp(self):
        self.env = {'TEST_ID': 'test', 'NAT_INSTANCE_ID': 'nat', 'PAPER_BUCKET': 'paper',
            'RESULT_KEY': 'validation/timer/test.json', 'CHECK_AT': (BOOT+timedelta(minutes=130)).isoformat()}
        self.marker = {'test_id': 'test', 'instance_id': 'nat', 'status': 'ARMED',
            'launch_time': BOOT.isoformat(), 'boot_time': BOOT.isoformat(),
            'armed_at': (BOOT+timedelta(minutes=1)).isoformat(), 'timer_seconds': 7200, 'timer_active': True}
        self.vm = {'LaunchTime': BOOT, 'State': {'Name': 'stopped'},
            'StateReason': {'Code': 'Client.InstanceInitiatedShutdown'},
            'Tags': [{'Key': 'Project', 'Value': 'paper-fixed-egress'}, {'Key': 'Name', 'Value': 'stock-automation-paper-nat'}]}
        self.event = {'source': 'aws.ec2', 'detail-type': 'EC2 Instance State-change Notification',
            'time': (BOOT+timedelta(minutes=121)).isoformat(), 'detail': {'instance-id': 'nat', 'state': 'stopped'}}
        self.now = BOOT+timedelta(minutes=122)

    def test_real_os_stop_in_original_two_hour_window_passes(self):
        self.assertEqual(v.evaluate(self.event, self.marker, self.vm, self.env, self.now), 'PASSED')

    def test_api_stop_or_early_os_stop_never_passes(self):
        for minute, code in ((119, 'Client.InstanceInitiatedShutdown'), (121, 'Client.UserInitiatedShutdown')):
            with self.subTest(minute=minute, code=code):
                self.event['time'] = (BOOT+timedelta(minutes=minute)).isoformat()
                self.vm['StateReason']['Code'] = code
                self.assertNotEqual(v.evaluate(self.event, self.marker, self.vm, self.env, self.now), 'PASSED')

    def test_wrong_host_or_boot_is_rejected_without_stopping_it(self):
        self.vm['LaunchTime'] = BOOT+timedelta(minutes=1)
        with self.assertRaisesRegex(ValueError, 'BOOT_CHANGED'):
            v.evaluate(self.event, self.marker, self.vm, self.env, self.now)

    def test_timeout_cannot_infer_success_from_a_stopped_host(self):
        self.assertEqual(v.evaluate({'action': 'TIMEOUT'}, self.marker, self.vm, self.env,
            BOOT+timedelta(minutes=131)), 'MISSING_STOP_EVENT')

    def test_missing_timer_configuration_or_unarmed_marker_is_rejected(self):
        for change in ({'timer_seconds': 300}, {'timer_active': False}, {'status': 'PREPARED'}):
            with self.assertRaises(ValueError):
                v.evaluate(self.event, {**self.marker, **change}, self.vm, self.env, self.now)

    def test_already_final_result_does_not_send_a_second_notification(self):
        self.marker['status'] = 'PASSED'
        clients = {n: Mock() for n in ('ec2', 's3', 'secretsmanager')}
        clients['s3'].get_object.return_value = {'Body': io.BytesIO(json.dumps(self.marker).encode())}
        clients['ec2'].describe_instances.return_value = {'Reservations': [{'Instances': [self.vm]}]}
        with patch.object(v, 'notify') as notify:
            self.assertEqual(v.handle(self.event, clients=clients, env=self.env, now=self.now)['status'], 'ALREADY_FINAL')
        notify.assert_not_called(); clients['ec2'].stop_instances.assert_not_called()

    def test_failed_trial_stops_host_before_storage_or_notification_failure(self):
        clients = {n: Mock() for n in ('ec2', 's3', 'secretsmanager')}; events = []
        clients['s3'].get_object.return_value = {'Body': io.BytesIO(json.dumps(self.marker).encode())}
        self.vm['State']['Name'] = 'running'
        clients['ec2'].describe_instances.return_value = {'Reservations': [{'Instances': [self.vm]}]}
        clients['ec2'].stop_instances.side_effect = lambda **kw: events.append('STOP')
        def fail(**kw): events.append('WRITE'); raise RuntimeError('storage failed')
        clients['s3'].put_object.side_effect = fail
        with self.assertRaises(RuntimeError):
            v.handle({'action': 'TIMEOUT'}, clients=clients, env=self.env, now=BOOT+timedelta(minutes=131))
        self.assertEqual(events, ['STOP', 'WRITE'])

    def test_observer_has_no_start_order_task_or_schedule_edit_permissions(self):
        t = builder.build(); statements = t['Resources']['Boundary']['Properties']['PolicyDocument']['Statement']
        actions = {a for s in statements for a in s['Action']}
        self.assertFalse(actions.intersection({'ec2:StartInstances', 'ecs:RunTask', 'scheduler:UpdateSchedule',
            'iam:PassRole', 'dynamodb:PutItem'}))
        storage = next(s for s in statements if 's3:PutObject' in s['Action'])
        self.assertTrue(storage['Resource']['Fn::Sub'].endswith('/validation/timer/${TestId}.json'))

    def test_inline_source_matches_and_all_schedules_are_one_off_checks(self):
        t = builder.build()
        self.assertEqual(t, json.loads((ROOT/'infra/paper-timer-verification.yaml').read_text(encoding='utf-8')))
        self.assertEqual(t['Resources']['Verifier']['Properties']['Code']['ZipFile'],
            (ROOT/'infra/paper_timer_verifier.py').read_text(encoding='utf-8'))
        schedules = [r['Properties'] for r in t['Resources'].values() if r['Type'] == 'AWS::Scheduler::Schedule']
        self.assertEqual(len(schedules), 2)
        for schedule in schedules:
            self.assertTrue(schedule['ScheduleExpression']['Fn::Sub'].startswith('at('))
            self.assertEqual(schedule['FlexibleTimeWindow'], {'Mode': 'OFF'})
        self.assertEqual(t['Resources']['StopPermission']['Properties']['SourceAccount'], {'Ref': 'AWS::AccountId'})

    def test_operator_can_arm_only_the_one_test_object(self):
        t = builder.build()
        statements = t['Resources']['OperatorReviewPolicy']['Properties']['PolicyDocument']['Statement']
        writes = [s for s in statements if 's3:PutObject' in s['Action']]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]['Resource']['Fn::Sub'],
            'arn:${AWS::Partition}:s3:::${ArtifactBucketName}/validation/timer/${TestId}.json')


if __name__ == '__main__': unittest.main()
