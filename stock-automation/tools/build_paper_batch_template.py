"""Build fifteen disabled, date-bounded schedules for five paper sessions."""
import argparse
import base64
import importlib.util
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def packed_source():
    sources = {name: (ROOT/'infra'/f'{name}.py').read_text(encoding='utf-8')
               for name in ('paper_pilot', 'paper_batch')}
    raw = json.dumps(sources, sort_keys=True, separators=(',', ':')).encode()
    encoded = base64.b64encode(zlib.compress(raw, 9)).decode()
    return ('# Canonical sources: infra/paper_pilot.py and infra/paper_batch.py.\n'
        'import base64,json,sys,types,zlib\nSOURCES_ZLIB_BASE64='+repr(encoded)+'\n'
        '_sources=json.loads(zlib.decompress(base64.b64decode(SOURCES_ZLIB_BASE64)))\n'
        '_base=types.ModuleType("paper_pilot");sys.modules["paper_pilot"]=_base\n'
        'exec(compile(_sources["paper_pilot"],"paper_pilot.py","exec"),_base.__dict__)\n'
        'exec(compile(_sources["paper_batch"],"paper_batch.py","exec"))\n')


def build():
    spec = importlib.util.spec_from_file_location('batch_template_base', ROOT/'tools/build_paper_pilot_template.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    # Change only the new stack's identity; the existing pilot is not modified.
    body = json.dumps(base.build()).replace('stock-paper-pilot', 'stock-paper-batch').replace(
        'stock-automation-paper-pilot', 'stock-automation-paper-batch').replace('StockPaperPilot', 'StockPaperBatch').replace(
        'validation/pilot/${PilotId}', 'validation/batch/${PilotId}')
    template = json.loads(body)
    parameters, resources = template['Parameters'], template['Resources']
    for name in list(parameters):
        if name.endswith('ScheduleAt'):
            del parameters[name]
    for name in ('ParentPrefix', 'ParentPlanKey'):
        parameters[name] = {'Type': 'String'}
    for name in ('PmStart', 'PmEnd', 'AmStart', 'AmEnd'):
        parameters[name] = {'Type': 'String', 'AllowedPattern':
            r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z'}
    resources['Pilot']['Properties']['Code']['ZipFile'] = packed_source()
    resources['Pilot']['Properties']['Description'] = 'Five dated paper sessions; predecessor gate, permanent failure halt, no real orders'
    resources['PilotRole']['Properties']['Policies'][0]['PolicyName'] = 'five-dated-paper-sessions'
    for name, resource in resources.items():
        if resource['Type'] != 'AWS::Scheduler::Schedule':
            continue
        prop = resource['Properties']
        phase = prop['Name'].removeprefix('stock-paper-batch-').upper().replace('-', '_')
        times = {'GATE': (9, 45), 'START_PM': (14, 40), 'STOP_PM': (16, 10), 'REPORT_PM': (16, 15),
                 'START_AM': (8, 55), 'STOP_AM': (9, 25), 'REPORT_AM': (9, 40),
                 'FALLBACK_PM': (16, 20), 'FALLBACK_AM': (9, 35),
                 'SCAN_1450': (14, 47), 'SHORTLIST_1510': (15, 7), 'ENTRY_1520': (15, 17),
                 'EQUITY_SNAPSHOT_1550': (15, 47), 'EXIT_0905': (9, 2), 'EXIT_0910': (9, 8)}
        hour, minute = times[phase]
        window = 'Am' if phase.endswith('_AM') or phase.startswith('EXIT_') else 'Pm'
        prop.update(ScheduleExpression=f'cron({minute} {hour} ? * MON-FRI *)',
                    ScheduleExpressionTimezone='Asia/Seoul', StartDate={'Ref': window+'Start'}, EndDate={'Ref': window+'End'})
        if not phase.startswith('FALLBACK_'):
            prop['Target']['Input'] = {'Fn::Sub': '{"action":"'+phase+'","batch_id":"${PilotId}","scheduled_at":"<aws.scheduler.scheduled-time>"}'}
    def sub(text):
        return {'Fn::Sub': text}
    for policy in (resources['Boundary']['Properties']['PolicyDocument'],
                   resources['PilotRole']['Properties']['Policies'][0]['PolicyDocument']):
        for statement in policy['Statement']:
            if statement['Action'] == ['s3:ListBucket']:
                statement['Condition']['StringLike']['s3:prefix'].append(sub('${ParentPrefix}/*'))
            if statement['Action'] == ['s3:GetObject']:
                statement['Resource'].extend([
                    sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/${ParentPrefix}/*'),
                    sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/${ParentPlanKey}')])
    # The existing operator already has ten managed policies attached. Do not
    # create another user-attached policy here; extend the existing pilot review
    # policy separately if local operator access is needed.
    resources.pop('OperatorReviewPolicy')
    parameters.pop('OperatorUserName', None)
    template['Description'] = 'Five date-bounded paper sessions only after verified prior completion; no live orders or regular schedule changes'
    return template


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Preserve existing output')
    args.output.write_text(json.dumps(build(), indent=2)+'\n', encoding='utf-8')
    print('FIVE_SESSION_BATCH_TEMPLATE_BUILT; disabled; no AWS calls')
