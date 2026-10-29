"""Five dated paper sessions after verified predecessor completion.

No broker orders, ledger writes, schedule mutation, or automatic HALT reset.
The original one-session pilot and its immutable plan remain unchanged.
"""
import copy
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
import paper_pilot as p

LIMITS = {'SCAN_1450': (240, 300), 'SHORTLIST_1510': (180, 180),
          'ENTRY_1520': (59, 60), 'EQUITY_SNAPSHOT_1550': (180, 180),
          'EXIT_0905': (120, 120), 'EXIT_0910': (120, 120)}
# Only these reviewed run lengths are accepted; any other count fails closed.
ALLOWED_SESSION_COUNTS = (2, 3, 5)
EXPECTED = {'GATE': 'READY', 'START_PM': 'READY', 'START_AM': 'READY',
            'STOP_PM': 'STOP_REQUESTED', 'STOP_AM': 'STOP_REQUESTED',
            'REPORT_PM': 'REPORTED', 'REPORT_AM': 'REPORTED',
            **{name: 'COMPLETED' for name in p.PHASE_TIMES}}
# Phases that start a host or a worker; GATE and reports only read state.
LAUNCH_PHASES = ('START_PM', 'START_AM', *p.PHASE_TIMES)


# Telegram explanations. The first message line keeps the original codes for log
# matching; these lines only translate them and never change any decision.
PHASE_KO = {'GATE': '09:45 준비 검사(직전 회차 정상 종료·설정 변경 여부 확인)',
    'START_PM': '14:40 서버·네트워크 켜기', 'STOP_PM': '16:10 작업 정리·서버 끄기',
    'REPORT_PM': '16:15 오후 결과 보고', 'START_AM': '08:55 다음 날 서버 켜기',
    'STOP_AM': '09:25 다음 날 작업 정리·서버 끄기', 'REPORT_AM': '09:40 회차 최종 결과 보고',
    'SCAN_1450': '14:50 시장 스캔', 'SHORTLIST_1510': '15:10 후보 축소',
    'ENTRY_1520': '15:20 가상매수 판단', 'EQUITY_SNAPSHOT_1550': '15:50 모의 총자산 집계',
    'EXIT_0905': '09:05 손절·목표 점검', 'EXIT_0910': '09:10 남은 가상수량 청산'}
STATUS_KO = {
    'READY': '준비 완료. 이번 회차의 예약된 모의 단계를 진행합니다.',
    'RECONCILIATION_REQUIRED': '확인 필요: 서버·작업이 정리되지 않았거나 최종 보고 시점에 열린 가상 포지션이 남아 있습니다. '
        '다음 회차 신규 진입은 자동 중지(HALT)됩니다. 재실행하지 말고 status 명령으로 상태를 확인하세요.',
    'BLOCKED_OR_FAILED': '이 단계가 안전 검사로 차단되었거나 실패했습니다. 다음 회차 신규 진입은 자동 중지(HALT)되며, '
        '이미 있는 가상 포지션의 손절·청산과 서버 정리 예약은 계속 동작합니다. 재실행하지 말고 status 명령으로 확인하세요.'}
DECISION_KO = {
    'BUY': '가상매수 1건이 기록되었습니다. 다음 거래일 09:10 전후에 가상 청산합니다.',
    'NO_TRADE': '가상매수를 하지 않았습니다(NO_TRADE). 조건이 약하면 매수하지 않는 것이 정상 결과입니다.',
    'NO_RECORD': '판단 기록을 확인하지 못했습니다(기록 없음 또는 장부와 불일치). 매수 여부를 단정하지 않습니다.',
    'UNKNOWN': '판단 기록의 결과 값을 읽지 못했습니다. status로 확인이 필요합니다.'}
WORKER_KO = {'COMPLETED': '정상 종료', 'NO_RECORD': '실행 기록 없음',
    'BLOCKED_OR_FAILED': '차단 또는 실패', 'RUNNING': '종료 기록 없음(실행 중이었거나 중단됨)'}
DECISION_REASON_KO = {'NO_QUALIFYING_CANDIDATE': '종가배팅 기준을 충족한 종목 없음',
    'MARKET_DATA_UNAVAILABLE': '검증 가능한 시세 자료 없음', 'TOP_SCORE_SELECTED': '종합점수 1위 종목 선택'}
