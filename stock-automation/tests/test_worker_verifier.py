import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


v = module('worker_verifier', ROOT/'infra/paper_worker_verifier.py')
b = module('worker_bootstrap', ROOT/'infra/paper_worker_bootstrap.py')
builder = module('worker_verifier_template', ROOT/'tools/build_worker_verification_template.py')
RUN = datetime(2026, 10, 21, 0, 5, tzinfo=timezone.utc)
DISPATCH = RUN - timedelta(minutes=3)
BOOT = RUN - timedelta(minutes=9)


class WorkerVerifierTests(unittest.TestCase):
    def setUp(self):
        self.env = {'TEST_ID': 'a'*32, 'RUN_AT': RUN.isoformat(), 'START_AT': (RUN-timedelta(minutes=10)).isoformat(),
            'WATCH_AT': (RUN+timedelta(minutes=11)).isoformat(), 'PAPER_BUCKET': 'paper', 'PAPER_TABLE': 'stock-automation-paper',
            'RESULT_KEY': 'validation/worker/test.json', 'TASK_DEFINITION_ARN': 'diagnostic', 'PRODUCTION_TASK_DEFINITION_ARN': 'production',
            'NAT_INSTANCE_ID': 'nat', 'CLUSTER_ARN': 'cluster', 'CONTROL_FUNCTION_ARN': 'controller', 'EXPECTED_IMAGE_URI': 'reviewed-image',
            'APP_LOG_GROUP': 'paper-log', 'SUBNET_IDS': 'private', 'SECURITY_GROUP_IDS': 'outbound-only',
            'BOOTSTRAP_SHA256': hashlib.sha256((ROOT/'infra/paper_worker_bootstrap.py').read_text(encoding='utf-8').encode()).hexdigest()}
        self.marker = {'status': 'ARMED', 'test_id': self.env['TEST_ID'], 'occurrence': self.env['RUN_AT'],
            'task_definition': 'diagnostic', 'baseline_digest': v.digest([])}
        self.clients = {name: Mock() for name in ('s3','ec2','ecs','dynamodb','cloudformation','lambda','logs','secretsmanager')}
        self.clients['s3'].get_object.return_value = {'Body': io.BytesIO(json.dumps(self.marker).encode())}
        self.worker = v.Verifier(self.clients, self.env, clock=lambda: DISPATCH, sleep=Mock())
        self.event = {'action': 'RUN', 'test_id': self.env['TEST_ID']}

    def test_exact_dispatch_and_watch_windows_only(self):
        self.assertEqual(v.validate_event(self.event,self.env,DISPATCH),RUN)
        for event, now in ((self.event,DISPATCH-timedelta(seconds=1)), (self.event,DISPATCH+timedelta(seconds=61)),
            ({'action':'ENTRY_1520','test_id':self.env['TEST_ID']},DISPATCH), ({**self.event,'test_id':'other'},DISPATCH),
            ({**self.event,'RUN_PHASE':'ENTRY_1520'},DISPATCH)):
            with self.assertRaises(ValueError): v.validate_event(event,self.env,now)
        self.assertEqual(v.validate_event({'action':'WATCH','test_id':self.env['TEST_ID']},self.env,RUN+timedelta(minutes=11)),RUN)

    def test_weekend_or_other_phase_time_is_rejected(self):
        for value in ('2026-10-24T00:05:00+00:00','2026-10-21T06:20:00+00:00'):
            with self.assertRaises(ValueError): v.validate_event(self.event,{**self.env,'RUN_AT':value},DISPATCH)

    def test_already_final_never_reruns_or_notifies(self):
        self.marker['status']='PASSED'
        self.clients['s3'].get_object.return_value={'Body':io.BytesIO(json.dumps(self.marker).encode())}
        self.worker.notify=Mock();self.worker.cleanup=Mock()
        self.assertEqual(self.worker.handle(self.event),{'status':'ALREADY_FINAL'})
        self.clients['ecs'].run_task.assert_not_called();self.worker.notify.assert_not_called();self.worker.cleanup.assert_not_called()

    def test_running_marker_is_not_automatically_reacquired(self):
        self.marker['status']='RUNNING'
        self.clients['s3'].get_object.return_value={'Body':io.BytesIO(json.dumps(self.marker).encode())}
        self.worker.cleanup=Mock();self.worker.notify=Mock()
        result=self.worker.handle(self.event)
        self.assertEqual(result['status'],'FAILED')
        self.clients['ecs'].run_task.assert_not_called();self.worker.cleanup.assert_called_once()

    def test_preflight_failure_cleans_before_failed_result_write(self):
        calls=[]
        self.worker.preflight=Mock(side_effect=ValueError('LEDGER_CHANGED_BEFORE_TEST'))
        self.worker.cleanup=Mock(side_effect=lambda:calls.append('CLEANUP'))
        self.worker.notify=Mock()
        def write(**kwargs):
            state=json.loads(kwargs['Body']);calls.append(state['status'])
            if state['status']=='FAILED':raise RuntimeError('storage unavailable')
        self.clients['s3'].put_object.side_effect=write
        with self.assertRaises(RuntimeError):self.worker.handle(self.event)
        self.assertEqual(calls,['RUNNING','CLEANUP','FAILED'])
        self.clients['ecs'].run_task.assert_not_called()

    def test_cleanup_failure_is_never_reported_as_passed(self):
        self.worker.preflight=Mock(return_value='stock-automation')
        self.clients['ecs'].run_task.return_value={'tasks':[{'taskArn':'task'}]}
        self.clients['ecs'].describe_tasks.return_value={'tasks':[{'taskArn':'task','lastStatus':'STOPPED','containers':[{'exitCode':0}]}]}
        self.worker.verify_task=Mock();self.worker.cleanup=Mock(side_effect=ValueError('NAT_STOP_NOT_CONFIRMED'));self.worker.notify=Mock()
        result=self.worker.handle(self.event)
        self.assertEqual(result['status'],'FAILED')
        self.assertEqual(result['reason'],'CLEANUP_REQUIRES_RECONCILIATION')

    def test_launch_preserves_original_occurrence_and_private_network(self):
        self.worker.preflight=Mock(return_value='stock-automation')
        self.clients['ecs'].run_task.return_value={'tasks':[{'taskArn':'task'}]}
        self.clients['ecs'].describe_tasks.return_value={'tasks':[{'taskArn':'task','lastStatus':'STOPPED','containers':[{'exitCode':0}]}]}
        self.worker.verify_task=Mock();self.worker.cleanup=Mock();self.worker.notify=Mock()
        self.assertEqual(self.worker.handle(self.event)['status'],'PASSED')
        request=self.clients['ecs'].run_task.call_args.kwargs
        env={x['name']:x['value'] for x in request['overrides']['containerOverrides'][0]['environment']}
        self.assertEqual(env,{'RUN_PHASE':'EXIT_0905','SCHEDULED_AT':RUN.isoformat()})
        self.assertNotIn('command',request['overrides']['containerOverrides'][0])
        self.assertEqual(request['networkConfiguration']['awsvpcConfiguration']['assignPublicIp'],'DISABLED')
        self.assertEqual(request['taskDefinition'],'diagnostic')

    def real_proof(self):
        self.worker.state=dict(self.marker)
        self.clients['logs'].get_log_events.return_value={'events':[{'message':json.dumps({'status':'EXIT_REVIEW_COMPLETE','results':[]})}]}
        self.clients['dynamodb'].get_item.return_value={'Item':{'status':{'S':'COMPLETED'},'owner':{'S':'f'*32},
            'started_at':{'S':(RUN+timedelta(seconds=1)).isoformat()},'finished_at':{'S':(RUN+timedelta(seconds=5)).isoformat()}}}
        self.worker.rows=Mock(return_value=[])
        return {'taskArn':'task/id','lastStatus':'STOPPED','containers':[{'exitCode':0}]}

    def test_exit_zero_and_completed_real_attempt_are_both_required(self):
        task=self.real_proof();self.worker.verify_task(task,RUN,'stock-automation')
        self.assertTrue(self.worker.state['normal_time_worker_verified'])
        self.clients['dynamodb'].get_item.return_value['Item']['status']={'S':'RUNNING'}
        with self.assertRaisesRegex(ValueError,'ATTEMPT'):self.worker.verify_task(task,RUN,'stock-automation')

    def test_business_mutation_missing_log_or_nonzero_exit_fails(self):
        task=self.real_proof();self.worker.rows.return_value=[{'pk':{'S':'WALLET#CLOSING_BET#KRX_1520'}}]
        with self.assertRaisesRegex(ValueError,'LEDGER'):self.worker.verify_task(task,RUN,'stock-automation')
        self.worker.rows.return_value=[]
        self.clients['logs'].get_log_events.return_value={'events':[{'message':'{"status":"SKIPPED"}'}]}
        with self.assertRaises(ValueError):self.worker.verify_task(task,RUN,'stock-automation')
        with self.assertRaises(ValueError):self.worker.verify_task({**task,'containers':[{'exitCode':2}]},RUN,'stock-automation')

    def test_cleanup_refuses_different_boot(self):
        self.worker.state={**self.marker,'launch_time':BOOT.isoformat()}
        self.worker.tasks=Mock(return_value=[])
        self.worker.instance=Mock(return_value={'LaunchTime':BOOT+timedelta(minutes=1),'State':{'Name':'running'}})
        with self.assertRaisesRegex(ValueError,'BOOT_CHANGED'):self.worker.cleanup()
        self.clients['lambda'].invoke.assert_not_called();self.clients['ec2'].stop_instances.assert_not_called()

    def test_denied_task_inventory_still_stops_owned_boot_and_stays_failed(self):
        self.worker.state={**self.marker,'launch_time':BOOT.isoformat()}
        denied=ClientError({'Error':{'Code':'AccessDeniedException','Message':'private ARN must not leak'}},'ListTasks')
        self.worker.tasks=Mock(side_effect=denied)
        running={'LaunchTime':BOOT,'State':{'Name':'running'}}
        stopped={'LaunchTime':BOOT,'State':{'Name':'stopped'}}
        self.worker.instance=Mock(side_effect=[running,running,stopped])
        self.worker.controller=Mock()
        with self.assertRaisesRegex(ValueError,'TASK_INVENTORY_REQUIRES_RECONCILIATION'):
            self.worker.cleanup()
        self.worker.controller.assert_called_once()
        self.clients['ec2'].stop_instances.assert_called_once_with(InstanceIds=['nat'])
        self.assertEqual(self.worker.state['cleanup_inventory_error'],{'code':'AccessDeniedException','operation':'ListTasks'})
        self.assertNotIn('private ARN',json.dumps(self.worker.state))

    def test_denied_inventory_never_stops_an_unowned_or_changed_boot(self):
        self.worker.state={**self.marker,'launch_time':BOOT.isoformat()}
        self.worker.tasks=Mock(side_effect=RuntimeError('inventory unavailable'))
        self.worker.instance=Mock(return_value={'LaunchTime':BOOT+timedelta(seconds=1),'State':{'Name':'running'}})
        with self.assertRaisesRegex(ValueError,'BOOT_CHANGED'):self.worker.cleanup()
        self.clients['ec2'].stop_instances.assert_not_called();self.clients['lambda'].invoke.assert_not_called()

    def test_stopped_host_does_not_prove_active_task_cleanup(self):
        self.worker.state={**self.marker,'launch_time':BOOT.isoformat()}
        self.worker.tasks=Mock(return_value=[{'taskArn':'own','startedBy':self.env['TEST_ID'],'lastStatus':'RUNNING'}])
        self.worker.instance=Mock(return_value={'LaunchTime':BOOT,'State':{'Name':'stopped'}})
        with self.assertRaisesRegex(ValueError,'TASK_CLEANUP_NOT_CONFIRMED'):self.worker.cleanup()
        self.clients['ecs'].stop_task.assert_called_once()

    def test_cleanup_failure_preserves_original_worker_reason_and_safe_aws_code(self):
        self.worker.preflight=Mock(side_effect=ValueError('CURRENT_BOOT_NOT_READY'))
        self.worker.cleanup=Mock(side_effect=ClientError({'Error':{'Code':'AccessDeniedException','Message':'private ARN'}},'ListTasks'))
        self.worker.notify=Mock()
        self.assertEqual(self.worker.handle(self.event)['status'],'FAILED')
        self.assertEqual(self.worker.state['worker_reason'],'CURRENT_BOOT_NOT_READY')
        self.assertEqual(self.worker.state['cleanup_error'],{'code':'AccessDeniedException','operation':'ListTasks'})
        self.assertNotIn('private ARN',json.dumps(self.worker.state))

    def test_list_tasks_uses_supported_cluster_condition_in_boundary_and_operator_policy(self):
        template=builder.build()
        for policy in (template['Resources']['Boundary']['Properties']['PolicyDocument'],
                       template['Resources']['OperatorReviewPolicy']['Properties']['PolicyDocument']):
            entries=[row for row in policy['Statement'] if 'ecs:ListTasks' in row['Action']]
            self.assertEqual(len(entries),1)
            self.assertEqual(entries[0]['Resource'],'*')
            self.assertEqual(entries[0]['Condition'],{'ArnEquals':{'ecs:cluster':{'Ref':'ClusterArn'}},
                'StringEquals':{'aws:RequestedRegion':'ap-northeast-2'}})

    def test_completed_reviewed_historical_empty_lease_is_preserved(self):
        previous=RUN-timedelta(days=1)
        key='CONTROL#RUN#EXIT_0905#'+previous.isoformat()
        row={'pk':{'S':key},'status':{'S':'COMPLETED'},'owner':{'S':'a'*32},
            'started_at':{'S':previous.isoformat()},'finished_at':{'S':(previous+timedelta(seconds=5)).isoformat()}}
        before=copy.deepcopy(row)
        v.require_empty_business_ledger([row],RUN,[key])
        self.assertEqual(row,before)
        with self.assertRaises(ValueError):v.require_empty_business_ledger([row],RUN)

    def test_historical_allowlist_never_allows_a_business_record(self):
        for key in ('WALLET#CLOSING_BET#KRX_1520','OPEN#CLOSING_BET#KRX_1520','OUTBOX#old','EQUITY#paper#old'):
            with self.assertRaises(ValueError):v.require_empty_business_ledger([{'pk':{'S':key}}],RUN,[key])

    def test_unfinished_invalid_same_day_and_late_historical_attempts_are_blocked(self):
        previous=RUN-timedelta(days=1);key='CONTROL#RUN#EXIT_0905#'+previous.isoformat()
        row={'pk':{'S':key},'status':{'S':'COMPLETED'},'owner':{'S':'a'*32},
            'started_at':{'S':previous.isoformat()},'finished_at':{'S':(previous+timedelta(seconds=5)).isoformat()}}
        for field,value in (('status',{'S':'RUNNING'}),('owner',{'S':'invalid'}),
                ('started_at',{'S':(previous-timedelta(seconds=1)).isoformat()}),
                ('finished_at',{'S':(previous+timedelta(seconds=251)).isoformat()})):
            candidate=copy.deepcopy(row);candidate[field]=value
            with self.assertRaises(ValueError):v.require_empty_business_ledger([candidate],RUN,[key])
        row['pk']={'S':'CONTROL#RUN#EXIT_0905#'+RUN.isoformat()}
        with self.assertRaises(ValueError):v.require_empty_business_ledger([row],RUN,[row['pk']['S']])

    def test_retest_parameters_use_new_defaults_without_replacing_resources(self):
        original=builder.build();updated,aliases=builder.next_trial_template(original)
        self.assertEqual(set(original['Resources']),set(updated['Resources']))
        self.assertEqual(original['Resources']['ValidationTask'],updated['Resources']['ValidationTask'])
        for old,new in aliases.items():
            self.assertNotIn(old,updated['Parameters']);self.assertIn(new,updated['Parameters'])
        env=updated['Resources']['Verifier']['Properties']['Environment']['Variables']
        self.assertEqual(env['TEST_ID'],{'Ref':'NextTestId'})
        self.assertEqual(env['RUN_AT'],{'Fn::Sub':'${NextRunAt}+00:00'})
        self.assertIn('${NextTestId}',updated['Resources']['RunTest']['Properties']['Target']['Input']['Fn::Sub'])
        self.assertEqual(updated['Resources']['Verifier']['Properties']['Code'],original['Resources']['Verifier']['Properties']['Code'])

    def test_changed_revision_or_enabled_schedule_prevents_launch(self):
        for revision, state in (('different','DISABLED'),('production','ENABLED')):
            with self.subTest(revision=revision,state=state):
                self.clients['cloudformation'].describe_stacks.return_value={'Stacks':[{
                    'StackStatus':'UPDATE_COMPLETE','Outputs':[{'OutputKey':'TaskDefinitionArn','OutputValue':revision}],
                    'Parameters':[{'ParameterKey':k,'ParameterValue':val} for k,val in {
                        'ImageUri':'reviewed-image','CoreScheduleState':state,'NxtScheduleState':'DISABLED','AssignPublicIp':'DISABLED'}.items()]}]}
                with self.assertRaises(ValueError):self.worker.preflight(RUN)
        self.clients['ecs'].run_task.assert_not_called()

    def test_stale_lease_or_late_finish_does_not_prove_normal_worker_success(self):
        task=self.real_proof()
        for key,value in (('started_at',(RUN-timedelta(seconds=1)).isoformat()),('finished_at',(RUN+timedelta(seconds=251)).isoformat())):
            with self.subTest(key=key):
                old=self.clients['dynamodb'].get_item.return_value['Item'][key]
                self.clients['dynamodb'].get_item.return_value['Item'][key]={'S':value}
                with self.assertRaises(ValueError):self.worker.verify_task(task,RUN,'stock-automation')
                self.clients['dynamodb'].get_item.return_value['Item'][key]=old

    def test_template_does_not_grant_schedule_activation_or_ledger_writes(self):
        t=builder.build();statements=t['Resources']['Boundary']['Properties']['PolicyDocument']['Statement']
        actions={a for row in statements for a in row['Action']}
        self.assertFalse(actions.intersection({'scheduler:UpdateSchedule','dynamodb:PutItem','dynamodb:UpdateItem','ec2:StartInstances'}))
        run=next(row for row in statements if 'ecs:RunTask' in row['Action'])
        self.assertEqual(run['Resource'],{'Ref':'ValidationTask'})
        secrets=next(row for row in statements if 'secretsmanager:GetSecretValue' in row['Action'])
        self.assertEqual(secrets['Resource'],{'Ref':'TelegramSecretArn'})

    def test_template_is_disabled_and_has_only_four_one_off_schedules(self):
        t=builder.build()
        self.assertEqual(t['Parameters']['VerificationState']['Default'],'DISABLED')
        schedules=[r['Properties'] for r in t['Resources'].values() if r['Type']=='AWS::Scheduler::Schedule']
        self.assertEqual(len(schedules),4)
        for schedule in schedules:
            self.assertTrue(schedule['ScheduleExpression']['Fn::Sub'].startswith('at('))
            self.assertEqual(schedule['State'],{'Ref':'VerificationState'})
        self.assertEqual(t,json.loads((ROOT/'infra/paper-worker-verification.yaml').read_text(encoding='utf-8')))

    def test_diagnostic_image_and_isolation_are_explicit_and_source_is_embedded(self):
        t=builder.build();container=t['Resources']['ValidationTask']['Properties']['ContainerDefinitions'][0]
        self.assertEqual(container['Image'],{'Ref':'ImageUri'})
        self.assertTrue(container['ReadonlyRootFilesystem']);self.assertEqual(container['User'],'65534:65534')
        self.assertEqual(container['EntryPoint'],['python'])
        self.assertEqual(container['Command'],['-c',(ROOT/'infra/paper_worker_bootstrap.py').read_text(encoding='utf-8')])
        self.assertEqual(t['Resources']['Verifier']['Properties']['Code']['ZipFile'],(ROOT/'infra/paper_worker_verifier.py').read_text(encoding='utf-8'))


