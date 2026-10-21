import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]


class ControlInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t=json.loads((ROOT/'infra/paper-control.yaml').read_text(encoding='utf-8'))

    def test_all_network_schedules_are_frozen_and_zero_retry(self):
        self.assertEqual(self.t['Parameters']['ScheduleState']['AllowedValues'],['DISABLED'])
        schedules=[x['Properties'] for x in self.t['Resources'].values() if x['Type']=='AWS::Scheduler::Schedule']
        self.assertEqual(len(schedules),6)
        for schedule in schedules:
            self.assertEqual(schedule['State'],{'Ref':'ScheduleState'})
            self.assertEqual(schedule['Target']['RetryPolicy']['MaximumRetryAttempts'],0)
            self.assertEqual(json.loads(schedule['Target']['Input'])['scheduled_at'],'<aws.scheduler.scheduled-time>')

    def test_controller_cannot_start_tasks_or_access_broker_or_wallets(self):
        doc=self.t['Resources']['ControlBoundary']['Properties']['PolicyDocument']
        actions={a for s in doc['Statement'] for a in s['Action']}
        self.assertNotIn('ecs:RunTask',actions);self.assertNotIn('iam:PassRole',actions)
        self.assertNotIn('dynamodb:UpdateItem',actions);self.assertNotIn('s3:DeleteObject',actions)
        secret=next(x for x in doc['Statement'] if 'secretsmanager:GetSecretValue' in x['Action'])
        self.assertEqual(secret['Resource'],{'Ref':'TelegramSecretArn'})
        ddb=next(x for x in doc['Statement'] if 'dynamodb:PutItem' in x['Action'])
        self.assertEqual(ddb['Condition']['ForAllValues:StringLike']['dynamodb:LeadingKeys'],['CONTROL#NETWORK#*','CONTROL#ALERT#*'])

    def test_stop_permission_is_limited_to_one_nat_and_one_paper_cluster(self):
        doc=self.t['Resources']['ControlBoundary']['Properties']['PolicyDocument']
        nat=next(x for x in doc['Statement'] if 'ec2:StopInstances' in x['Action'])
        self.assertTrue(nat['Resource']['Fn::Sub'].endswith('instance/${NatInstanceId}'))
        task=next(x for x in doc['Statement'] if 'ecs:StopTask' in x['Action'])
        self.assertTrue(task['Resource']['Fn::Sub'].endswith('task/stock-automation-paper/*'))
        self.assertEqual(task['Condition']['ArnEquals']['ecs:cluster'],{'Ref':'ClusterArn'})

    def test_operator_has_only_control_inspection_and_invocation(self):
        doc=self.t['Resources']['OperatorControlPolicy']['Properties']['PolicyDocument']
        actions={a for s in doc['Statement'] for a in s['Action']}
        self.assertNotIn('secretsmanager:GetSecretValue',actions)
        self.assertFalse(any(x.startswith('iam:') for x in actions))
        self.assertFalse(any(x.startswith('ec2:') for x in actions))

    def test_lambda_is_bounded_without_provisioned_or_always_on_compute(self):
        func=self.t['Resources']['ControlFunction']['Properties']
        self.assertEqual(func['Timeout'],600);self.assertEqual(func['MemorySize'],128)
        self.assertEqual(func['ReservedConcurrentExecutions'],2)
        self.assertNotIn('VpcConfig',func)
        self.assertEqual(self.t['Resources']['ControlAsyncPolicy']['Properties']['MaximumRetryAttempts'],0)

    def test_failure_rule_only_accepts_stopped_tasks_in_own_cluster(self):
        p=self.t['Resources']['FailureRule']['Properties']['EventPattern']
        self.assertEqual(p['source'],['aws.ecs'])
        self.assertEqual(p['detail']['lastStatus'],['STOPPED'])
        self.assertEqual(p['detail']['clusterArn'],[{'Ref':'ClusterArn'}])
        permission=self.t['Resources']['FailureInvokePermission']['Properties']
        self.assertEqual(permission['SourceAccount'],{'Ref':'AWS::AccountId'})

    def test_package_is_deterministic_and_contains_only_reviewed_python(self):
        spec=importlib.util.spec_from_file_location('package_control',ROOT/'tools/package_paper_control.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            a=module.package(Path(tmp)/'a.zip');b=module.package(Path(tmp)/'b.zip')
            self.assertEqual(a,b)
            with zipfile.ZipFile(Path(tmp)/'a.zip') as archive:
                self.assertEqual(set(archive.namelist()),{'paper_control.py','stock_automation/__init__.py','stock_automation/calendar.py'})
            with self.assertRaises(ValueError):module.package(Path(tmp)/'a.zip')


if __name__=='__main__':unittest.main()