REASON_KO = {
    'BATCH_MANUALLY_STOPPED': '사용자가 stop 명령으로 운용을 중지했습니다.',
    'BATCH_NEW_ENTRIES_HALTED': '이전 단계 실패로 신규 진입이 이미 중지(HALT)된 상태입니다.',
    'BATCH_NOT_ARMED': '5회 운용 예약이 활성화(ARMED) 기록과 일치하지 않습니다.',
    'PREDECESSOR_MANUALLY_STOPPED': '직전 회차가 수동 중지되어 이번 회차를 시작하지 않았습니다.',
    'PREDECESSOR_BATCH_HALTED': '직전 운용이 신규 진입 중지(HALT) 상태로 끝나 이번 운용을 시작하지 않았습니다.',
    'UNSUPPORTED_PARENT_KIND': '직전 회차 지정 형식이 승인된 종류가 아닙니다.',
    'PREDECESSOR_OPERATOR_STOP_REQUIRED': '이어 시작할 직전 운용에 운영자 stop 기록이 없어 새 운용을 시작하지 않았습니다.',
    'PREDECESSOR_LATER_SESSION_STARTED': '직전 운용에서 지정 회차 이후 회차가 실행된 기록이 있어 새 운용을 시작하지 않았습니다.',
    'INVALID_STOPPED_SESSION_INDEX': '직전 운용에서 이어 붙일 회차 번호가 올바르지 않습니다.',
    'APPROVED_PAPER_SESSION_COUNT_REQUIRED': '운용 회차 수가 승인된 값(2회·3회·5회)이 아닙니다.',
    'OUTSIDE_APPROVED_SESSIONS': '승인된 회차 날짜에 해당하지 않는 예약이라 실행하지 않았습니다.',
    'PREDECESSOR_NOT_COMPLETED': '직전 회차의 단계가 모두 정상 완료되지 않았습니다.',
    'PREDECESSOR_TIME_INVALID': '직전 회차 단계의 실행 시각이 허용 범위를 벗어났습니다.',
    'PREDECESSOR_REAL_LEASE_NOT_VERIFIED': '직전 회차 작업의 실제 실행 기록을 확인하지 못했습니다.',
    'PREDECESSOR_DECISION_MISSING': '직전 회차의 15:20 판단 기록이 없습니다.',
    'PREDECESSOR_DECISION_LEDGER_DIFFERS': '직전 회차 판단 기록과 가상 장부가 다릅니다.',
    'PREDECESSOR_FINAL_REPORT_NOT_CLEAN': '직전 회차 최종 보고에 열린 포지션이나 미정리 서버가 있었습니다.',
    'LEDGER_CHANGED_AFTER_REPORT': '직전 회차 보고 뒤 가상 장부가 바뀌었습니다.',
    'UNRECONCILED_OPEN_OR_PENDING_STATE': '정리되지 않은 가상 포지션 또는 대기 상태가 남아 있습니다.',
    'ISOLATED_PAPER_WALLET_REQUIRED': '종가배팅 전용 모의 지갑을 하나로 확인하지 못했습니다.',
    'PAPER_WALLET_NOT_RECONCILED': '모의 지갑 금액이 예상 형식과 맞지 않습니다.',
    'PREVIOUS_CLEANUP_NOT_CURRENT': '이전 작업 뒤 서버가 꺼져 있지 않거나 실행 중 작업이 남아 있습니다.',
    'MORNING_PASS_NOT_VERIFIED': '사전 정상 시간 검증(PASS) 기록을 확인하지 못했습니다.',
    'MORNING_ATTEMPT_NOT_VERIFIED': '사전 검증 작업의 실행 기록을 확인하지 못했습니다.',
    'CALENDAR_CHANGED': '승인된 거래일 달력이 바뀌었습니다.',
    'STACK_NOT_STABLE': 'AWS 스택이 정상 완료 상태가 아닙니다.',
    'APP_CONFIGURATION_CHANGED': '앱 스택 설정값이 승인된 값과 다릅니다.',
    'REGULAR_SCHEDULE_NOT_DISABLED': '꺼져 있어야 할 정기 예약이 켜져 있습니다.',
    'PRODUCTION_TASK_CHANGED': '앱 작업 정의(이미지 등)가 승인 당시와 다릅니다.',
    'PILOT_ISOLATION_CHANGED': '모의운용 작업의 권한·자원 구성이 원본과 다릅니다.',
    'PAPER_CONTAINER_CHANGED': '모의운용 컨테이너 설정이 승인된 값과 다릅니다(모의 모드·실주문 OFF 확인 포함).',
    'PILOT_MANUALLY_STOPPED': '사용자가 stop 명령으로 운용을 중지했습니다.',
    'PILOT_NOT_READY': '09:45 준비 검사가 통과하지 않아 이후 단계를 진행하지 않았습니다.',
    'CONTROLLER_NOT_CONFIRMED': '서버 켜기·끄기 결과를 제어 기능에서 확인하지 못했습니다.',
    'EXISTING_TASK_PRESENT': '다른 작업이 이미 실행 중이라 중복 실행을 막았습니다.',
    'PREREQUISITE_NOT_COMPLETED': '앞 단계(14:50 스캔 또는 15:10 후보)가 정상 완료되지 않았습니다.',
    'EXISTING_POSITION_OR_PENDING_STATE': '이미 열린 가상 포지션이 있어 새 가상매수를 막았습니다.',
    'TASK_LAUNCH_NOT_CONFIRMED': '분석 작업 시작을 확인하지 못했습니다.',
    'TASK_INSPECTION_FAILED': '분석 작업 상태를 조회하지 못했습니다.',
    'TASK_BOUND_EXCEEDED': '분석 작업이 허용 시간 안에 끝나지 않아 중지했습니다.',
    'PAPER_WORKER_NOT_SUCCESSFUL': '분석 작업이 오류로 종료되었습니다.',
    'REAL_ATTEMPT_NOT_COMPLETED': '분석 작업의 완료 기록을 확인하지 못했습니다.',
    'LEDGER_SCAN_INCOMPLETE': '가상 장부 전체를 읽지 못했습니다.',
    'OUTSIDE_DISPATCH_WINDOW': '예약 허용 시각을 벗어나 실행하지 않았습니다.',
    'NOTIFICATION_REJECTED': '텔레그램 전송이 거부되었습니다.'}