class PrewarmTests(unittest.TestCase):
    def setUp(self):
        self.env={'KIWOOM_MODE':'demo','LIVE_ORDER_ENABLED':'0','RUN_PHASE':'EXIT_0905','SCHEDULED_AT':RUN.isoformat()}

    def test_waits_for_actual_clock_without_changing_occurrence(self):
        clock=Mock(side_effect=[RUN-timedelta(seconds=2),RUN-timedelta(seconds=1),RUN])
        sleep=Mock();before=dict(self.env)
        b.wait_for_occurrence(self.env,clock=clock,sleep=sleep,monotonic=Mock(return_value=0))
        sleep.assert_called_once_with(1);self.assertEqual(self.env,before)

    def test_other_phases_missing_timezone_and_excessive_wait_are_rejected(self):
        for change in ({'RUN_PHASE':'ENTRY_1520'},{'KIWOOM_MODE':'live'},{'SCHEDULED_AT':'2026-10-21T00:05:00'}):
            with self.assertRaises(ValueError):b.wait_for_occurrence({**self.env,**change},clock=lambda:DISPATCH,sleep=Mock(),monotonic=lambda:0)
        with self.assertRaisesRegex(ValueError,'TOO_EARLY'):
            b.wait_for_occurrence(self.env,clock=lambda:RUN-timedelta(seconds=301),sleep=Mock(),monotonic=lambda:0)

    def test_clock_stall_hits_monotonic_bound(self):
        with self.assertRaisesRegex(ValueError,'BOUND'):
            b.wait_for_occurrence(self.env,clock=lambda:DISPATCH,sleep=Mock(),monotonic=Mock(side_effect=[0,301]))

    def test_original_bounded_worker_remains_the_execution_path(self):
        with patch.dict('os.environ',self.env),patch.object(b,'wait_for_occurrence') as wait,patch('stock_automation.scheduled_execution.run_bounded',return_value=2) as run:
            self.assertEqual(b.main(),2);wait.assert_called_once();run.assert_called_once_with()
