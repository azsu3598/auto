"""Build a disabled one-session paper pilot; never change regular schedules."""
import argparse
import base64
import copy
import importlib.util
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inline_source():
    # CloudFormation's inline body limit includes parameters and IAM policies.
    # This is deterministic packaging of the reviewed plaintext repository file;
    # deployment verification compares both wrapper and canonical source hashes.
    source=(ROOT/'infra/paper_pilot.py').read_text(encoding='utf-8').encode()
    encoded=base64.b64encode(zlib.compress(source,9)).decode('ascii')
    return ('# Canonical source: infra/paper_pilot.py; deterministic inline packaging.\n'
        'import base64, zlib\nSOURCE_ZLIB_BASE64 = '+repr(encoded)+'\n'
        'exec(compile(zlib.decompress(base64.b64decode(SOURCE_ZLIB_BASE64)), "paper_pilot.py", "exec"))\n')


def build():
    spec = importlib.util.spec_from_file_location('worker_template_base', ROOT/'tools/build_worker_verification_template.py')
    base = importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
    original = base.build()
    def ref(name): return {'Ref': name}
    def sub(value): return {'Fn::Sub': value}
    def arn(name): return {'Fn::GetAtt': [name, 'Arn']}
    def trust(service):
        statement = {'Effect': 'Allow', 'Principal': {'Service': service}, 'Action': 'sts:AssumeRole'}
        if service == 'scheduler.amazonaws.com':
            statement['Condition'] = {'StringEquals': {'aws:SourceAccount': ref('AWS::AccountId')},
                'ArnLike': {'aws:SourceArn': sub('arn:${AWS::Partition}:scheduler:${AWS::Region}:${AWS::AccountId}:schedule-group/default')}}
        return {'Version': '2012-10-17', 'Statement': [statement]}
    parameters = copy.deepcopy(original['Parameters'])
    for name in ('TestId', 'StartAt', 'DispatchAt', 'RunAt', 'WatchAt', 'FailSafeAt', 'VerificationState', 'ProductionTaskDefinitionArn'):
        parameters.pop(name)
    for name in ('PilotId', 'PlanKey', 'PlanSha256', 'MorningResultKey', 'EntryDate', 'ExitDate', 'DecisionKey'):
        parameters[name] = {'Type': 'String'}
    parameters['PilotId']['AllowedPattern'] = '[a-f0-9]{32}'
    parameters['PlanSha256']['AllowedPattern'] = '[a-f0-9]{64}'
    parameters['PilotState'] = {'Type': 'String', 'Default': 'DISABLED', 'AllowedValues': ['DISABLED', 'ENABLED']}
    parameters['RegularScheduleArns'] = {'Type': 'CommaDelimitedList'}
    task = copy.deepcopy(original['Resources']['ValidationTask'])
    task['Properties']['Family'] = 'stock-automation-paper-pilot'
    container = task['Properties']['ContainerDefinitions'][0]
    container['Command'] = ['-c', (ROOT/'infra/paper_pilot_bootstrap.py').read_text(encoding='utf-8')]
    container['Environment'].extend([{'Name': 'PILOT_ENTRY_DATE', 'Value': ref('EntryDate')},
        {'Name': 'PILOT_EXIT_DATE', 'Value': ref('ExitDate')}])
    host = sub('arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${NatInstanceId}')
    stop = {'Effect': 'Allow', 'Action': ['ec2:StopInstances'], 'Resource': host,
        'Condition': {'StringEquals': {'ec2:ResourceTag/Project': 'paper-fixed-egress',
            'ec2:ResourceTag/Name': 'stock-automation-paper-nat', 'aws:RequestedRegion': 'ap-northeast-2'}}}
    result = sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/validation/pilot/${PilotId}/*')
    log = sub('arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/stock-paper-pilot:*')
    policy = {'Version': '2012-10-17', 'Statement': [
        {'Effect': 'Allow', 'Action': ['ecs:RunTask'], 'Resource': ref('PilotTask'),
            'Condition': {'ArnEquals': {'ecs:cluster': ref('ClusterArn')}}},
        {'Effect': 'Allow', 'Action': ['iam:PassRole'], 'Resource': [ref('TaskExecutionRoleArn'), ref('TaskRoleArn')],
            'Condition': {'StringEquals': {'iam:PassedToService': 'ecs-tasks.amazonaws.com'}}},
        {'Effect': 'Allow', 'Action': ['ecs:DescribeClusters'], 'Resource': ref('ClusterArn')},
        {'Effect': 'Allow', 'Action': ['ecs:DescribeTasks', 'ecs:StopTask'],
            'Resource': sub('arn:${AWS::Partition}:ecs:${AWS::Region}:${AWS::AccountId}:task/stock-automation-paper/*')},
        {'Effect': 'Allow', 'Action': ['ecs:DescribeTaskDefinition', 'ec2:DescribeInstances'], 'Resource': '*',
            'Condition': {'StringEquals': {'aws:RequestedRegion': 'ap-northeast-2'}}},
        {'Effect': 'Allow', 'Action': ['cloudformation:DescribeStacks'], 'Resource': [
            sub('arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/' + name + '/*')
            for name in ('stock-automation-paper', 'stock-automation-paper-control', 'stock-automation-paper-network')]},
        {'Effect': 'Allow', 'Action': ['scheduler:GetSchedule'], 'Resource': ref('RegularScheduleArns')},
        {'Effect': 'Allow', 'Action': ['lambda:InvokeFunction'], 'Resource': ref('ControlFunctionArn')},
        {'Effect': 'Allow', 'Action': ['dynamodb:GetItem', 'dynamodb:Scan'],
            'Resource': sub('arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/stock-automation-paper')},
        {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject'], 'Resource': result},
        {'Effect': 'Allow', 'Action': ['s3:ListBucket'],
            'Resource': sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}'),
            'Condition': {'StringLike': {'s3:prefix': [sub('validation/pilot/${PilotId}/*'), ref('DecisionKey')]}}},
        {'Effect': 'Allow', 'Action': ['s3:GetObject'], 'Resource': [
            sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/${PlanKey}'),
            sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/${DecisionKey}'),
            sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/config/calendar/current.json'),
            sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/${MorningResultKey}')]},
        {'Effect': 'Allow', 'Action': ['secretsmanager:GetSecretValue'], 'Resource': ref('TelegramSecretArn')},
        {'Effect': 'Allow', 'Action': ['logs:CreateLogStream', 'logs:PutLogEvents'], 'Resource': log}]}
    resources = {
        'PilotTask': task,
        'Boundary': {'Type': 'AWS::IAM::ManagedPolicy', 'Properties': {
            'ManagedPolicyName': 'StockPaperPilotBoundary', 'PolicyDocument': policy}},
        'PilotRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'RoleName': 'stock-paper-pilot', 'Path': '/stock-paper/', 'PermissionsBoundary': ref('Boundary'),
            'AssumeRolePolicyDocument': trust('lambda.amazonaws.com'),
            'Policies': [{'PolicyName': 'one-dated-paper-session', 'PolicyDocument': policy}]}},
        'LogGroup': {'Type': 'AWS::Logs::LogGroup', 'Properties': {'LogGroupName': '/aws/lambda/stock-paper-pilot', 'RetentionInDays': 7}},
        'Pilot': {'Type': 'AWS::Lambda::Function', 'DependsOn': 'LogGroup', 'Properties': {
            'FunctionName': 'stock-paper-pilot', 'Runtime': 'python3.13', 'Handler': 'index.handler',
            'MemorySize': 128, 'Timeout': 900, 'ReservedConcurrentExecutions': 2, 'Role': arn('PilotRole'),
            'Code': {'ZipFile': inline_source()},
            'Environment': {'Variables': {
                'PAPER_BUCKET': ref('ArtifactBucketName'), 'PAPER_TABLE': 'stock-automation-paper', 'PILOT_ID': ref('PilotId'),
                'PLAN_KEY': ref('PlanKey'), 'PLAN_SHA256': ref('PlanSha256'),
                'RESULT_PREFIX': sub('validation/pilot/${PilotId}'), 'NAT_INSTANCE_ID': ref('NatInstanceId'),
                'TASK_DEFINITION_ARN': ref('PilotTask'), 'CLUSTER_ARN': ref('ClusterArn'),
                'SUBNET_IDS': {'Fn::Join': [',', ref('SubnetIds')]}, 'SECURITY_GROUP_IDS': {'Fn::Join': [',', ref('SecurityGroupIds')]},
                'CONTROL_FUNCTION_ARN': ref('ControlFunctionArn'), 'TELEGRAM_SECRET_ARN': ref('TelegramSecretArn')}}}},
        'SchedulerRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'RoleName': 'stock-paper-pilot-scheduler', 'Path': '/stock-paper/',
            'AssumeRolePolicyDocument': trust('scheduler.amazonaws.com'), 'Policies': [{
                'PolicyName': 'dated-pilot-and-fallback-stop', 'PolicyDocument': {'Version': '2012-10-17', 'Statement': [stop,
                    {'Effect': 'Allow', 'Action': ['lambda:InvokeFunction'], 'Resource': arn('Pilot')}]}}]}}
    }
    phases = ['GATE', 'START_PM', 'SCAN_1450', 'SHORTLIST_1510', 'ENTRY_1520', 'EQUITY_SNAPSHOT_1550', 'STOP_PM',
        'REPORT_PM', 'START_AM', 'EXIT_0905', 'EXIT_0910', 'STOP_AM', 'REPORT_AM', 'FALLBACK_PM', 'FALLBACK_AM']
    for phase in phases:
        logical = ''.join(word.title() for word in phase.split('_')) + 'Schedule'
        moment = logical + 'At'
        parameters[moment] = {'Type': 'String', 'AllowedPattern': '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'}
        target = {'Arn': arn('Pilot'), 'RoleArn': arn('SchedulerRole'),
            'Input': sub('{"action":"' + phase + '","pilot_id":"${PilotId}"}'),
            'RetryPolicy': {'MaximumEventAgeInSeconds': 60, 'MaximumRetryAttempts': 0}}
        if phase.startswith('FALLBACK_'):
            target.update(Arn=sub('arn:${AWS::Partition}:scheduler:::aws-sdk:ec2:stopInstances'),
                Input=sub('{"InstanceIds":["${NatInstanceId}"]}'))
        resources[logical] = {'Type': 'AWS::Scheduler::Schedule', 'Properties': {
            'Name': 'stock-paper-pilot-' + phase.lower().replace('_', '-'), 'State': ref('PilotState'),
            'ScheduleExpression': sub('at(${' + moment + '})'), 'ScheduleExpressionTimezone': 'UTC',
            'FlexibleTimeWindow': {'Mode': 'OFF'}, 'Target': target}}
    schedule_ids = [key for key, r in resources.items() if r['Type'] == 'AWS::Scheduler::Schedule']
    review = {'Version': '2012-10-17', 'Statement': [
        {'Effect': 'Allow', 'Action': ['cloudformation:DescribeStacks', 'cloudformation:DescribeStackEvents',
            'cloudformation:DescribeStackResources', 'cloudformation:GetTemplate'],
            'Resource': sub('arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/stock-automation-paper-pilot/*')},
        {'Effect': 'Allow', 'Action': ['lambda:GetFunction', 'lambda:GetFunctionConfiguration'], 'Resource': arn('Pilot')},
        {'Effect': 'Allow', 'Action': ['lambda:InvokeFunction'], 'Resource': arn('Pilot')},
        {'Effect': 'Allow', 'Action': ['scheduler:GetSchedule'], 'Resource': ref('RegularScheduleArns')},
        {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject'], 'Resource': [result, sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/${PlanKey}')]},
        {'Effect': 'Allow', 'Action': ['scheduler:GetSchedule', 'scheduler:UpdateSchedule'], 'Resource': [arn(key) for key in schedule_ids]},
        {'Effect': 'Allow', 'Action': ['iam:PassRole'], 'Resource': arn('SchedulerRole'),
            'Condition': {'StringEquals': {'iam:PassedToService': 'scheduler.amazonaws.com'}}},
        {'Effect': 'Allow', 'Action': ['logs:DescribeLogStreams', 'logs:GetLogEvents', 'logs:FilterLogEvents'], 'Resource': log}]}
    resources['OperatorReviewPolicy'] = {'Type': 'AWS::IAM::ManagedPolicy', 'Properties': {
        'ManagedPolicyName': 'StockPaperPilotReview', 'Users': [ref('OperatorUserName')], 'PolicyDocument': review}}
    return {'AWSTemplateFormatVersion': '2010-09-09', 'Description': 'One dated paper closing-bet session after independent morning PASS; no regular schedule changes',
        'Parameters': parameters, 'Resources': resources, 'Outputs': {
            'PilotArn': {'Value': arn('Pilot')}, 'PilotTaskArn': {'Value': ref('PilotTask')},
            'SchedulerRoleArn': {'Value': arn('SchedulerRole')},
            **{key + 'Arn': {'Value': arn(key)} for key in schedule_ids}}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True); args = parser.parse_args()
    output = Path(args.output)
    if output.exists(): raise SystemExit('Preserve existing output')
    output.write_text(json.dumps(build(), indent=2) + '\n', encoding='utf-8')
    print('DATED_PAPER_PILOT_TEMPLATE_BUILT; schedules disabled; no AWS calls')
