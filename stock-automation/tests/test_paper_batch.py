import ast
import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
import zlib
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'infra'))
import paper_batch as b
import paper_pilot as p


def build_plan():
    calendar = {'year': 2026, 'reviewed_through': '2026-12-31', 'automatic_schedule_eligible': True,
                'holidays': [], 'special_session_review_dates': []}
    parent = {'entry_date': '2026-10-23', 'exit_date': '2026-10-26', 'starting_cash': '600000',
              'paper_only': True, 'approved_calendar': calendar, 'events': {},
              'decision_key': 'runs/2026/10/23/KRX_1520/decision.json'}
    result = {'batch_id': 'b'*32, 'paper_only': True, 'starting_cash': '600000', 'template': parent,
        'parent': {'prefix': 'validation/pilot/parent', 'pilot_id': 'a'*32,
                   'plan_key': 'parent-plan.json', 'plan_sha256': '0'*64, 'plan': parent},
        'sessions': [{'entry_date': start, 'exit_date': end, 'pilot_id': str(i+1)*32} for i, (start, end) in enumerate([
            ('2026-10-26', '2026-10-27'), ('2026-10-27', '2026-10-28'), ('2026-10-28', '2026-10-29'),
            ('2026-10-29', '2026-10-30'), ('2026-10-30', '2026-11-02')])]}
    fake = copy.deepcopy(result)
    fake['sessions'][0] = {'entry_date': parent['entry_date'], 'exit_date': parent['exit_date'], 'pilot_id': 'a'*32}
    parent.update(b.session_plan(fake, 0))
    parent['events']['GATE']['dispatch_at'] = '2026-10-23T00:25:00+00:00'
    result['template'] = copy.deepcopy(parent)
    return result


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan()
        self.parent_raw = json.dumps(self.plan['parent']['plan']).encode()
        self.plan['parent']['plan_sha256'] = hashlib.sha256(self.parent_raw).hexdigest()
        self.items = {}
        self.clients = {name: Mock() for name in ('s3', 'ecs', 'ec2', 'dynamodb', 'scheduler', 'cloudformation', 'lambda', 'secretsmanager')}
        self.raw = json.dumps(self.plan).encode()
        self.env = {'PAPER_BUCKET': 'paper', 'PAPER_TABLE': 'stock-automation-paper', 'PILOT_ID': 'b'*32,
                    'PLAN_KEY': 'batch-plan.json', 'PLAN_SHA256': hashlib.sha256(self.raw).hexdigest(),
                    'RESULT_PREFIX': 'validation/batch/root', 'NAT_INSTANCE_ID': 'nat', 'CLUSTER_ARN': 'cluster',
                    'TASK_DEFINITION_ARN': 'batch-task', 'SUBNET_IDS': 'private', 'SECURITY_GROUP_IDS': 'outbound'}
        self.now = p.stamp(b.session_plan(self.plan, 0)['events']['GATE']['dispatch_at'])
        self.clients['s3'].get_object.side_effect = lambda **kw: {'Body': io.BytesIO(self.parent_raw if kw['Key']=='parent-plan.json' else self.raw)}
        def put(**kw):
            if kw.get('IfNoneMatch') == '*' and kw['Key'] in self.items:
                raise ValueError('CAS_ALREADY_EXISTS')
            self.items[kw['Key']] = json.loads(kw['Body'])
        self.clients['s3'].put_object.side_effect = put
        self.worker = self.make_worker()

    def make_worker(self):
        worker = b.Batch(self.clients, dict(self.env), clock=lambda: self.now, sleep=Mock())
        def get(key, optional=False):
            if key not in self.items:
                if optional:
                    return None
                raise ValueError('REQUIRED_OBJECT_MISSING')
            return copy.deepcopy(self.items[key])
        worker.get = Mock(side_effect=get)
        worker.notify = Mock()
        worker.rows = Mock(return_value=[{'pk': {'S': 'WALLET#CLOSING_BET#KRX_1520'},
            'initial_cash': {'N': '600000'}, 'available_cash': {'N': '575000'}, 'invested_principal': {'N': '0'}}])
        worker.proof = Mock()
        worker.configuration = Mock()
        worker.idle = Mock()
        return worker

    def event(self, phase, index=0):
        at = b.session_plan(self.plan, index)['events'][phase]['dispatch_at']
        self.now = p.stamp(at)
        return {'action': phase, 'batch_id': 'b'*32, 'scheduled_at': at}

    def ready(self, index=0):
        slot = self.plan['sessions'][index]
        self.items['validation/batch/root/sessions/'+slot['entry_date']+'/ready.json'] = {
            'status': 'READY', 'pilot_id': slot['pilot_id'], 'plan_sha256': self.env['PLAN_SHA256']}

    def complete_parent(self):
        plan = self.plan['parent']['plan']
        for phase, status in b.EXPECTED.items():
            at = p.stamp(plan['events'][phase]['dispatch_at']).isoformat()
            self.items['validation/pilot/parent/'+phase+'.json'] = {
                'status': status, 'pilot_id': 'a'*32, 'started_at': at, 'finished_at': at,
                'report': {'decision': 'NO_TRADE', 'open_positions': 0, 'network_stopped_and_idle': True}}
        artifact = {'idempotency_key': '20261023:KRX_1520', 'decision': 'NO_TRADE'}
        self.items[plan['decision_key']] = artifact
        self.leases = {}
        for phase in p.PHASE_TIMES:
            at = p.stamp(plan['events'][phase]['scheduled_at']).isoformat()
            self.leases['CONTROL#RUN#'+phase+'#'+at] = {'status': {'S': 'COMPLETED'}, 'owner': {'S': 'd'*32},
                                                     'started_at': {'S': at}, 'finished_at': {'S': at}}
        self.leases[artifact['idempotency_key']] = {'payload_json': {'S': json.dumps(artifact)}}
        self.clients['dynamodb'].get_item.side_effect = lambda **kw: {'Item': copy.deepcopy(self.leases.get(kw['Key']['pk']['S'], {}))}

    def test_two_session_batch_is_accepted_and_reports_its_own_length(self):
        short = copy.deepcopy(self.plan)
        short['sessions'] = short['sessions'][:2]
        b.validate_batch(short)
        for count in (1, 3, 4, 6):
            value = copy.deepcopy(self.plan)
            value['sessions'] = (value['sessions'] * 2)[:count]
            with self.assertRaisesRegex(ValueError, 'APPROVED_PAPER_SESSION_COUNT_REQUIRED|NONCONTIGUOUS'):
                b.validate_batch(value)
        batch = b.Batch({}, {})
        batch.batch, batch.index = short, 1
        batch.current_plan = b.session_plan(short, 1)
        batch.get = Mock(return_value={})
        with unittest.mock.patch.object(p.Pilot, 'notify') as parent:
            batch.notify('GATE: READY. Bounded 2-session paper batch.')
        self.assertIn('회차: 2/2 (진입일 2026-10-27)', parent.call_args.args[0])

    def test_exact_five_contiguous_calendar_approved_sessions_only(self):
        b.validate_batch(self.plan)
        for mutation in (lambda x: x.update(paper_only=False), lambda x: x.update(starting_cash='1'),
                         lambda x: x['sessions'].pop(), lambda x: x['sessions'][1].update(entry_date='2026-10-28'),
                         lambda x: x['sessions'][1].update(pilot_id=x['sessions'][0]['pilot_id']),
                         lambda x: x['sessions'][4].update(exit_date='2026-11-01'),
                         lambda x: x['template']['approved_calendar'].update(reviewed_through='2026-10-30')):
            value = copy.deepcopy(self.plan)
            mutation(value)
            with self.assertRaises(ValueError):
                b.validate_batch(value)

    def test_gate_is_after_previous_report_and_workers_keep_real_clock(self):
        for index in range(5):
            plan = b.session_plan(self.plan, index)
            self.assertEqual(p.stamp(plan['events']['GATE']['dispatch_at']).astimezone(p.KST).strftime('%H:%M'), '09:45')
            for phase in p.PHASE_TIMES:
                item = plan['events'][phase]
                self.assertEqual((p.stamp(item['scheduled_at'])-p.stamp(item['dispatch_at'])).total_seconds(), 120 if phase == 'EXIT_0910' else 180)

    def test_missing_predecessor_halts_before_any_host_or_task_start(self):
        self.items['validation/batch/root/ARMED.json'] = {'status': 'ARMED', 'plan_sha256': self.env['PLAN_SHA256']}
        result = self.worker.handle(self.event('GATE'))
        self.assertEqual(result['status'], 'BLOCKED_OR_FAILED')
        self.assertIn('validation/batch/root/HALT.json', self.items)
        self.clients['lambda'].invoke.assert_not_called()
        self.clients['ecs'].run_task.assert_not_called()

    def test_gate_accepts_only_complete_predecessor_and_preserves_wallet(self):
        self.complete_parent()
        self.items['validation/batch/root/ARMED.json'] = {'status': 'ARMED', 'plan_sha256': self.env['PLAN_SHA256']}
        result = self.worker.handle(self.event('GATE'))
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(self.worker.rows()[0]['available_cash'], {'N': '575000'})
        self.clients['dynamodb'].put_item.assert_not_called()
        self.clients['dynamodb'].update_item.assert_not_called()

    def test_incomplete_worker_or_bad_lease_cannot_count_as_success(self):
        for mutation in ('marker', 'lease', 'time', 'report', 'decision'):
            self.complete_parent()
            if mutation == 'marker':
                self.items['validation/pilot/parent/ENTRY_1520.json']['status'] = 'BLOCKED_OR_FAILED'
            elif mutation == 'lease':
                self.leases[next(k for k in self.leases if 'ENTRY_1520' in k)]['status'] = {'S': 'RUNNING'}
            elif mutation == 'time':
                self.leases[next(k for k in self.leases if 'ENTRY_1520' in k)]['started_at'] = {'S': '2026-10-23T06:21:00+00:00'}
            elif mutation == 'report':
                self.items['validation/pilot/parent/REPORT_AM.json']['report']['network_stopped_and_idle'] = False
            else:
                self.leases['20261023:KRX_1520']['payload_json'] = {'S': '{}'}
            with self.assertRaises(ValueError):
                self.worker.completed('validation/pilot/parent', 'a'*32, self.plan['parent']['plan'])

    def test_open_pending_or_unreconciled_wallet_blocks_next_entry(self):
        original = self.worker.rows()
        mutations = [original+[{'pk': {'S': 'OPEN#CLOSING_BET#KRX_1520'}}], original+[{'pk': {'S': 'PENDING#unknown'}}],
                     [{**original[0], 'invested_principal': {'N': '1'}}],
                     [{**original[0], 'available_cash': {'N': '-1'}}],
                     [{**original[0], 'pk': {'S': 'WALLET#MEDIUM_TERM#KRX'}}]]
        for rows in mutations:
            self.worker.rows.return_value = rows
            with self.assertRaises(ValueError):
                self.worker.wallet()

    def test_no_trade_predecessor_may_have_no_wallet_but_open_state_still_blocks(self):
        self.worker.rows.return_value=[]
        self.assertEqual(self.worker.wallet(allow_uncreated=True),[])
        with self.assertRaisesRegex(ValueError,'ISOLATED_PAPER_WALLET'):
            self.worker.wallet()

    def test_halt_blocks_new_entry_but_preserves_existing_scheduled_exit(self):
        self.items['validation/batch/root/HALT.json'] = {'status': 'NEW_ENTRIES_HALTED'}
        self.ready()
        self.worker.run = Mock(return_value='COMPLETED')
        self.assertEqual(self.worker.handle(self.event('ENTRY_1520'))['status'], 'BLOCKED_OR_FAILED')
        self.worker.run.assert_not_called()
        worker = self.make_worker()
        worker.run = Mock(return_value='COMPLETED')
        self.assertEqual(worker.handle(self.event('EXIT_0910'))['status'], 'COMPLETED')
        worker.run.assert_called_once()

    def test_manual_stop_fences_exit_launch_but_keeps_cleanup_callable(self):
        self.items['validation/batch/root/STOP.json'] = {'status': 'STOPPED_BY_OPERATOR'}
        self.ready()
        self.worker.run = Mock()
        self.assertEqual(self.worker.handle(self.event('EXIT_0910'))['status'], 'BLOCKED_OR_FAILED')
        self.worker.run.assert_not_called()
        worker = self.make_worker()
        self.items['validation/batch/root/sessions/2026-10-26/START_AM.json'] = {'status': 'BLOCKED_OR_FAILED'}
        worker.controller = Mock(return_value='STOP_REQUESTED')
        self.assertEqual(worker.handle(self.event('STOP_AM'))['status'], 'STOP_REQUESTED')
        worker.controller.assert_called_once()

    def test_hash_wrong_event_late_or_sixth_session_never_launches(self):
        good = self.event('ENTRY_1520')
        for event in ({**good, 'action': 'LIVE_ENTRY'}, {**good, 'extra': 'override'},
                      {**good, 'batch_id': 'wrong'}, {**good, 'scheduled_at': '2026-11-02T06:17:00+00:00'}):
            with self.assertRaises(ValueError):
                self.worker.handle(event)
        self.now += timedelta(seconds=61)
        with self.assertRaisesRegex(ValueError, 'DISPATCH'):
            self.worker.handle(good)
        self.env['PLAN_SHA256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'HASH'):
            self.make_worker().handle(good)
        self.clients['ecs'].run_task.assert_not_called()

    def test_duplicate_phase_is_not_replayed(self):
        self.items['validation/batch/root/sessions/2026-10-26/ENTRY_1520.json'] = {'status': 'RUNNING'}
        self.assertEqual(self.worker.handle(self.event('ENTRY_1520'))['status'], 'ALREADY_ATTEMPTED')
        self.clients['s3'].put_object.assert_not_called()

    def test_changed_ledger_after_report_blocks_successor(self):
        self.complete_parent()
        self.items['validation/pilot/parent/REPORT_AM.json']['ledger_digest'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'LEDGER_CHANGED'):
            self.worker.completed('validation/pilot/parent', 'a'*32, self.plan['parent']['plan'], True)

    def test_date_adapter_only_adds_approved_dates(self):
        client = Mock()
        plan = b.session_plan(self.plan, 4)
        args = {'overrides': {'containerOverrides': [{'environment': [{'name': 'RUN_PHASE', 'value': 'ENTRY_1520'}]}]}}
        b.DatedECS(client, plan).run_task(**args)
        values = {x['name']: x['value'] for x in client.run_task.call_args.kwargs['overrides']['containerOverrides'][0]['environment']}
        self.assertEqual(values, {'RUN_PHASE': 'ENTRY_1520', 'PILOT_ENTRY_DATE': '2026-10-30', 'PILOT_EXIT_DATE': '2026-11-02'})
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_DATE'):
            b.DatedECS(client, plan).run_task(**args)

    def test_deployment_check_reads_actual_scope_without_claiming_future_pass(self):
        self.items['validation/pilot/parent/ARMED.json']={'status':'ARMED','plan_sha256':self.plan['parent']['plan_sha256']}
        self.now-=timedelta(days=1)
        result=self.worker.handle({'action':'DEPLOYMENT_CHECK','batch_id':'b'*32})
        self.assertEqual(result,{'status':'DEPLOYMENT_VERIFIED','paper_only':True,'mutations':False,
                                 'predecessor_success':'PENDING_REAL_EXECUTION'})
        self.clients['s3'].put_object.assert_not_called()
        self.clients['ecs'].run_task.assert_not_called()
        self.clients['lambda'].invoke.assert_not_called()
        self.worker.notify.assert_not_called()

    def test_cancelled_parent_cannot_arm_continuation(self):
        self.items['validation/pilot/parent/STOP.json']={'status':'STOPPED_BY_OPERATOR'}
        self.now-=timedelta(days=1)
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_MANUALLY_STOPPED'):
            self.worker.handle({'action':'DEPLOYMENT_CHECK','batch_id':'b'*32})
        self.clients['s3'].put_object.assert_not_called()


class BatchTemplateTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('batch_builder_tests', ROOT/'tools/build_paper_batch_template.py')
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.template = self.builder.build()

    def test_only_fifteen_bounded_disabled_schedules_and_two_native_stops(self):
        schedules = [x['Properties'] for x in self.template['Resources'].values() if x['Type'] == 'AWS::Scheduler::Schedule']
        self.assertEqual(len(schedules), 15)
        native = 0
        for schedule in schedules:
            self.assertEqual(schedule['State'], {'Ref': 'PilotState'})
            self.assertIn('StartDate', schedule)
            self.assertIn('EndDate', schedule)
            self.assertEqual(schedule['ScheduleExpressionTimezone'], 'Asia/Seoul')
            self.assertEqual(schedule['Target']['RetryPolicy'], {'MaximumEventAgeInSeconds': 60, 'MaximumRetryAttempts': 0})
            if 'FALLBACK' in schedule['Name'].upper():
                native += 1
                self.assertIn('stopInstances', str(schedule['Target']['Arn']))
        self.assertEqual(native, 2)
        self.assertEqual(self.template['Parameters']['PilotState']['Default'], 'DISABLED')
        self.assertNotIn('OperatorReviewPolicy', self.template['Resources'])
        self.assertFalse(any(x['Type']=='AWS::IAM::ManagedPolicy' and 'Users' in x.get('Properties',{})
                             for x in self.template['Resources'].values()))

    def test_schedule_bounds_use_eventbridge_scheduler_millisecond_utc_format(self):
        import re
        for name in ('PmStart', 'PmEnd', 'AmStart', 'AmEnd'):
            parameter = self.template['Parameters'][name]
            self.assertEqual(parameter['Type'], 'String')
            pattern = parameter['AllowedPattern']
            self.assertIsNotNone(re.fullmatch(pattern, '2026-10-22T00:00:00.000Z'))
            for invalid in ('2026-10-22T00:00:00Z', '2026-10-22T00:00:00.000+09:00', 'invalid'):
                self.assertIsNone(re.fullmatch(pattern, invalid))

    def test_packaged_sources_are_exact_plaintext_and_no_ledger_or_schedule_writes(self):
        source = self.template['Resources']['Pilot']['Properties']['Code']['ZipFile']
        tree = ast.parse(source)
        assignment = next(x for x in tree.body if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SOURCES_ZLIB_BASE64' for t in x.targets))
        sources = json.loads(zlib.decompress(base64.b64decode(ast.literal_eval(assignment.value))))
        for name in ('paper_pilot', 'paper_batch'):
            self.assertEqual(sources[name], (ROOT/'infra'/f'{name}.py').read_text(encoding='utf-8'))
        policy = self.template['Resources']['Boundary']['Properties']['PolicyDocument']
        actions = {action for statement in policy['Statement'] for action in statement['Action']}
        self.assertFalse(actions & {'scheduler:UpdateSchedule', 'dynamodb:PutItem', 'dynamodb:UpdateItem', 'ec2:StartInstances'})
        self.assertEqual(self.template['Resources']['PilotTask']['Properties']['Family'], 'stock-automation-paper-batch')


class BatchSessionParentTests(unittest.TestCase):
    """A later batch may follow the last session of an earlier approved batch."""
    def setUp(self):
        self.previous = build_plan()
        raw = json.dumps(self.previous).encode()
        self.batch = copy.deepcopy(self.previous)
        self.batch.update(batch_id='c'*32, sessions=[
            {'entry_date': '2026-11-02', 'exit_date': '2026-11-03', 'pilot_id': '6'*32},
            {'entry_date': '2026-11-03', 'exit_date': '2026-11-04', 'pilot_id': '7'*32}],
            parent={'kind': 'batch_session', 'prefix': 'validation/batch/prev', 'plan_key': 'prev-plan.json',
                    'plan_sha256': hashlib.sha256(raw).hexdigest(), 'batch_plan': self.previous})
        self.items = {}
        self.worker = b.Batch({}, {})
        self.worker.batch = self.batch
        self.worker.get = Mock(side_effect=lambda key, optional=False: copy.deepcopy(self.items.get(key)))

    def test_two_sessions_after_previous_batch_are_valid(self):
        b.validate_batch(self.batch)
        reference = b.parent_reference(self.batch)
        self.assertEqual(reference['session_prefix'], 'validation/batch/prev/sessions/2026-10-30')
        self.assertEqual(reference['plan'], b.session_plan(self.previous, 4))
        self.assertTrue(reference['require_digest'])

    def test_gap_reused_identity_unknown_kind_or_invalid_previous_plan_rejected(self):
        mutations = (lambda x: x['sessions'][0].update(entry_date='2026-11-03'),
                     lambda x: x['sessions'][1].update(pilot_id='5'*32),
                     lambda x: x.update(batch_id='b'*32),
                     lambda x: x['parent'].update(kind='other'),
                     lambda x: x['parent']['batch_plan']['sessions'].pop())
        for mutation in mutations:
            value = copy.deepcopy(self.batch)
            mutation(value)
            with self.assertRaises(ValueError):
                b.validate_batch(value)

    def test_predecessor_is_previous_last_session_with_ledger_digest(self):
        self.assertEqual(self.worker.predecessor(0), ('validation/batch/prev/sessions/2026-10-30', '5'*32,
                                                      b.session_plan(self.previous, 4), True))

    def test_previous_batch_halt_or_stop_blocks_new_batch(self):
        for key, code in (('validation/batch/prev/HALT.json', 'PREDECESSOR_BATCH_HALTED'),
                          ('validation/batch/prev/STOP.json', 'PREDECESSOR_MANUALLY_STOPPED'),
                          ('validation/batch/prev/sessions/2026-10-30/STOP.json', 'PREDECESSOR_MANUALLY_STOPPED')):
            self.items = {key: {'status': 'X'}}
            with self.assertRaisesRegex(ValueError, code):
                self.worker.predecessor(0)

    def test_pilot_parent_keeps_original_shape(self):
        reference = b.parent_reference(build_plan())
        self.assertEqual((reference['session_prefix'], reference['require_digest'], reference['halt_key']),
                         ('validation/pilot/parent', False, None))


class BatchNotificationExplanationTests(unittest.TestCase):
    def test_report_message_keeps_codes_and_adds_korean_meaning(self):
        message = 'REPORT_PM: decision=NO_TRADE; entry_worker=COMPLETED; exit_worker=NO_RECORD; open_positions=0.'
        text = b.explain(message, (2, 5, '2026-10-27'), '종가배팅 기준을 충족한 종목 없음')
        self.assertIn('회차: 2/5 (진입일 2026-10-27)', text)
        self.assertIn('16:15 오후 결과 보고', text)
        self.assertIn('NO_TRADE', text)
        self.assertIn('정상 결과', text)
        self.assertIn('판단 사유: 종가배팅 기준을 충족한 종목 없음', text)
        self.assertIn('15:20 판단 작업: 정상 종료', text)
        self.assertIn('다음 거래일 오전 예정', text)
        self.assertIn('열린 가상 포지션: 없음', text)

    def test_failure_and_reconciliation_explain_halt_and_cause(self):
        failed = b.explain('2026-10-27 ENTRY_1520: BLOCKED_OR_FAILED. PREREQUISITE_NOT_COMPLETED')
        self.assertIn('15:20 가상매수 판단', failed)
        self.assertIn('자동 중지(HALT)', failed)
        self.assertIn('15:10 후보', failed)
        unknown = b.explain('2026-10-27 STOP_PM: BLOCKED_OR_FAILED. ClientError')
        self.assertIn('ClientError (AWS 호출 또는 미분류 오류', unknown)
        reconcile = b.explain('REPORT_AM: decision=BUY; entry_worker=COMPLETED; exit_worker=COMPLETED; '
                              'open_positions=1. RECONCILIATION_REQUIRED.')
        self.assertIn('열린 가상 포지션: 1개', reconcile)
        self.assertIn('확인 필요', reconcile)
        self.assertNotIn('준비 완료', b.explain('GATE: BLOCKED_OR_FAILED. PILOT_NOT_READY'))

    def make(self, artifact):
        batch = b.Batch({}, {})
        batch.batch = build_plan()
        batch.index = 1
        batch.current_plan = b.session_plan(batch.batch, 1)
        batch.get = Mock(return_value=artifact)
        return batch

    def test_notify_appends_explanation_and_reads_only_decision_reason(self):
        batch = self.make({'reason_codes': ['NO_QUALIFYING_CANDIDATE'],
                           'notes': '앞선 후보 선별은 완료됐지만 통과한 종목이 없어 모의매수를 진행하지 않았습니다.'})
        with unittest.mock.patch.object(p.Pilot, 'notify') as parent:
            batch.notify('REPORT_PM: decision=NO_TRADE; entry_worker=COMPLETED; exit_worker=NO_RECORD; open_positions=0.')
        text = parent.call_args.args[0]
        self.assertTrue(text.startswith('REPORT_PM: decision=NO_TRADE;'))
        self.assertIn('회차: 2/5 (진입일 2026-10-27)', text)
        self.assertIn('판단 사유: 종가배팅 기준을 충족한 종목 없음 — 앞선 후보 선별은 완료', text)
        batch.get.assert_called_once_with(batch.current_plan['decision_key'], optional=True)

    def test_explanation_failures_still_send_original_message(self):
        batch = self.make({})
        batch.get.side_effect = RuntimeError('read failed')
        with unittest.mock.patch.object(p.Pilot, 'notify') as parent:
            batch.notify('REPORT_PM: decision=BUY; entry_worker=COMPLETED; exit_worker=NO_RECORD; open_positions=1.')
        self.assertNotIn('판단 사유', parent.call_args.args[0])
        with unittest.mock.patch.object(b, 'explain', side_effect=ValueError('boom')), \
                unittest.mock.patch.object(p.Pilot, 'notify') as parent:
            batch.notify('GATE: READY. Bounded five-session paper batch.')
        parent.assert_called_once_with('GATE: READY. Bounded five-session paper batch.')

    def test_english_legacy_notes_are_not_shown_as_reason(self):
        batch = self.make({'reason_codes': ['MARKET_DATA_UNAVAILABLE'],
                           'notes': 'Selection threshold or mandatory risk filters were not satisfied.'})
        self.assertEqual(batch.decision_reason(), '검증 가능한 시세 자료 없음')


if __name__ == '__main__':
    unittest.main()