def explain(message, session=None, decision_reason=None):
    """Return Korean lines for a controller message without changing it."""
    lines = ['[쉬운 설명] 실제 계좌 주문 없는 모의운용 알림입니다.']
    if session:
        lines.append('회차: %d/%d (진입일 %s)' % session)
    phase = next((name for name in re.findall('[A-Z][A-Z0-9_]+', message) if name in PHASE_KO), None)
    if phase:
        lines.append('단계: ' + PHASE_KO[phase])
    values = dict(re.findall(r'(\w+)=([A-Z0-9_]+)', message))
    if 'decision' in values:
        lines.append('판단: ' + DECISION_KO.get(values['decision'], values['decision']))
        if decision_reason:
            lines.append('판단 사유: ' + decision_reason)
    if 'entry_worker' in values:
        lines.append('15:20 판단 작업: ' + WORKER_KO.get(values['entry_worker'], values['entry_worker']))
    if 'exit_worker' in values:
        worker = values['exit_worker']
        if phase == 'REPORT_PM' and worker == 'NO_RECORD':
            lines.append('09:10 청산 작업: 다음 거래일 오전 예정이라 아직 기록이 없는 것이 정상입니다.')
        else:
            lines.append('09:10 청산 작업: ' + WORKER_KO.get(worker, worker))
    if 'open_positions' in values:
        count = int(values['open_positions'])
        lines.append('열린 가상 포지션: ' + ('없음' if not count else '%d개' % count))
    for status, text in STATUS_KO.items():
        if re.search(r'\b' + status + r'\b', message):
            lines.append('상태: ' + text)
            break
    failed = re.search(r'BLOCKED_OR_FAILED\. ([A-Za-z0-9_]+)', message)
    if failed:
        code = failed.group(1)
        lines.append('원인: ' + REASON_KO.get(code, code + ' (AWS 호출 또는 미분류 오류. status와 로그로 확인 필요)'))
    return '\n'.join(lines)


def session_plan(batch, index):
    result = copy.deepcopy(batch['template'])
    entry, exit_day = batch['sessions'][index]['entry_date'], batch['sessions'][index]['exit_date']
    result.update(entry_date=entry, exit_date=exit_day,
                  decision_key='runs/' + entry.replace('-', '/') + '/KRX_1520/decision.json', events={})
    times = {'GATE': (9, 45), 'START_PM': (14, 40), 'STOP_PM': (16, 10),
             'REPORT_PM': (16, 15), 'START_AM': (8, 55), 'STOP_AM': (9, 25), 'REPORT_AM': (9, 40)}
    def at(day, hm):
        return datetime.fromisoformat(day + 'T%02d:%02d:00+09:00' % hm).astimezone(timezone.utc)
    for name, hm in times.items():
        result['events'][name] = {'dispatch_at': at(exit_day if name.endswith('_AM') else entry, hm).isoformat()}
    for name, hm in p.PHASE_TIMES.items():
        occurrence = at(exit_day if name.startswith('EXIT_') else entry, hm)
        result['events'][name] = {'scheduled_at': occurrence.isoformat(),
            'dispatch_at': (occurrence-timedelta(minutes=2 if name == 'EXIT_0910' else 3)).isoformat()}
    return result


