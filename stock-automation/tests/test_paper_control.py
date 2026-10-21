import importlib.util
import io
import json
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

spec=importlib.util.spec_from_file_location('paper_control',Path(__file__).resolve().parents[1]/'infra/paper_control.py')
control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)
NOW=datetime(2026,10,19,8,55,tzinfo=timezone(timedelta(hours=9)))


class PaperControlTests(unittest.TestCase):
    def setUp(self):
        self.clients={n:Mock() for n in ('ec2','ecs','ssm','s3','dynamodb','secretsmanager')}
        self.env={'PAPER_BUCKET':'paper','PAPER_TABLE':'paper','NAT_INSTANCE_ID':'instance',
            'PAPER_CLUSTER':'paper-cluster','PRIVATE_SUBNET_CIDR':'10.77.32.0/24','NOTIFICATION_SECRET_ARN':'test-secret'}
        self.c=control.Controller(clients=self.clients,env=self.env,clock=lambda:NOW,sleep=Mock())
        self.c.notify=Mock()
        self.vm={'State':{'Name':'running'},'SourceDestCheck':False,'LaunchTime':NOW-timedelta(minutes=1),
            'Tags':[{'Key':'Project','Value':'paper-fixed-egress'},{'Key':'Name','Value':'stock-automation-paper-nat'}]}
        self.c.instance=Mock(return_value=self.vm)

    def test_old_or_early_schedule_never_starts_nat(self):
        for timestamp in ('2026-10-17T23:55:00Z','2026-10-18T23:50:00Z','2026-10-19T23:55:00Z'):
            with self.assertRaises(ValueError):
                control.validate_event({'action':'START','window':'morning','scheduled_at':timestamp},NOW)
        self.clients['ec2'].start_instances.assert_not_called()

    def test_expected_schedule_uses_original_time(self):
        action,key,expiry=control.validate_event({'action':'START','window':'morning','scheduled_at':'2026-10-18T23:55:00Z'},NOW+timedelta(seconds=20))
        self.assertEqual(action,'START');self.assertEqual(expiry.hour,9);self.assertEqual(expiry.minute,25)

    def test_manual_verification_requires_explicit_test_id(self):
        with self.assertRaisesRegex(ValueError,'TEST_ID'):
            control.validate_event({'action':'VERIFY_START'},NOW)

    def test_unreviewed_calendar_blocks_start_before_instance_mutation(self):
        self.clients['s3'].get_object.return_value={'Body':io.BytesIO(json.dumps({'year':2026,'automatic_schedule_eligible':False}).encode())}
        with self.assertRaisesRegex(ValueError,'CALENDAR_NOT_APPROVED'):
            self.c.handle({'action':'START','window':'morning','scheduled_at':NOW.isoformat()})
        self.clients['ec2'].start_instances.assert_not_called()

    def test_failed_current_boot_readiness_invalidates_marker_and_stops_nat(self):
        stopped={**self.vm,'State':{'Name':'stopped'}}
        self.c.instance=Mock(side_effect=[stopped,self.vm])
        self.clients['ssm'].describe_instance_information.return_value={'InstanceInformationList':[{'PingStatus':'Online'}]}
        self.clients['ssm'].send_command.return_value={'Command':{'CommandId':'command'}}
        self.clients['ssm'].get_command_invocation.return_value={'Status':'Failed','StandardOutputContent':'old marker ignored'}
        with self.assertRaisesRegex(ValueError,'NETWORK_CONTROL_FAILED'):
            self.c.handle({'action':'VERIFY_START','test_id':'test'})
        states=[json.loads(x.kwargs['Body'])['state'] for x in self.clients['s3'].put_object.call_args_list]
        self.assertEqual(states,['STARTING','FAILED'])
        self.clients['ec2'].stop_instances.assert_called_once_with(InstanceIds=['instance'])
        self.c.notify.assert_called_once_with('NETWORK_CONTROL_FAILED')

    def test_successful_readiness_proof_is_pinned_to_the_current_launch(self):
        self.c.instance=Mock(side_effect=[{**self.vm,'State':{'Name':'stopped'}},self.vm,self.vm])
        self.clients['ssm'].describe_instance_information.return_value={'InstanceInformationList':[{'PingStatus':'Online'}]}
        self.clients['ssm'].send_command.return_value={'Command':{'CommandId':'command'}}
        self.clients['ssm'].get_command_invocation.return_value={'Status':'Success','StandardOutputContent':'PAPER_BOOT_VERIFIED'}
        self.assertEqual(self.c.start(NOW+timedelta(minutes=30)),{'state':'READY'})
        proof=json.loads(self.clients['s3'].put_object.call_args.kwargs['Body'])
        self.assertEqual(proof['launch_time'],self.vm['LaunchTime'].isoformat())
        self.assertEqual(proof['expires_at'],(NOW+timedelta(minutes=30)).isoformat())

    def test_duplicate_start_is_not_retried_or_rearmed(self):
        self.clients['dynamodb'].put_item.side_effect=ClientError({'Error':{'Code':'ConditionalCheckFailedException'}},'PutItem')
        self.assertEqual(self.c.handle({'action':'VERIFY_START','test_id':'test'}),{'state':'DUPLICATE_BLOCKED'})
        self.clients['ec2'].start_instances.assert_not_called();self.clients['ssm'].send_command.assert_not_called()

    def test_new_start_request_does_not_stop_an_already_running_window(self):
        with self.assertRaises(ValueError):
            self.c.handle({'action':'VERIFY_START','test_id':'different-request'})
        self.clients['ec2'].stop_instances.assert_not_called()
        self.clients['s3'].put_object.assert_not_called()

    def test_stop_fences_new_work_before_waiting_and_stops_after_completion(self):
        events=[]
        self.c.mark=Mock(side_effect=lambda state,**kwargs:events.append(state))
        pending={'task':{'taskArn':'task'}}
        self.c.tasks=Mock(side_effect=lambda:events.append('INSPECT') or (pending if events.count('INSPECT')==1 else {}))
        self.clients['ec2'].stop_instances.side_effect=lambda **kwargs:events.append('STOP')
        result=self.c.stop()
        self.assertEqual(events[0],'CLOSING');self.assertEqual(events[-1],'STOP')
        self.assertFalse(result['forced_cleanup']);self.assertTrue(result['cleanup_complete'])
        self.clients['ecs'].stop_task.assert_not_called()

    def test_overdue_task_is_stopped_and_requires_reconciliation(self):
        self.c.tasks=Mock(side_effect=[{'task':{}}]*12+[{}])
        result=self.c.stop()
        self.clients['ecs'].stop_task.assert_called_once()
        self.assertTrue(result['forced_cleanup']);self.assertTrue(result['cleanup_complete'])
        self.c.notify.assert_called_once_with('TASK_CLEANUP_RECONCILE_REQUIRED')

    def test_cleanup_failure_cannot_extend_network_without_bound(self):
        self.c.tasks=Mock(return_value={'task':{}})
        result=self.c.stop()
        self.assertEqual(self.c.sleep.call_count,24)
        self.assertFalse(result['cleanup_complete'])
        self.clients['ec2'].stop_instances.assert_called_once()
        states=[json.loads(x.kwargs['Body'])['state'] for x in self.clients['s3'].put_object.call_args_list]
        self.assertEqual(states,['CLOSING','CLEANUP_FAILED'])

    def test_stop_inspection_failure_still_bounds_nat_and_alerts(self):
        self.c.tasks=Mock(side_effect=RuntimeError('private failure'))
        with self.assertRaisesRegex(ValueError,'NETWORK_CONTROL_FAILED'):
            self.c.handle({'action':'VERIFY_STOP','test_id':'test'})
        self.clients['ec2'].stop_instances.assert_called_once()
        self.c.notify.assert_called_once_with('NETWORK_CONTROL_FAILED')

    def test_wrong_cluster_and_successful_task_do_not_send_failure_alert(self):
        self.c.handle({'source':'aws.ecs','detail':{'clusterArn':'other','lastStatus':'STOPPED'}})
        self.c.handle({'source':'aws.ecs','detail':{'clusterArn':'paper-cluster','lastStatus':'STOPPED','containers':[{'exitCode':0}]}})
        self.c.notify.assert_not_called()

    def test_failed_task_alert_never_contains_raw_event_or_reason(self):
        self.c.handle({'source':'aws.ecs','detail':{'clusterArn':'paper-cluster','lastStatus':'STOPPED',
            'taskArn':'private-task','stoppedAt':'test','stoppedReason':'private body','containers':[{'exitCode':124}]}})
        self.c.notify.assert_called_once_with('ECS_TASK_FAILED_RECONCILE_REQUIRED')

    def test_duplicate_task_failure_does_not_send_a_second_alert(self):
        self.clients['dynamodb'].put_item.side_effect=ClientError({'Error':{'Code':'ConditionalCheckFailedException'}},'PutItem')
        result=self.c.handle({'source':'aws.ecs','detail':{'clusterArn':'paper-cluster','lastStatus':'STOPPED','containers':[{'exitCode':2}]}})
        self.assertEqual(result['state'],'DUPLICATE_BLOCKED');self.c.notify.assert_not_called()


if __name__=='__main__':unittest.main()
