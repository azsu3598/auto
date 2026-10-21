import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


p = module('paper_pilot_test', ROOT/'infra/paper_pilot.py')
b = module('pilot_bootstrap_test', ROOT/'infra/paper_pilot_bootstrap.py')
builder = module('pilot_template_test', ROOT/'tools/build_paper_pilot_template.py')
UTC = timezone.utc


def plan():
    times = {'GATE': '09:25', 'START_PM': '14:40', 'STOP_PM': '16:10', 'START_AM': '08:55',
        'STOP_AM': '09:25', 'REPORT_PM': '16:15', 'REPORT_AM': '09:40'}
    result = {'entry_date': '2026-10-21', 'exit_date': '2026-10-22', 'starting_cash': '600000', 'paper_only': True, 'events': {}}
    for name, clock in times.items():
        day = result['exit_date'] if name.endswith('_AM') else result['entry_date']
        result['events'][name] = {'dispatch_at': day + 'T' + clock + ':00+09:00'}
    for phase, clock in p.PHASE_TIMES.items():
        day = result['exit_date'] if phase.startswith('EXIT_') else result['entry_date']
        at = datetime.fromisoformat(day + 'T%02d:%02d:00+09:00' % clock)
        result['events'][phase] = {'scheduled_at': at.astimezone(UTC).isoformat(),
            'dispatch_at': (at-timedelta(minutes=2 if phase == 'EXIT_0910' else 3)).astimezone(UTC).isoformat()}
    result.update(morning_result_key='validation/worker/approved.json', morning_test_id='a'*32,
        morning_occurrence='2026-10-21T00:05:00+00:00', morning_task_definition='approved-diagnostic')
    return result


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan()
        self.raw = json.dumps(self.plan).encode()
        self.env = {'PAPER_BUCKET': 'paper', 'PAPER_TABLE': 'stock-automation-paper', 'PILOT_ID': 'f'*32,
            'PLAN_KEY': 'validation/pilot-plan/approved.json', 'PLAN_SHA256': hashlib.sha256(self.raw).hexdigest(),
            'RESULT_PREFIX': 'validation/pilot/approved', 'NAT_INSTANCE_ID': 'nat', 'CLUSTER_ARN': 'cluster',
            'TASK_DEFINITION_ARN': 'pilot-task', 'SUBNET_IDS': 'private', 'SECURITY_GROUP_IDS': 'outbound-only',
            'CONTROL_FUNCTION_ARN': 'controller'}
        self.clients = {name: Mock() for name in ('s3','ec2','ecs','dynamodb','cloudformation','lambda','scheduler','secretsmanager')}
        self.now = p.stamp(self.plan['events']['GATE']['dispatch_at'])
        self.pilot = p.Pilot(self.clients, self.env, clock=lambda: self.now, sleep=Mock())
        self.clients['s3'].get_object.side_effect = lambda **kw: {'Body': io.BytesIO(self.raw)}
        self.pilot.get = Mock(return_value=None)
        self.pilot.notify = Mock()

    def event(self, name):
        self.now = p.stamp(self.plan['events'][name]['dispatch_at'])
        return {'action': name, 'pilot_id': self.env['PILOT_ID']}

    def test_exact_dates_capital_phases_and_times_only(self):
        p.validate_plan(self.plan, self.now)
        mutations = [lambda x: x.update(paper_only=False), lambda x: x.update(starting_cash='600001'),
            lambda x: x['events'].pop('EXIT_0910'), lambda x: x['events'].update(ENTRY_NXT_1955={}),
            lambda x: x['events']['ENTRY_1520'].update(scheduled_at='2026-10-22T06:20:00+00:00'),
            lambda x: x['events']['ENTRY_1520'].update(dispatch_at='2026-10-21T06:00:00+00:00'),
            lambda x: x['events']['GATE'].update(dispatch_at='2026-10-24T09:25:00+09:00')]
        for change in mutations:
            candidate=copy.deepcopy(self.plan);change(candidate)
            with self.assertRaises(ValueError): p.validate_plan(candidate, self.now)

    def test_wrong_plan_hash_or_event_never_launches(self):
        for event in ({'action':'LIVE_ENTRY','pilot_id':self.env['PILOT_ID']}, {'action':'GATE','pilot_id':'other'},
                      {'action':'GATE','pilot_id':self.env['PILOT_ID'],'override':True}):
            with self.assertRaises(ValueError):self.pilot.handle(event)
        self.env['PLAN_SHA256']='0'*64
        with self.assertRaisesRegex(ValueError,'HASH'): self.pilot.handle(self.event('GATE'))
        self.clients['ecs'].run_task.assert_not_called();self.clients['lambda'].invoke.assert_not_called()

    def test_late_delivery_rejected_and_duplicate_never_replayed(self):
        event=self.event('ENTRY_1520');self.now+=timedelta(seconds=61)
        with self.assertRaisesRegex(ValueError,'DISPATCH'):self.pilot.handle(event)
        event=self.event('ENTRY_1520');self.pilot.get.return_value={'status':'RUNNING'}
        self.assertEqual(self.pilot.handle(event)['status'],'ALREADY_ATTEMPTED')
        self.clients['s3'].put_object.assert_not_called();self.clients['ecs'].run_task.assert_not_called()

    def test_pass_missing_blocks_start_and_worker(self):
        self.pilot.require_ready=Mock(side_effect=ValueError('MORNING_PASS_NOT_VERIFIED'))
        for phase in ('START_PM','ENTRY_1520','EXIT_0910'):
            self.assertEqual(self.pilot.handle(self.event(phase))['status'],'BLOCKED_OR_FAILED')
        self.clients['lambda'].invoke.assert_not_called();self.clients['ecs'].run_task.assert_not_called()

    def test_phase_claim_is_atomic_and_failure_cannot_be_retried(self):
        self.pilot.gate=Mock(side_effect=ValueError('EMPTY_BASELINE_CHANGED'))
        self.assertEqual(self.pilot.handle(self.event('GATE'))['status'],'BLOCKED_OR_FAILED')
        calls=self.clients['s3'].put_object.call_args_list
        self.assertEqual(calls[0].kwargs['IfNoneMatch'],'*')
        self.assertNotIn('IfNoneMatch',calls[-1].kwargs)
        self.assertEqual(json.loads(calls[-1].kwargs['Body'])['reason'],'EMPTY_BASELINE_CHANGED')
        self.pilot.get.return_value={'status':'BLOCKED_OR_FAILED'}
        self.assertEqual(self.pilot.handle(self.event('GATE'))['status'],'ALREADY_ATTEMPTED')

    def test_stop_cleans_own_start_without_pass_and_does_not_launch(self):
        self.pilot.get.side_effect=lambda key,optional=False: {'status':'BLOCKED_OR_FAILED'} if key.endswith('/START_PM.json') else None
        self.pilot.controller=Mock(return_value='STOP_REQUESTED');self.pilot.require_ready=Mock(side_effect=RuntimeError())
        self.assertEqual(self.pilot.handle(self.event('STOP_PM'))['status'],'STOP_REQUESTED')
        self.pilot.require_ready.assert_not_called();self.pilot.controller.assert_called_once()
        self.clients['ecs'].run_task.assert_not_called()

    def test_stop_does_not_assume_ownership_without_start(self):
        self.assertEqual(self.pilot.handle(self.event('STOP_AM'))['status'],'NO_OWN_START')
        self.clients['lambda'].invoke.assert_not_called()

    def test_worker_preserves_real_occurrence_private_network_and_pinned_task(self):
        self.pilot.get.return_value={'status':'COMPLETED'}
        self.clients['ecs'].describe_clusters.return_value={'clusters':[{'runningTasksCount':0,'pendingTasksCount':0}]}
        self.clients['ecs'].run_task.return_value={'tasks':[{'taskArn':'own-task'}]}
        self.clients['ecs'].describe_tasks.return_value={'tasks':[{'lastStatus':'STOPPED','containers':[{'exitCode':0}]}]}
        self.clients['dynamodb'].get_item.return_value={'Item':{'status':{'S':'COMPLETED'}}}
        self.assertEqual(self.pilot.run('ENTRY_1520',self.plan['events']['ENTRY_1520'],self.plan),'COMPLETED')
        request=self.clients['ecs'].run_task.call_args.kwargs
        env={v['name']:v['value'] for v in request['overrides']['containerOverrides'][0]['environment']}
        self.assertEqual(env['SCHEDULED_AT'],self.plan['events']['ENTRY_1520']['scheduled_at'])
        self.assertEqual(env['DISPATCHED_AT'],self.plan['events']['ENTRY_1520']['dispatch_at'])
        self.assertEqual(request['networkConfiguration']['awsvpcConfiguration']['assignPublicIp'],'DISABLED')
        self.assertEqual(request['taskDefinition'],'pilot-task');self.assertNotIn('command',request['overrides']['containerOverrides'][0])

    def test_missing_scan_or_shortlist_and_existing_task_block_entry(self):
        self.clients['ecs'].describe_clusters.return_value={'clusters':[{'runningTasksCount':0,'pendingTasksCount':0}]}
        with self.assertRaisesRegex(ValueError,'PREREQUISITE'):self.pilot.run('ENTRY_1520',self.plan['events']['ENTRY_1520'],self.plan)
        self.clients['ecs'].describe_clusters.return_value={'clusters':[{'runningTasksCount':1,'pendingTasksCount':0}]}
        with self.assertRaisesRegex(ValueError,'EXISTING_TASK'):self.pilot.run('ENTRY_1520',self.plan['events']['ENTRY_1520'],self.plan)
        self.clients['ecs'].run_task.assert_not_called()

    def test_no_exit_zero_shortcut_without_real_completed_lease(self):
        self.pilot.get.return_value={'status':'COMPLETED'}
        self.clients['ecs'].describe_clusters.return_value={'clusters':[{'runningTasksCount':0,'pendingTasksCount':0}]}
        self.clients['ecs'].run_task.return_value={'tasks':[{'taskArn':'own-task'}]}
        self.clients['ecs'].describe_tasks.return_value={'tasks':[{'lastStatus':'STOPPED','containers':[{'exitCode':0}]}]}
        self.clients['dynamodb'].get_item.return_value={'Item':{'status':{'S':'RECONCILE_REQUIRED'}}}
        with self.assertRaisesRegex(ValueError,'REAL_ATTEMPT'):self.pilot.run('EXIT_0910',self.plan['events']['EXIT_0910'],self.plan)
        self.clients['ecs'].stop_task.assert_called_once()

    def proof(self):
        at=p.stamp(self.plan['morning_occurrence'])
        key='CONTROL#RUN#EXIT_0905#'+at.isoformat()
        proof={'status':'PASSED','normal_time_worker_verified':True,'cleanup_complete':True,
            'test_id':self.plan['morning_test_id'],'occurrence':self.plan['morning_occurrence'],
            'task_definition':self.plan['morning_task_definition'],'worker_attempt_key':key,
            'checked_at':(at+timedelta(minutes=2)).isoformat(),'baseline_digest':p.digest([])}
        self.pilot.get.return_value=proof
        self.clients['dynamodb'].get_item.return_value={'Item':{'status':{'S':'COMPLETED'},'owner':{'S':'a'*32},
            'started_at':{'S':at.isoformat()},'finished_at':{'S':(at+timedelta(seconds=5)).isoformat()}}}
        return proof,key

    def test_morning_pass_requires_exact_test_task_cleanup_and_completed_attempt(self):
        proof,key=self.proof();self.assertEqual(self.pilot.proof(self.plan),(proof,key))
        for field,value in (('status','FAILED'),('cleanup_complete',False),('normal_time_worker_verified',False),
                ('task_definition','other'),('test_id','other'),('worker_attempt_key','other'),
                ('checked_at','2026-10-21T20:00:00+00:00')):
            old=proof[field];proof[field]=value
            with self.assertRaises(ValueError):self.pilot.proof(self.plan)
            proof[field]=old
        self.clients['dynamodb'].get_item.return_value['Item']['status']={'S':'RUNNING'}
        with self.assertRaises(ValueError):self.pilot.proof(self.plan)

    def test_gate_requires_unchanged_empty_ledger_and_stopped_network(self):
        proof,key=self.proof();self.pilot.configuration=Mock();self.pilot.rows=Mock(return_value=[{'pk':{'S':'WALLET#CLOSING_BET#KRX_1520'}}])
        with self.assertRaisesRegex(ValueError,'BASELINE'):self.pilot.gate(self.plan)
        self.pilot.rows.return_value=[]
        self.clients['ec2'].describe_instances.return_value={'Reservations':[{'Instances':[{'State':{'Name':'running'}}]}]}
        self.clients['ecs'].describe_clusters.return_value={'clusters':[{'runningTasksCount':0,'pendingTasksCount':0}]}
        with self.assertRaisesRegex(ValueError,'CLEANUP'):self.pilot.gate(self.plan)
        self.clients['ec2'].describe_instances.return_value['Reservations'][0]['Instances'][0]['State']['Name']='stopped'
        self.assertEqual(self.pilot.gate(self.plan),'READY')
        self.assertEqual(self.clients['s3'].put_object.call_args.kwargs['IfNoneMatch'],'*')

    def test_configuration_rejects_regular_schedule_drift(self):
        candidate={'stack_parameters':{},'regular_schedules':[{'name':'regular','arn':'approved'}]}
        self.clients['scheduler'].get_schedule.return_value={'Arn':'approved','State':'ENABLED'}
        with self.assertRaisesRegex(ValueError,'SCHEDULE'):self.pilot.configuration(candidate)
        self.clients['ecs'].run_task.assert_not_called()

    def test_reports_never_infer_purchase_and_flag_remaining_position(self):
        self.pilot.rows=Mock(return_value=[{'pk':{'S':'OPEN#CLOSING_BET#KRX_1520'}}])
        self.pilot.get.return_value={'status':'COMPLETED'}
        self.assertEqual(self.pilot.report('REPORT_AM'),'RECONCILIATION_REQUIRED')
        message=self.pilot.notify.call_args.args[0]
        self.assertIn('open_positions=1',message);self.assertNotIn('BUY',message)

    def test_bootstrap_limits_phase_mode_day_and_dispatch(self):
        item=self.plan['events']['ENTRY_1520']
        env={'KIWOOM_MODE':'demo','LIVE_ORDER_ENABLED':'0','RUN_PHASE':'ENTRY_1520',
            'SCHEDULED_AT':item['scheduled_at'],'DISPATCHED_AT':item['dispatch_at'],
            'PILOT_ENTRY_DATE':'2026-10-21','PILOT_EXIT_DATE':'2026-10-22'}
        occurrence=p.stamp(item['scheduled_at'])
        b.wait_for_occurrence(env,clock=lambda:occurrence,sleep=Mock(),monotonic=lambda:0)
        for key,value in (('KIWOOM_MODE','live'),('LIVE_ORDER_ENABLED','1'),('RUN_PHASE','ENTRY_NXT_1955'),
                ('PILOT_ENTRY_DATE','2026-10-22'),('DISPATCHED_AT',occurrence.isoformat())):
            with self.assertRaises(ValueError):b.wait_for_occurrence({**env,key:value},clock=lambda:occurrence,sleep=Mock(),monotonic=lambda:0)

    def test_bootstrap_wait_uses_real_clock_then_original_bounded_worker(self):
        source=(ROOT/'infra/paper_pilot_bootstrap.py').read_text(encoding='utf-8')
        self.assertIn('return run_bounded()',source);self.assertNotIn('patch(',source)
        item=self.plan['events']['ENTRY_1520'];at=p.stamp(item['scheduled_at']);ticks=[at-timedelta(seconds=1)]
        env={'KIWOOM_MODE':'demo','LIVE_ORDER_ENABLED':'0','RUN_PHASE':'ENTRY_1520',
            'SCHEDULED_AT':item['scheduled_at'],'DISPATCHED_AT':item['dispatch_at'],
            'PILOT_ENTRY_DATE':'2026-10-21','PILOT_EXIT_DATE':'2026-10-22'}
        sleep=Mock(side_effect=lambda _:ticks.append(at))
        b.wait_for_occurrence(env,clock=lambda:ticks[-1],sleep=sleep,monotonic=lambda:0)
        sleep.assert_called_once()

    def test_template_is_disabled_one_off_and_cannot_mutate_regular_schedules_or_ledger(self):
        template=builder.build()
        schedules=[r['Properties'] for r in template['Resources'].values() if r['Type']=='AWS::Scheduler::Schedule']
        self.assertEqual(len(schedules),15)
        self.assertEqual(template['Parameters']['PilotState']['Default'],'DISABLED')
        for schedule in schedules:
            self.assertEqual(schedule['State'],{'Ref':'PilotState'})
            self.assertTrue(schedule['ScheduleExpression']['Fn::Sub'].startswith('at('))
            self.assertEqual(schedule['Target']['RetryPolicy']['MaximumRetryAttempts'],0)
        policy=template['Resources']['Boundary']['Properties']['PolicyDocument']
        text=json.dumps(policy)
        for action in ('scheduler:UpdateSchedule','scheduler:CreateSchedule','dynamodb:PutItem','dynamodb:UpdateItem',
                's3:DeleteObject','ec2:StartInstances','secretsmanager:*'):
            self.assertNotIn(action,text)
        run=next(s for s in policy['Statement'] if 'ecs:RunTask' in s['Action'])
        self.assertEqual(run['Resource'],{'Ref':'PilotTask'})
        self.assertLess(len(json.dumps(policy,separators=(',',':'))),6144)
        self.assertFalse(any(r['Type'] in ('AWS::EC2::Instance','AWS::EC2::EIP','AWS::ECS::Service') for r in template['Resources'].values()))


if __name__ == '__main__':
    unittest.main()