def validate_batch(batch):
    try:
        # The batch and every session it builds carry one approved capital pair.
        approved = p.capital(batch) == p.capital(batch.get('template', {}))
    except ValueError:
        approved = False
    if (batch.get('paper_only') is not True or not approved
            or len(batch.get('sessions', [])) not in ALLOWED_SESSION_COUNTS
            or not re.fullmatch('[a-f0-9]{32}', batch.get('batch_id', ''))):
        raise ValueError('APPROVED_PAPER_SESSION_COUNT_REQUIRED')
    reference = parent_reference(batch)
    parent = reference['plan']
    if batch['batch_id'] in reference['ids']:
        raise ValueError('NONCONTIGUOUS_OR_DUPLICATE_SESSION')
    previous = parent['exit_date']
    ids = reference['ids'] | {batch['batch_id']}
    for index, slot in enumerate(batch['sessions']):
        # Only a restart after an operator-stopped batch may leave a gap, and
        # then only forward: never the same day as the stopped session's exit.
        if index == 0 and reference['allow_later_start']:
            ordered = slot['entry_date'] > previous
        else:
            ordered = slot['entry_date'] == previous
        if not ordered or slot['pilot_id'] in ids or not re.fullmatch('[a-f0-9]{32}', slot['pilot_id']):
            raise ValueError('NONCONTIGUOUS_OR_DUPLICATE_SESSION')
        ids.add(slot['pilot_id'])
        plan = session_plan(batch, index)
        p.validate_calendar(plan)
        previous = slot['exit_date']
    if batch['template']['approved_calendar'] != parent['approved_calendar']:
        raise ValueError('CALENDAR_IDENTITY_CHANGED')


def parent_reference(batch):
    """Describe the completed run the first session must follow.

    `pilot` (default) is the original one-session pilot. `batch_session` is the
    last session of an earlier approved batch whose full immutable plan is
    embedded, so the same completion, ledger digest and cleanup checks apply.
    `stopped_batch_session` restarts after an operator `stop`: it follows the
    named fully completed session of that batch. The batch-level STOP is then
    required instead of rejected, later sessions must not have launched, and a
    HALT is tolerated only when the stop fence itself caused it.
    """
    parent = batch['parent']
    kind = parent.get('kind', 'pilot')
    if kind == 'pilot':
        plan = parent['plan']
        p.validate_plan(plan)
        p.validate_calendar(plan)
        return {'session_prefix': parent['prefix'], 'pilot_id': parent['pilot_id'], 'plan': plan,
                'stored_plan': plan, 'armed_key': parent['prefix'] + '/ARMED.json',
                'fence_keys': [parent['prefix'] + '/STOP.json'], 'halt_key': None,
                'require_digest': False, 'ids': {parent['pilot_id']},
                'required_stop_key': None, 'later_prefixes': [], 'allow_later_start': False}
    if kind not in ('batch_session', 'stopped_batch_session'):
        raise ValueError('UNSUPPORTED_PARENT_KIND')
    previous = parent['batch_plan']
    validate_batch(previous)
    root = parent['prefix']
    if kind == 'batch_session':
        index = len(previous['sessions']) - 1
    else:
        index = parent.get('session_index')
        if type(index) is not int or not 0 <= index < len(previous['sessions']):
            raise ValueError('INVALID_STOPPED_SESSION_INDEX')
    slot = previous['sessions'][index]
    session_prefix = root + '/sessions/' + slot['entry_date']
    ids = parent_reference(previous)['ids'] | {previous['batch_id']} | {s['pilot_id'] for s in previous['sessions']}
    stopped = kind == 'stopped_batch_session'
    return {'session_prefix': session_prefix, 'pilot_id': slot['pilot_id'],
            'plan': session_plan(previous, index), 'stored_plan': previous, 'armed_key': root + '/ARMED.json',
            'fence_keys': ([] if stopped else [root + '/STOP.json']) + [session_prefix + '/STOP.json'],
            'halt_key': root + '/HALT.json', 'require_digest': True, 'ids': ids,
            'required_stop_key': root + '/STOP.json' if stopped else None,
            'later_prefixes': [root + '/sessions/' + s['entry_date'] for s in previous['sessions'][index+1:]] if stopped else [],
            'allow_later_start': stopped}


