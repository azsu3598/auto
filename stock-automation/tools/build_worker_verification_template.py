"""Build a disabled-by-default, one-off normal-time empty paper worker test."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def next_trial_template(template):
    """New parameter names make console updates use the new dated defaults.

    This avoids silently retaining yesterday's UsePreviousValue settings. Keep
    resource names stable so updating the existing stack adds no new resources.
    """
    aliases = {name: 'Next' + name for name in ('TestId', 'StartAt', 'DispatchAt', 'RunAt', 'WatchAt', 'FailSafeAt')}
    def rewrite(value):
        if isinstance(value, list): return [rewrite(item) for item in value]
        if not isinstance(value, dict): return value
        result = {}
        for key, item in value.items():
            if key == 'Ref' and item in aliases:
                item = aliases[item]
            elif key == 'Fn::Sub' and isinstance(item, str):
                for old, new in aliases.items(): item = item.replace('${' + old + '}', '${' + new + '}')
            else:
                item = rewrite(item)
            result[key] = item
        return result
    result = rewrite(template)
    result['Parameters'] = {aliases.get(name, name): value for name, value in result['Parameters'].items()}
    return result, aliases


def build():
    def ref(name): return {'Ref': name}
    def sub(value): return {'Fn::Sub': value}
    def arn(name): return {'Fn::GetAtt': [name, 'Arn']}
    def trust(service):
        statement = {'Effect': 'Allow', 'Principal': {'Service': service}, 'Action': 'sts:AssumeRole'}
        if service == 'scheduler.amazonaws.com':
            statement['Condition'] = {'StringEquals': {'aws:SourceAccount': ref('AWS::AccountId')},
                'ArnLike': {'aws:SourceArn': sub('arn:${AWS::Partition}:scheduler:${AWS::Region}:${AWS::AccountId}:schedule-group/default')}}
        return {'Version': '2012-10-17', 'Statement': [statement]}
    host = sub('arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${NatInstanceId}')
    obj = sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/validation/worker/${TestId}.json')
    stop = {'Effect': 'Allow', 'Action': ['ec2:StopInstances'], 'Resource': host,
        'Condition': {'StringEquals': {'ec2:ResourceTag/Project': 'paper-fixed-egress',
            'ec2:ResourceTag/Name': 'stock-automation-paper-nat', 'aws:RequestedRegion': 'ap-northeast-2'}}}
    pass_runtime = {'Effect': 'Allow', 'Action': ['iam:PassRole'], 'Resource': [ref('TaskExecutionRoleArn'), ref('TaskRoleArn')],
        'Condition': {'StringEquals': {'iam:PassedToService': 'ecs-tasks.amazonaws.com'}}}
    read_log = sub('arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:${AppLogGroupName}:*')
    own_log = sub('arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/stock-paper-worker-verifier:*')
    policy = {'Version': '2012-10-17', 'Statement': [stop, pass_runtime,
        {'Effect': 'Allow', 'Action': ['ecs:RunTask'], 'Resource': ref('ValidationTask'),
            'Condition': {'ArnEquals': {'ecs:cluster': ref('ClusterArn')}}},
        {'Effect': 'Allow', 'Action': ['ecs:DescribeClusters'], 'Resource': ref('ClusterArn')},
        # ListTasks does not authorize a cluster ARN in Resource. Restrict this
        # read with its supported ecs:cluster condition instead (also Fargate).
        {'Effect': 'Allow', 'Action': ['ecs:ListTasks'], 'Resource': '*',
            'Condition': {'ArnEquals': {'ecs:cluster': ref('ClusterArn')},
                'StringEquals': {'aws:RequestedRegion': 'ap-northeast-2'}}},
        {'Effect': 'Allow', 'Action': ['ecs:DescribeTasks', 'ecs:StopTask'],
            'Resource': sub('arn:${AWS::Partition}:ecs:${AWS::Region}:${AWS::AccountId}:task/stock-automation-paper/*')},
        {'Effect': 'Allow', 'Action': ['ecs:DescribeTaskDefinition', 'ec2:DescribeInstances'], 'Resource': '*',
            'Condition': {'StringEquals': {'aws:RequestedRegion': 'ap-northeast-2'}}},
        {'Effect': 'Allow', 'Action': ['cloudformation:DescribeStacks'], 'Resource': [
            sub('arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/' + name + '/*')
            for name in ('stock-automation-paper', 'stock-automation-paper-control', 'stock-automation-paper-network')]},
        {'Effect': 'Allow', 'Action': ['lambda:InvokeFunction'], 'Resource': ref('ControlFunctionArn')},
        {'Effect': 'Allow', 'Action': ['dynamodb:GetItem', 'dynamodb:Scan'],
            'Resource': sub('arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/stock-automation-paper')},
        {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject'], 'Resource': obj},
        {'Effect': 'Allow', 'Action': ['s3:GetObject'],
            'Resource': sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/control/network/current.json')},
        {'Effect': 'Allow', 'Action': ['secretsmanager:GetSecretValue'], 'Resource': ref('TelegramSecretArn')},
        {'Effect': 'Allow', 'Action': ['logs:GetLogEvents'], 'Resource': read_log},
        {'Effect': 'Allow', 'Action': ['logs:CreateLogStream', 'logs:PutLogEvents'], 'Resource': own_log}]}
    bootstrap = (ROOT / 'infra/paper_worker_bootstrap.py').read_text(encoding='utf-8')
    environment = [
        {'Name': 'KIWOOM_MODE', 'Value': 'demo'}, {'Name': 'KIWOOM_TOKEN_STORE', 'Value': 'memory'},
        {'Name': 'LIVE_ORDER_ENABLED', 'Value': '0'},
        {'Name': 'NAT_INSTANCE_ID', 'Value': ref('NatInstanceId')}, {'Name': 'EXPECTED_EGRESS_IP', 'Value': ref('ExpectedEgressIp')},
        {'Name': 'PAPER_BUCKET', 'Value': ref('ArtifactBucketName')}, {'Name': 'PAPER_TABLE', 'Value': 'stock-automation-paper'},
        {'Name': 'TRADING_CALENDAR_KEY', 'Value': 'config/calendar/current.json'},
        *[{'Name': name, 'Value': ref(param)} for name, param in (
            ('STARTING_CASH', 'StartingCash'), ('MEDIUM_STARTING_CASH', 'MediumStartingCash'),
            ('DAY_TRADE_STARTING_CASH', 'DayTradeStartingCash'), ('BUY_FEE_BPS', 'BuyFeeBps'),
            ('SELL_FEE_BPS', 'SellFeeBps'), ('SELL_TAX_BPS', 'SellTaxBps'),
            ('PAPER_WALLET_EPOCH', 'PaperWalletEpoch'))],
        {'Name': 'NOTIFICATION_CHANNEL', 'Value': 'telegram'}, {'Name': 'NOTIFICATION_SECRET_ARN', 'Value': ref('TelegramSecretArn')},
        {'Name': 'SNS_NOTIFICATION_TOPIC_ARN', 'Value': ref('TradeNotificationTopicArn')}]
    resources = {
        'ValidationTask': {'Type': 'AWS::ECS::TaskDefinition', 'Properties': {
            'Family': 'stock-automation-paper-validation', 'Cpu': '512', 'Memory': '1024',
            'NetworkMode': 'awsvpc', 'RequiresCompatibilities': ['FARGATE'],
            'ExecutionRoleArn': ref('TaskExecutionRoleArn'), 'TaskRoleArn': ref('TaskRoleArn'),
            'Tags': [{'Key': 'Project', 'Value': 'stock-automation-paper'}],
            'Volumes': [{'Name': 'runtime-tmp'}], 'ContainerDefinitions': [{
                'Name': 'stock-automation', 'Image': ref('ImageUri'), 'Essential': True,
                'User': '65534:65534', 'ReadonlyRootFilesystem': True,
                'LinuxParameters': {'Capabilities': {'Drop': ['ALL']}, 'InitProcessEnabled': True},
                'MountPoints': [{'SourceVolume': 'runtime-tmp', 'ContainerPath': '/tmp', 'ReadOnly': False}],
                'EntryPoint': ['python'], 'Command': ['-c', bootstrap], 'Environment': environment,
                'Secrets': [{'Name': 'APP_KEY_MOCK', 'ValueFrom': sub('${KiwoomDemoSecretArn}:app_key_mock::')},
                    {'Name': 'APP_SECRET_MOCK', 'ValueFrom': sub('${KiwoomDemoSecretArn}:app_secret_mock::')},
                    {'Name': 'DART_API_KEY', 'ValueFrom': sub('${DartSecretArn}:dart_api_key::')}],
                'LogConfiguration': {'LogDriver': 'awslogs', 'Options': {'awslogs-group': ref('AppLogGroupName'),
                    'awslogs-region': ref('AWS::Region'), 'awslogs-stream-prefix': 'paper'}}}]}},
        'Boundary': {'Type': 'AWS::IAM::ManagedPolicy', 'Properties': {
            'ManagedPolicyName': 'StockPaperWorkerVerifierBoundary', 'PolicyDocument': policy}},
        'VerifierRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'RoleName': 'stock-paper-worker-verifier', 'Path': '/stock-paper/', 'PermissionsBoundary': ref('Boundary'),
            'AssumeRolePolicyDocument': trust('lambda.amazonaws.com'),
            'Policies': [{'PolicyName': 'one-empty-worker-test', 'PolicyDocument': policy}]}},
        'LogGroup': {'Type': 'AWS::Logs::LogGroup', 'Properties': {
            'LogGroupName': '/aws/lambda/stock-paper-worker-verifier', 'RetentionInDays': 7}},
        'Verifier': {'Type': 'AWS::Lambda::Function', 'DependsOn': 'LogGroup', 'Properties': {
            'FunctionName': 'stock-paper-worker-verifier', 'Runtime': 'python3.13', 'Handler': 'index.handler',
            'MemorySize': 128, 'Timeout': 900, 'ReservedConcurrentExecutions': 1, 'Role': arn('VerifierRole'),
            'Code': {'ZipFile': (ROOT/'infra/paper_worker_verifier.py').read_text(encoding='utf-8')},
            'Environment': {'Variables': {
                'PAPER_BUCKET': ref('ArtifactBucketName'), 'PAPER_TABLE': 'stock-automation-paper', 'TEST_ID': ref('TestId'),
                'RESULT_KEY': sub('validation/worker/${TestId}.json'), 'NAT_INSTANCE_ID': ref('NatInstanceId'),
                'RUN_AT': sub('${RunAt}+00:00'), 'START_AT': sub('${StartAt}+00:00'), 'WATCH_AT': sub('${WatchAt}+00:00'),
                'TASK_DEFINITION_ARN': ref('ValidationTask'), 'PRODUCTION_TASK_DEFINITION_ARN': ref('ProductionTaskDefinitionArn'),
                'EXPECTED_IMAGE_URI': ref('ImageUri'), 'CLUSTER_ARN': ref('ClusterArn'),
                'SUBNET_IDS': {'Fn::Join': [',', ref('SubnetIds')]},
                'SECURITY_GROUP_IDS': {'Fn::Join': [',', ref('SecurityGroupIds')]},
                'CONTROL_FUNCTION_ARN': ref('ControlFunctionArn'), 'APP_LOG_GROUP': ref('AppLogGroupName'),
                'TELEGRAM_SECRET_ARN': ref('TelegramSecretArn'), 'BOOTSTRAP_SHA256': hashlib.sha256(bootstrap.encode()).hexdigest()}}}},
        'SchedulerRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'RoleName': 'stock-paper-worker-test-scheduler', 'Path': '/stock-paper/',
            'AssumeRolePolicyDocument': trust('scheduler.amazonaws.com'), 'Policies': [{
                'PolicyName': 'one-off-start-check-and-stop', 'PolicyDocument': {'Version': '2012-10-17', 'Statement': [stop,
                    {'Effect': 'Allow', 'Action': ['lambda:InvokeFunction'], 'Resource': [ref('ControlFunctionArn'), arn('Verifier')]}]}}]}},
    }
    schedule_names = {'StartTest': 'start', 'RunTest': 'run', 'WatchTest': 'watch', 'FallbackStop': 'fallback-stop'}
    for logical, suffix in schedule_names.items():
        if logical == 'StartTest':
            moment, target, payload = 'StartAt', ref('ControlFunctionArn'), sub('{"action":"VERIFY_START","test_id":"${TestId}"}')
        elif logical in ('RunTest', 'WatchTest'):
            moment = 'DispatchAt' if logical == 'RunTest' else 'WatchAt'
            target = arn('Verifier')
            payload = sub('{"action":"' + ('RUN' if logical == 'RunTest' else 'WATCH') + '","test_id":"${TestId}"}')
        else:
            moment, target, payload = 'FailSafeAt', sub('arn:${AWS::Partition}:scheduler:::aws-sdk:ec2:stopInstances'), sub('{"InstanceIds":["${NatInstanceId}"]}')
        resources[logical] = {'Type': 'AWS::Scheduler::Schedule', 'Properties': {
            'Name': 'stock-paper-worker-test-' + suffix, 'State': ref('VerificationState'),
            'ScheduleExpression': sub('at(${' + moment + '})'), 'ScheduleExpressionTimezone': 'UTC',
            'FlexibleTimeWindow': {'Mode': 'OFF'}, 'Target': {'Arn': target, 'RoleArn': arn('SchedulerRole'),
                'Input': payload, 'RetryPolicy': {'MaximumEventAgeInSeconds': 60, 'MaximumRetryAttempts': 0}}}}
    review = [
        {'Effect': 'Allow', 'Action': ['ecs:ListTasks'], 'Resource': '*',
            'Condition': {'ArnEquals': {'ecs:cluster': ref('ClusterArn')},
                'StringEquals': {'aws:RequestedRegion': 'ap-northeast-2'}}},
        {'Effect': 'Allow', 'Action': ['cloudformation:DescribeStacks', 'cloudformation:DescribeStackEvents', 'cloudformation:DescribeStackResources', 'cloudformation:GetTemplate'],
            'Resource': sub('arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/stock-automation-paper-worker-test/*')},
        {'Effect': 'Allow', 'Action': ['lambda:GetFunction', 'lambda:GetFunctionConfiguration'], 'Resource': arn('Verifier')},
        {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject'], 'Resource': obj},
        {'Effect': 'Allow', 'Action': ['scheduler:GetSchedule', 'scheduler:UpdateSchedule'], 'Resource': [arn(name) for name in schedule_names]},
        {'Effect': 'Allow', 'Action': ['iam:PassRole'], 'Resource': arn('SchedulerRole'),
            'Condition': {'StringEquals': {'iam:PassedToService': 'scheduler.amazonaws.com'}}},
        {'Effect': 'Allow', 'Action': ['logs:DescribeLogStreams', 'logs:GetLogEvents', 'logs:FilterLogEvents'], 'Resource': own_log}]
    resources['OperatorReviewPolicy'] = {'Type': 'AWS::IAM::ManagedPolicy', 'Properties': {
        'ManagedPolicyName': 'StockPaperWorkerVerifierReview', 'Users': [ref('OperatorUserName')],
        'PolicyDocument': {'Version': '2012-10-17', 'Statement': review}}}
    parameters = {name: {'Type': 'String'} for name in (
        'NatInstanceId', 'ArtifactBucketName', 'TelegramSecretArn', 'TestId', 'StartAt', 'DispatchAt', 'RunAt', 'WatchAt', 'FailSafeAt',
        'ProductionTaskDefinitionArn', 'ImageUri', 'ClusterArn', 'TaskExecutionRoleArn', 'TaskRoleArn', 'AppLogGroupName',
        'ControlFunctionArn', 'KiwoomDemoSecretArn', 'DartSecretArn', 'ExpectedEgressIp', 'TradeNotificationTopicArn')}
    parameters.update(SubnetIds={'Type': 'CommaDelimitedList'}, SecurityGroupIds={'Type': 'CommaDelimitedList'},
        VerificationState={'Type': 'String', 'Default': 'DISABLED', 'AllowedValues': ['DISABLED', 'ENABLED']},
        OperatorUserName={'Type': 'String', 'Default': 'stock-paper-operator', 'AllowedValues': ['stock-paper-operator']})
    parameters['TestId']['AllowedPattern'] = '[a-f0-9]{32}'
    for name in ('StartAt', 'DispatchAt', 'RunAt', 'WatchAt', 'FailSafeAt'):
        parameters[name]['AllowedPattern'] = '[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
    for name, default in (('StartingCash', '200000'), ('MediumStartingCash', '200000'), ('DayTradeStartingCash', '200000'),
                          ('BuyFeeBps', '1.5'), ('SellFeeBps', '1.5'), ('SellTaxBps', '20')):
        parameters[name] = {'Type': 'String', 'Default': default}
    # Empty keeps the original wallet keys; the 200,000 KRW run uses 200K-20261103.
    parameters['PaperWalletEpoch'] = {'Type': 'String', 'Default': '', 'AllowedPattern': '[A-Za-z0-9_-]{0,40}'}
    return {'AWSTemplateFormatVersion': '2010-09-09',
        'Description': 'Disabled one-off prewarmed empty 09:05 paper worker verification; no recurring or live schedule activation',
        'Parameters': parameters, 'Resources': resources, 'Outputs': {
            'VerifierArn': {'Value': arn('Verifier')}, 'ValidationTaskArn': {'Value': ref('ValidationTask')},
            'SchedulerRoleArn': {'Value': arn('SchedulerRole')}, 'ResultKey': {'Value': sub('validation/worker/${TestId}.json')},
            **{name + 'Arn': {'Value': arn(name)} for name in schedule_names}}}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); args = p.parse_args()
    output = Path(args.output)
    if output.exists(): raise SystemExit('Preserve existing output')
    output.write_text(json.dumps(build(), indent=2) + '\n', encoding='utf-8')
    print('ONE_OFF_WORKER_TEMPLATE_BUILT; schedules disabled; no AWS calls')
