import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('operations_test',ROOT/'tools/paper_operations.py')
ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)


class PaperOperationsTests(unittest.TestCase):
    def setUp(self):
        self.names=['GATE','START_PM','SCAN_1450','SHORTLIST_1510','ENTRY_1520','EQUITY_SNAPSHOT_1550',
            'STOP_PM','REPORT_PM','START_AM','EXIT_0905','EXIT_0910','STOP_AM','REPORT_AM']
        self.plan={'stack_name':'stock-automation-paper-pilot','parameters':{'PilotId':'f'*32,'ArtifactBucketName':'paper',
            'NatInstanceId':'nat','ClusterArn':'cluster','ControlFunctionArn':'controller','EntryDate':'2026-10-23','ExitDate':'2026-10-26'},
            'pilot_plan':{'paper_only':True,'events':dict.fromkeys(self.names,{})}}
        self.clients={name:Mock() for name in ('s3','ec2','ecs','dynamodb','cloudformation','scheduler','lambda')}
        self.trace=[];self.items={};outputs=[]
        for name in self.names:
            n='stock-paper-pilot-'+name.lower().replace('_','-')
            self.items[n]={'Name':n,'Arn':'arn:'+name,'State':'ENABLED','Target':{'original':name},'ScheduleExpression':'at(future)','FlexibleTimeWindow':{'Mode':'OFF'}}
            logical=''.join(x.title() for x in name.split('_'))+'Schedule'
            outputs.append({'OutputKey':logical+'Arn','OutputValue':'arn:'+name})
        self.clients['cloudformation'].describe_stacks.side_effect=lambda **kw:{'Stacks':[{'Outputs':outputs if kw['StackName'].endswith('-pilot') else [{'OutputKey':'ControlFunctionArn','OutputValue':'controller'}]}]}
        self.clients['scheduler'].meta.service_model.operation_model.return_value.input_shape.members={k:None for k in ('Name','State','Target','ScheduleExpression','FlexibleTimeWindow')}
        self.clients['scheduler'].get_schedule.side_effect=lambda **kw:copy.deepcopy(self.items[kw['Name']])
        def update(**kw):
            self.trace.append('DISABLE:'+kw['Name']);self.items[kw['Name']]['State']=kw['State']
        self.clients['scheduler'].update_schedule.side_effect=update
        self.clients['s3'].put_object.side_effect=lambda **kw:self.trace.append('STOP_FENCE')
        def invoke(**kw):
            self.trace.append('CONTROLLER_STOP')
            return {'Payload':io.BytesIO(json.dumps({'state':'STOP_REQUESTED','cleanup_complete':True,'forced_cleanup':False}).encode())}
        self.clients['lambda'].invoke.side_effect=invoke
        self.operator=ops.Operations(self.plan,self.clients,sleep=Mock(),monotonic=lambda:0)
        self.operator.status=Mock(return_value={'server_state':'stopped','running_tasks':0,'pending_tasks':0,'open_virtual_quantity':'0'})

    def test_stop_fences_before_disabling_and_preserves_cleanup_reports(self):
        result=self.operator.stop()
        self.assertEqual(result['status'],'STOPPED');self.assertEqual(result['entry_schedules_disabled'],9)
        self.assertEqual(self.trace[0],'STOP_FENCE');self.assertEqual(self.trace[-1],'CONTROLLER_STOP')
        for name in ('STOP_PM','STOP_AM','REPORT_PM','REPORT_AM'):
            self.assertEqual(self.items['stock-paper-pilot-'+name.lower().replace('_','-')]['State'],'ENABLED')
        payload=json.loads(self.clients['lambda'].invoke.call_args.kwargs['Payload'])
        self.assertEqual(payload['action'],'VERIFY_STOP')
        self.assertEqual(self.clients['s3'].put_object.call_args.kwargs['IfNoneMatch'],'*')
        self.clients['ecs'].run_task.assert_not_called();self.clients['dynamodb'].delete_item.assert_not_called()

    def test_schedule_disable_failure_still_attempts_bounded_controller_stop(self):
        self.clients['scheduler'].update_schedule.side_effect=RuntimeError('unavailable')
        result=self.operator.stop()
        self.assertTrue(result['entry_fence_saved']);self.assertEqual(len(result['schedule_errors']),9)
        self.clients['lambda'].invoke.assert_called_once()

    def test_unconfirmed_controller_cleanup_never_reports_stopped(self):
        self.clients['lambda'].invoke.return_value={'FunctionError':'Unhandled','Payload':io.BytesIO(b'{}')}
        self.clients['lambda'].invoke.side_effect=None
        with self.assertRaisesRegex(ValueError,'CLEANUP_NOT_CONFIRMED'):self.operator.stop()
        self.operator.status.assert_not_called()

    def test_wrong_project_is_rejected_without_any_api_action(self):
        with self.assertRaisesRegex(ValueError,'APPROVED_PAPER'):
            ops.Operations({**self.plan,'stack_name':'another-project'},self.clients)
        self.clients['lambda'].invoke.assert_not_called();self.clients['s3'].put_object.assert_not_called()

    def batch_operator(self):
        batch_plan={'stack_name':'stock-automation-paper-batch-v2','parameters':{'PilotId':'b'*32,'ArtifactBucketName':'paper'},
            'batch_plan':{'paper_only':True,'batch_id':'b'*32,'sessions':[{'entry_date':'2026-10-26','exit_date':'2026-10-27'}]*5}}
        outputs=[]
        for phase in self.names:
            old=self.items['stock-paper-pilot-'+phase.lower().replace('_','-')]
            item={**copy.deepcopy(old),'Name':old['Name'].replace('pilot','batch'),'Arn':'batch:'+phase}
            self.items[item['Name']]=item
            logical=''.join(x.title() for x in phase.split('_'))+'Schedule'
            outputs.append({'OutputKey':logical+'Arn','OutputValue':item['Arn']})
        original=self.clients['cloudformation'].describe_stacks.side_effect
        self.clients['cloudformation'].describe_stacks.side_effect=lambda **kw: {'Stacks':[{'Outputs':outputs}]} if kw['StackName']=='stock-automation-paper-batch-v2' else original(**kw)
        return ops.BatchOperations(batch_plan,self.clients)

    def test_batch_fence_and_disable_precede_parent_controller_cleanup(self):
        batch=self.batch_operator()
        result=batch.stop_entries()
        self.assertEqual(result['entry_schedules_disabled'],9)
        self.assertEqual(self.trace[0],'STOP_FENCE')
        self.assertTrue(all('batch' in x for x in self.trace[1:]))
        self.operator.stop()
        self.assertEqual(self.trace[-1],'CONTROLLER_STOP')
        for phase in ('STOP_PM','STOP_AM','REPORT_PM','REPORT_AM'):
            self.assertEqual(self.items['stock-paper-batch-'+phase.lower().replace('_','-')]['State'],'ENABLED')
        self.clients['dynamodb'].delete_item.assert_not_called()

    def test_batch_disable_errors_do_not_prevent_parent_cleanup(self):
        batch=self.batch_operator()
        self.clients['scheduler'].update_schedule.side_effect=RuntimeError('unavailable')
        self.assertEqual(len(batch.stop_entries()['schedule_errors']),9)
        self.operator.stop()
        self.clients['lambda'].invoke.assert_called_once()

    def test_batch_status_never_treats_access_denied_as_empty(self):
        batch=self.batch_operator()
        self.clients['s3'].list_objects_v2.side_effect=RuntimeError('AccessDenied')
        with self.assertRaises(RuntimeError):batch.status()

    def test_absent_batch_markers_are_reported_without_secret_reads(self):
        batch=self.batch_operator()
        self.clients['s3'].list_objects_v2.return_value={'Contents':[]}
        result=batch.status()
        self.assertEqual(result['ARMED']['status'],'NO_RECORD')
        self.assertEqual(len(result['sessions']),5)
        self.assertEqual(result['bounded_sessions'],5)
        self.clients['s3'].get_object.assert_not_called()

    def test_status_reads_the_wallet_of_the_stack_epoch(self):
        epoch='200K-20261103';key='WALLET#CLOSING_BET#KRX_1520#'+epoch
        wallets={key:{'available_cash':{'N':'200000'}},'WALLET#CLOSING_BET#KRX_1520':{'available_cash':{'N':'587000'}}}
        self.clients['dynamodb'].get_item.side_effect=lambda **kw:{'Item':wallets[kw['Key']['pk']['S']]} if kw['Key']['pk']['S'] in wallets else {}
        self.clients['ec2'].describe_instances.return_value={'Reservations':[{'Instances':[{'State':{'Name':'stopped'}}]}]}
        self.clients['ecs'].describe_clusters.return_value={'clusters':[{'runningTasksCount':0,'pendingTasksCount':0}]}
        self.clients['s3'].list_objects_v2.return_value={'Contents':[]}
        for epoch_value,expected_key,cash in (('','WALLET#CLOSING_BET#KRX_1520','587000'),(epoch,key,'200000')):
            with self.subTest(epoch=epoch_value):
                plan=copy.deepcopy(self.plan);plan['parameters']['PaperWalletEpoch']=epoch_value
                operator=ops.Operations(plan,self.clients);operator.get=Mock(return_value=None)
                result=operator.status()
                self.assertEqual((result['wallet_key'],result['virtual_available_cash']),(expected_key,cash))
        batch=self.batch_operator();batch.params['PaperWalletEpoch']=epoch
        result=batch.status()
        self.assertEqual((result['wallet_key'],result['virtual_available_cash']),(key,'200000'))
        self.clients['dynamodb'].put_item.assert_not_called();self.clients['dynamodb'].delete_item.assert_not_called()

    def test_two_session_batch_status_and_other_lengths_rejected(self):
        plan={'stack_name':'stock-automation-paper-batch-v2','parameters':{'PilotId':'b'*32,'ArtifactBucketName':'paper'},
            'batch_plan':{'paper_only':True,'batch_id':'b'*32,'sessions':[{'entry_date':'2026-10-26','exit_date':'2026-10-27'}]*2}}
        self.clients['s3'].list_objects_v2.return_value={'Contents':[]}
        result=ops.BatchOperations(plan,self.clients).status()
        self.assertEqual((result['bounded_sessions'],len(result['sessions'])),(2,2))
        three=copy.deepcopy(plan);three['batch_plan']['sessions']=three['batch_plan']['sessions'][:1]*3
        self.assertEqual(ops.BatchOperations(three,self.clients).status()['bounded_sessions'],3)
        for count in (1,4):
            other=copy.deepcopy(plan);other['batch_plan']['sessions']=other['batch_plan']['sessions'][:1]*count
            with self.assertRaisesRegex(ValueError,'APPROVED_SESSION_BATCH_REQUIRED'):
                ops.BatchOperations(other,self.clients)


if __name__=='__main__':unittest.main()