class DatedECS:
    """Add only the two plan-approved dates; preserve original launch guards."""
    def __init__(self, client, plan):
        self.client, self.plan = client, plan

    def __getattr__(self, name):
        return getattr(self.client, name)

    def run_task(self, **kwargs):
        values = kwargs['overrides']['containerOverrides'][0]['environment']
        if any(x['name'] in ('PILOT_ENTRY_DATE', 'PILOT_EXIT_DATE') for x in values):
            raise ValueError('DUPLICATE_DATE_OVERRIDE')
        values.extend([{'name': 'PILOT_ENTRY_DATE', 'value': self.plan['entry_date']},
                       {'name': 'PILOT_EXIT_DATE', 'value': self.plan['exit_date']}])
        return self.client.run_task(**kwargs)


class Batch(p.Pilot):
    def root_key(self, name):
        return self.root_prefix + '/' + name + '.json'

    def save_root(self, name, value, create=False):
        args = {'Bucket': self.env['PAPER_BUCKET'], 'Key': self.root_key(name),
                'Body': json.dumps(value).encode(), 'ContentType': 'application/json'}
        if create:
            args['IfNoneMatch'] = '*'
        self.clients['s3'].put_object(**args)

    def load(self):
        raw = self.clients['s3'].get_object(Bucket=self.env['PAPER_BUCKET'], Key=self.env['PLAN_KEY'])['Body'].read()
        if hashlib.sha256(raw).hexdigest() != self.env['PLAN_SHA256']:
            raise ValueError('BATCH_PLAN_HASH_MISMATCH')
        batch = json.loads(raw)
        validate_batch(batch)
        if batch['batch_id'] != self.env['PILOT_ID']:
            raise ValueError('WRONG_BATCH_ID')
        self.batch = batch
        self.root_prefix = self.env['RESULT_PREFIX']
        return batch

    def configuration(self, plan):
        # The registered task's two default dates remain the first session's.
        # RunTask supplies the approved current pair explicitly, without changing
        # command, image, secrets, phase clock, or runtime limits.
        review = copy.deepcopy(plan)
        review.update(entry_date=self.batch['sessions'][0]['entry_date'],
                      exit_date=self.batch['sessions'][0]['exit_date'])
        super().configuration(review)

    def idle(self):
        vm = self.clients['ec2'].describe_instances(InstanceIds=[self.env['NAT_INSTANCE_ID']])['Reservations'][0]['Instances'][0]
        cluster = self.clients['ecs'].describe_clusters(clusters=[self.env['CLUSTER_ARN']])['clusters'][0]
        if vm['State']['Name'] != 'stopped' or cluster['runningTasksCount'] or cluster['pendingTasksCount']:
            raise ValueError('PREVIOUS_CLEANUP_NOT_CURRENT')

    def halted(self):
        if self.get(self.root_key('STOP'), optional=True) is not None:
            raise ValueError('BATCH_MANUALLY_STOPPED')
        if self.get(self.root_key('HALT'), optional=True) is not None:
            raise ValueError('BATCH_NEW_ENTRIES_HALTED')

    def wallet(self, plan, *, allow_uncreated=False):
        """Check the one closing-bet wallet of ``plan``'s capital (cash and epoch)."""
        rows = self.rows()
        if any(r['pk']['S'].startswith(('OPEN#', 'PENDING#')) for r in rows):
            raise ValueError('UNRECONCILED_OPEN_OR_PENDING_STATE')
        cash, epoch = p.capital(plan)
        wallets = [r for r in rows if r['pk']['S'].startswith('WALLET#')]
        if epoch:
            # Wallets of an earlier capital are kept as history and not checked here.
            wallets = [r for r in wallets if r['pk']['S'].endswith('#' + epoch)]
        if not wallets and allow_uncreated:
            return rows
        expected = 'WALLET#CLOSING_BET#KRX_1520' + ('#' + epoch if epoch else '')
        if len(wallets) != 1 or wallets[0]['pk']['S'] != expected:
            raise ValueError('ISOLATED_PAPER_WALLET_REQUIRED')
        wallet = wallets[0]
        if (wallet.get('initial_cash') != {'N': cash} or wallet.get('invested_principal') != {'N': '0'}
                or not re.fullmatch('[0-9]+', wallet.get('available_cash', {}).get('N', ''))):
            raise ValueError('PAPER_WALLET_NOT_RECONCILED')
        # Preserve cash and realized results. Never reset it to the initial sum.
        return rows

    def ledger_digest(self, rows):
        return p.digest([r for r in rows if not r['pk']['S'].startswith(('CONTROL#NETWORK#', 'CONTROL#ALERT'))])

    def completed(self, prefix, pilot_id, plan, require_digest=False):
        if self.get(prefix+'/STOP.json', optional=True) is not None:
            raise ValueError('PREDECESSOR_MANUALLY_STOPPED')
        reports = {}
        for name, expected in EXPECTED.items():
            marker = self.get(prefix+'/'+name+'.json', optional=True) or {}
            at = p.stamp(plan['events'][name]['dispatch_at'])
            if marker.get('status') != expected or marker.get('pilot_id') != pilot_id:
                raise ValueError('PREDECESSOR_NOT_COMPLETED')
            if not at <= p.stamp(marker['started_at']) <= p.stamp(marker['finished_at']) <= min(self.clock(), at+timedelta(seconds=900)):
                raise ValueError('PREDECESSOR_TIME_INVALID')
            reports[name] = marker
        for name, (late, duration) in LIMITS.items():
            at = p.stamp(plan['events'][name]['scheduled_at'])
            key = 'CONTROL#RUN#'+name+'#'+at.astimezone(timezone.utc).isoformat()
            lease = self.clients['dynamodb'].get_item(TableName=self.env['PAPER_TABLE'],
                Key={'pk': {'S': key}}, ConsistentRead=True).get('Item', {})
            if (lease.get('status') != {'S': 'COMPLETED'}
                    or not re.fullmatch('[a-f0-9]{32}', lease.get('owner', {}).get('S', ''))
                    or not at <= p.stamp(lease['started_at']['S']) <= at+timedelta(seconds=late)
                    or not p.stamp(lease['started_at']['S']) <= p.stamp(lease['finished_at']['S']) <= at+timedelta(seconds=late+duration+10)):
                raise ValueError('PREDECESSOR_REAL_LEASE_NOT_VERIFIED')
        artifact = self.get(plan['decision_key'])
        if artifact.get('decision') not in ('BUY', 'NO_TRADE') or not artifact.get('idempotency_key'):
            raise ValueError('PREDECESSOR_DECISION_MISSING')
        record = self.clients['dynamodb'].get_item(TableName=self.env['PAPER_TABLE'],
            Key={'pk': {'S': artifact['idempotency_key']}}, ConsistentRead=True).get('Item', {})
        if json.loads(record.get('payload_json', {}).get('S', '{}')) != artifact:
            raise ValueError('PREDECESSOR_DECISION_LEDGER_DIFFERS')
        detail = reports['REPORT_AM'].get('report', {})
        if detail.get('decision') != artifact['decision'] or detail.get('open_positions') != 0 or detail.get('network_stopped_and_idle') is not True:
            raise ValueError('PREDECESSOR_FINAL_REPORT_NOT_CLEAN')
        # The predecessor's own capital: the first 200,000 KRW session follows a
        # 600,000 KRW run whose original wallet must still be clean.
        rows = self.wallet(plan, allow_uncreated=reports['REPORT_AM'].get('report', {}).get('decision') == 'NO_TRADE')
        if require_digest and reports['REPORT_AM'].get('ledger_digest') != self.ledger_digest(rows):
            raise ValueError('LEDGER_CHANGED_AFTER_REPORT')
        self.idle()

    def parent_fences_clear(self, reference):
        if any(self.get(key, optional=True) is not None for key in reference['fence_keys']):
            raise ValueError('PREDECESSOR_MANUALLY_STOPPED')
        halt = self.get(reference['halt_key'], optional=True) if reference['halt_key'] else None
        if reference['required_stop_key'] is None:
            if halt is not None:
                raise ValueError('PREDECESSOR_BATCH_HALTED')
            return
        stop = self.get(reference['required_stop_key'], optional=True) or {}
        if stop.get('status') != 'STOPPED_BY_OPERATOR' or not stop.get('at'):
            raise ValueError('PREDECESSOR_OPERATOR_STOP_REQUIRED')
        # A schedule that fired between the STOP marker and its disabling halts
        # with this exact reason; any other HALT is a real failure.
        if halt is not None and (halt.get('reason') != 'BATCH_MANUALLY_STOPPED' or not halt.get('at')
                                 or p.stamp(halt['at']) < p.stamp(stop['at'])):
            raise ValueError('PREDECESSOR_BATCH_HALTED')
        for prefix in reference['later_prefixes']:
            for name in LAUNCH_PHASES:
                marker = self.get(prefix + '/' + name + '.json', optional=True)
                if marker is not None and (marker.get('status') != 'BLOCKED_OR_FAILED'
                                           or marker.get('reason') != 'BATCH_MANUALLY_STOPPED'):
                    raise ValueError('PREDECESSOR_LATER_SESSION_STARTED')

    def predecessor(self, index):
        if index == 0:
            reference = parent_reference(self.batch)
            self.parent_fences_clear(reference)
            return (reference['session_prefix'], reference['pilot_id'], reference['plan'],
                    reference['require_digest'])
        slot = self.batch['sessions'][index-1]
        return (self.root_prefix+'/sessions/'+slot['entry_date'], slot['pilot_id'],
                session_plan(self.batch, index-1), True)

    def gate(self, plan):
        self.halted()
        armed = self.get(self.root_key('ARMED'))
        if armed.get('status') != 'ARMED' or armed.get('plan_sha256') != self.env['PLAN_SHA256']:
            raise ValueError('BATCH_NOT_ARMED')
        self.proof(plan)
        self.configuration(plan)
        self.completed(*self.predecessor(self.index))
        self.save('ready', {'status': 'READY', 'pilot_id': self.env['PILOT_ID'],
            'plan_sha256': self.env['PLAN_SHA256'], 'checked_at': self.clock().isoformat()}, create=True)
        return 'READY'

    def require_ready(self, plan):
        # A phase failure halts new entry but does not suppress the scheduled
        # risk review/exit for an already-created virtual position. Manual STOP
        # fences all launches; cleanup and reports remain independently callable.
        if self.action not in ('START_AM', 'EXIT_0905', 'EXIT_0910'):
            self.halted()
        elif self.get(self.root_key('STOP'), optional=True) is not None:
            raise ValueError('BATCH_MANUALLY_STOPPED')
        super().require_ready(plan)

    def decision_reason(self):
        # Best effort only: a failed read must never fail a report or a gate.
        try:
            artifact = self.get(self.current_plan['decision_key'], optional=True) or {}
            codes = [DECISION_REASON_KO.get(c, c) for c in artifact.get('reason_codes', []) if isinstance(c, str)]
            notes = artifact.get('notes')
            text = ', '.join(codes)
            if isinstance(notes, str) and notes and not notes.isascii():
                text += (' — ' if text else '') + notes[:200]
            return text or None
        except Exception:
            return None

    def notify(self, message):
        # An explanation error must not turn a clean report into a failure/HALT.
        try:
            index = getattr(self, 'index', None)
            sessions = self.batch['sessions']
            session = None if index is None else (index + 1, len(sessions), sessions[index]['entry_date'])
            reason = self.decision_reason() if re.search(r'decision=(BUY|NO_TRADE)\b', message) else None
            text = message + '\n\n' + explain(message, session, reason)
        except Exception:
            text = message
        super().notify(text)

    def run(self, name, item, plan):
        original = self.clients['ecs']
        self.clients['ecs'] = DatedECS(original, plan)
        try:
            return super().run(name, item, plan)
        finally:
            self.clients['ecs'] = original

    def handle(self, event):
        batch = self.load()
        if event == {'action': 'DEPLOYMENT_CHECK', 'batch_id': batch['batch_id']}:
            if self.clock() >= p.stamp(session_plan(batch, 0)['events']['GATE']['dispatch_at']):
                raise ValueError('DEPLOYMENT_REVIEW_WINDOW_CLOSED')
            self.halted()
            plan = session_plan(batch, 0)
            self.configuration(plan)
            self.proof(plan)
            self.rows()
            self.idle()
            self.get(self.root_key('ARMED'), optional=True)
            parent = batch['parent']
            reference = parent_reference(batch)
            self.parent_fences_clear(reference)
            raw = self.clients['s3'].get_object(Bucket=self.env['PAPER_BUCKET'], Key=parent['plan_key'])['Body'].read()
            if hashlib.sha256(raw).hexdigest() != parent['plan_sha256'] or json.loads(raw) != reference['stored_plan']:
                raise ValueError('PARENT_IMMUTABLE_PLAN_CHANGED')
            if (self.get(reference['armed_key']) or {}).get('plan_sha256') != parent['plan_sha256']:
                raise ValueError('PARENT_NOT_ARMED')
            self.get(reference['session_prefix']+'/REPORT_AM.json', optional=True)
            return {'status': 'DEPLOYMENT_VERIFIED', 'paper_only': True, 'mutations': False,
                    'predecessor_success': 'PENDING_REAL_EXECUTION'}
        if set(event) != {'action', 'batch_id', 'scheduled_at'} or event['batch_id'] != batch['batch_id'] or event['action'] not in EXPECTED:
            raise ValueError('WRONG_BATCH_EVENT')
        name = event['action']
        occurrence = p.stamp(event['scheduled_at'])
        matches = [(i, session_plan(batch, i)) for i in range(len(batch['sessions']))
            if p.stamp(session_plan(batch, i)['events'][name]['dispatch_at']) == occurrence]
        if len(matches) != 1:
            raise ValueError('OUTSIDE_APPROVED_SESSIONS')
        if not occurrence <= self.clock() <= occurrence+timedelta(seconds=60):
            raise ValueError('OUTSIDE_DISPATCH_WINDOW')
        self.index, plan = matches[0]
        self.current_plan = plan
        self.action = name
        slot = batch['sessions'][self.index]
        self.env = dict(self.env, PILOT_ID=slot['pilot_id'],
                        RESULT_PREFIX=self.root_prefix+'/sessions/'+slot['entry_date'])
        if self.get(self.key(name), optional=True) is not None:
            return {'status': 'ALREADY_ATTEMPTED', 'phase': name}
        state = {'status': 'RUNNING', 'pilot_id': slot['pilot_id'], 'started_at': self.clock().isoformat()}
        self.save(name, state, create=True)
        try:
            if name == 'GATE':
                status = self.gate(plan)
            elif name.startswith('REPORT_'):
                status = self.report(name, plan)
                state['report'] = self.report_detail
                if name == 'REPORT_AM' and status == 'REPORTED':
                    self.wallet(plan)
                    state['ledger_digest'] = self.ledger_digest(self.rows())
            elif name.startswith('STOP_'):
                status = 'NO_OWN_START' if self.get(self.key('START_'+name[-2:]), optional=True) is None else self.controller(
                    'STOP', 'morning' if name.endswith('_AM') else 'afternoon', plan['events'][name]['dispatch_at'])
            else:
                self.require_ready(plan)
                status = self.controller('START', 'morning' if name.endswith('_AM') else 'afternoon', plan['events'][name]['dispatch_at']) if name.startswith('START_') else self.run(name, plan['events'][name], plan)
            state['status'] = status
            if status == 'RECONCILIATION_REQUIRED':
                self.save_root('HALT', {'status': 'NEW_ENTRIES_HALTED', 'phase': name, 'at': self.clock().isoformat()}, create=True)
        except Exception as error:
            reason = str(error) if isinstance(error, ValueError) and re.fullmatch('[A-Z0-9_]+', str(error)) else type(error).__name__
            state.update(status='BLOCKED_OR_FAILED', reason=reason)
            if self.get(self.root_key('HALT'), optional=True) is None:
                self.save_root('HALT', {'status': 'NEW_ENTRIES_HALTED', 'phase': name, 'reason': reason,
                    'at': self.clock().isoformat()}, create=True)
        state['finished_at'] = self.clock().isoformat()
        self.save(name, state)
        if name == 'GATE' or state['status'] in ('BLOCKED_OR_FAILED', 'RECONCILIATION_REQUIRED'):
            try:
                self.notify(slot['entry_date']+' '+name+': '+state['status']+'. '+state.get(
                    'reason', 'Bounded %d-session paper batch.' % len(batch['sessions'])))
            except Exception:
                pass
        return {'status': state['status'], 'phase': name, 'entry_date': slot['entry_date']}


def handler(event, context):
    import boto3
    from botocore.config import Config
    try:
        clients = {name: boto3.client(name, config=Config(connect_timeout=3,
            read_timeout=230 if name == 'lambda' else 8, retries={'max_attempts': 0 if name == 'lambda' else 1}))
            for name in ('s3', 'ec2', 'ecs', 'dynamodb', 'cloudformation', 'lambda', 'scheduler', 'secretsmanager')}
        result = Batch(clients, os.environ).handle(event)
    except Exception as error:
        result = {'status': 'BATCH_REJECTED_OR_FAILED'}
        for key, value in (('error_code', getattr(error, 'response', {}).get('Error', {}).get('Code', type(error).__name__)),
                           ('operation', getattr(error, 'operation_name', ''))):
            if isinstance(value, str) and re.fullmatch('[A-Za-z0-9_]+', value):
                result[key] = value
        if isinstance(error, ValueError) and re.fullmatch('[A-Z0-9_]+', str(error)):
            result['reason'] = str(error)
    print(json.dumps(result))
    return result
