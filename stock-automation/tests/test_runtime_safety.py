import io
import json
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone, date
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from stock_automation.runtime_safety import RuntimeRejected, acquire_attempt, finish_attempt, verify_network
from stock_automation.calendar import TradingCalendar


NOW = datetime(2026, 10, 19, 5, 50, tzinfo=timezone.utc)


class RuntimeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.env = {"NAT_INSTANCE_ID": "test-instance", "PAPER_BUCKET": "test-bucket", "EXPECTED_EGRESS_IP": "192.0.2.4"}
        self.vm = {"State": {"Name": "running"}, "SourceDestCheck": False,
            "Tags": [{"Key": "Project", "Value": "paper-fixed-egress"}], "LaunchTime": NOW - timedelta(minutes=10)}
        self.proof = {"state": "READY", "instance_id": "test-instance", "launch_time": self.vm["LaunchTime"].isoformat(),
            "ready_at": (NOW - timedelta(minutes=9)).isoformat(), "expires_at": (NOW + timedelta(minutes=110)).isoformat()}

    def verify(self):
        s3, ec2, probe = Mock(), Mock(), Mock(return_value="192.0.2.4")
        s3.get_object.return_value = {"Body": io.BytesIO(json.dumps(self.proof).encode())}
        ec2.describe_instances.return_value = {"Reservations": [{"Instances": [self.vm]}]}
        verify_network(s3=s3, ec2=ec2, env=self.env, now=NOW, egress_probe=probe)

    def test_current_boot_and_actual_egress_pass(self):
        self.verify()

    def test_old_ready_marker_after_restart_is_rejected(self):
        self.vm["LaunchTime"] = NOW - timedelta(minutes=2)
        with self.assertRaisesRegex(RuntimeRejected, "STALE"):
            self.verify()

    def test_closing_expired_future_or_overlong_ready_proof_is_rejected(self):
        for key, value in (("state", "CLOSING"), ("expires_at", NOW.isoformat()),
                           ("ready_at", (NOW+timedelta(seconds=1)).isoformat()),
                           ("expires_at", (NOW+timedelta(hours=3)).isoformat()),
                           ("instance_id", "other")):
            with self.subTest(key=key, value=value):
                before=deepcopy(self.proof);self.proof[key]=value
                with self.assertRaises(RuntimeRejected):self.verify()
                self.proof=before

    def test_wrong_egress_stopped_nat_or_source_dest_guard_blocks_entry(self):
        self.env["EXPECTED_EGRESS_IP"]="192.0.2.5"
        with self.assertRaisesRegex(RuntimeRejected,"EGRESS"):self.verify()
        self.env["EXPECTED_EGRESS_IP"]="192.0.2.4"
        for update in ({"State":{"Name":"stopped"}},{"SourceDestCheck":True},{"Tags":[]}):
            before=deepcopy(self.vm);self.vm.update(update)
            with self.assertRaises(RuntimeRejected):self.verify()
            self.vm=before

    def test_probe_failure_does_not_leak_private_exception_text(self):
        ec2=Mock();ec2.describe_instances.side_effect=RuntimeError("private identity")
        with self.assertRaisesRegex(RuntimeRejected,"^NETWORK_CHECK_FAILED$"):
            verify_network(s3=Mock(),ec2=ec2,env=self.env,now=NOW,egress_probe=Mock())

    def test_same_occurrence_in_different_timezones_cannot_create_second_attempt(self):
        ddb=Mock();keys=set()
        def put(**kwargs):
            key=kwargs['Item']['pk']['S']
            if key in keys:raise ClientError({'Error':{'Code':'ConditionalCheckFailedException'}},'PutItem')
            keys.add(key)
        ddb.put_item.side_effect=put
        attempt=acquire_attempt(ddb,'paper','ENTRY_1520','2026-10-19T15:20:00+09:00',NOW)
        finish_attempt(ddb,'paper',attempt,'COMPLETED',NOW)
        with self.assertRaisesRegex(RuntimeRejected,'DUPLICATE'):
            acquire_attempt(ddb,'paper','ENTRY_1520','2026-10-19T06:20:00Z',NOW)
        self.assertEqual(len(keys),1)

    def test_stale_or_failed_attempt_is_not_automatically_reacquired(self):
        ddb=Mock();ddb.put_item.side_effect=ClientError({'Error':{'Code':'ConditionalCheckFailedException'}},'PutItem')
        with self.assertRaisesRegex(RuntimeRejected,'UNRECONCILED'):
            acquire_attempt(ddb,'paper','ENTRY_1520','2026-10-19T15:20:00+09:00',NOW+timedelta(days=30))
        ddb.delete_item.assert_not_called()

    def test_finish_can_only_change_its_own_running_attempt(self):
        ddb=Mock();finish_attempt(ddb,'paper',('key','owner'),'RECONCILE_REQUIRED',NOW)
        call=ddb.update_item.call_args.kwargs
        self.assertEqual(call['ConditionExpression'],'#owner = :owner AND #status = :running')
        self.assertEqual(call['ExpressionAttributeNames'],{'#owner':'owner','#status':'status'})
        self.assertEqual(call['ExpressionAttributeValues'][':status'],{'S':'RECONCILE_REQUIRED'})

    def test_unapproved_calendar_flag_is_enforced(self):
        c=TradingCalendar.from_dict({'year':2026,'automatic_schedule_eligible':False,'reviewed_through':'2026-12-31'})
        with self.assertRaisesRegex(ValueError,'CALENDAR_NOT_APPROVED'):c.require_automatic_session(date(2026,10,19))

    def test_closing_entry_before_special_next_session_is_blocked(self):
        c=TradingCalendar.from_dict({'year':2026,'automatic_schedule_eligible':True,'reviewed_through':'2026-12-30',
            'special_session_review_dates':['2026-11-19']})
        with self.assertRaisesRegex(ValueError,'NEXT_SESSION'):c.require_automatic_session(date(2026,11,18),check_next_session=True)
        with self.assertRaisesRegex(ValueError,'NONSTANDARD'):c.require_automatic_session(date(2026,11,19))
        c.require_automatic_session(date(2026,11,20),check_next_session=True)

    def test_review_horizon_and_next_year_fail_closed(self):
        c=TradingCalendar.from_dict({'year':2026,'automatic_schedule_eligible':True,'reviewed_through':'2026-10-23'})
        with self.assertRaisesRegex(ValueError,'NEXT_SESSION'):c.require_automatic_session(date(2026,10,23),check_next_session=True)
        c.require_automatic_session(date(2026,10,22),check_next_session=True)
        with self.assertRaises(ValueError):c.require_automatic_session(date(2026,10,26))


if __name__=='__main__':unittest.main()
