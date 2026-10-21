"""Build an inspectable one-off timer trial; never enable a trading schedule."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    def sub(value): return {'Fn::Sub': value}
    def ref(value): return {'Ref': value}
    def arn(value): return {'Fn::GetAtt': [value, 'Arn']}
    host = sub('arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${NatInstanceId}')
    obj = sub('arn:${AWS::Partition}:s3:::${ArtifactBucketName}/validation/timer/${TestId}.json')
    stop = {'Effect': 'Allow', 'Action': ['ec2:StopInstances'], 'Resource': host,
        'Condition': {'StringEquals': {'ec2:ResourceTag/Project': 'paper-fixed-egress',
            'ec2:ResourceTag/Name': 'stock-automation-paper-nat', 'aws:RequestedRegion': 'ap-northeast-2'}}}
    observer_policy = {'Version': '2012-10-17', 'Statement': [stop,
        {'Effect': 'Allow', 'Action': ['ec2:DescribeInstances'], 'Resource': '*',
            'Condition': {'StringEquals': {'aws:RequestedRegion': 'ap-northeast-2'}}},
        {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject'], 'Resource': obj},
        {'Effect': 'Allow', 'Action': ['secretsmanager:GetSecretValue'], 'Resource': ref('TelegramSecretArn')},
        {'Effect': 'Allow', 'Action': ['logs:CreateLogStream', 'logs:PutLogEvents'],
            'Resource': sub('arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/stock-paper-timer-verifier:*')}]}
    def trust(service):
        statement = {'Effect': 'Allow', 'Principal': {'Service': service}, 'Action': 'sts:AssumeRole'}
        if service == 'scheduler.amazonaws.com':
            statement['Condition'] = {'StringEquals': {'aws:SourceAccount': ref('AWS::AccountId')},
                'ArnLike': {'aws:SourceArn': sub('arn:${AWS::Partition}:scheduler:${AWS::Region}:${AWS::AccountId}:schedule-group/default')}}
        return {'Version': '2012-10-17', 'Statement': [statement]}
    scheduler_policy = {'Version': '2012-10-17', 'Statement': [stop,
        {'Effect': 'Allow', 'Action': ['lambda:InvokeFunction'], 'Resource': arn('Verifier')}]}
    resources = {
        'Boundary': {'Type': 'AWS::IAM::ManagedPolicy', 'Properties': {
            'ManagedPolicyName': 'StockPaperTimerVerifierBoundary', 'PolicyDocument': observer_policy}},
        'ObserverRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'RoleName': 'stock-paper-timer-verifier', 'Path': '/stock-paper/',
            'AssumeRolePolicyDocument': trust('lambda.amazonaws.com'), 'PermissionsBoundary': ref('Boundary'),
            'Policies': [{'PolicyName': 'one-nat-one-test', 'PolicyDocument': observer_policy}]}},
        'LogGroup': {'Type': 'AWS::Logs::LogGroup', 'Properties': {
            'LogGroupName': '/aws/lambda/stock-paper-timer-verifier', 'RetentionInDays': 7}},
        'Verifier': {'Type': 'AWS::Lambda::Function', 'DependsOn': 'LogGroup', 'Properties': {
            'FunctionName': 'stock-paper-timer-verifier', 'Runtime': 'python3.13', 'Handler': 'index.handler',
            'MemorySize': 128, 'Timeout': 60, 'ReservedConcurrentExecutions': 1,
            'Role': arn('ObserverRole'),
            'Code': {'ZipFile': (ROOT/'infra/paper_timer_verifier.py').read_text(encoding='utf-8')},
            'Environment': {'Variables': {'NAT_INSTANCE_ID': ref('NatInstanceId'),
                'PAPER_BUCKET': ref('ArtifactBucketName'), 'TEST_ID': ref('TestId'),
                'RESULT_KEY': sub('validation/timer/${TestId}.json'),
                'CHECK_AT': sub('${CheckAt}+00:00'), 'TELEGRAM_SECRET_ARN': ref('TelegramSecretArn')}}}},
        'StopRule': {'Type': 'AWS::Events::Rule', 'Properties': {'Name': 'stock-paper-timer-stop-observer',
            'State': ref('ObservationState'), 'EventPattern': {'source': ['aws.ec2'],
                'detail-type': ['EC2 Instance State-change Notification'],
                'detail': {'instance-id': [ref('NatInstanceId')], 'state': ['stopped']}},
            'Targets': [{'Id': 'timer-result', 'Arn': arn('Verifier'),
                'RetryPolicy': {'MaximumEventAgeInSeconds': 300, 'MaximumRetryAttempts': 2}}]}},
        'StopPermission': {'Type': 'AWS::Lambda::Permission', 'Properties': {'Action': 'lambda:InvokeFunction',
            'FunctionName': ref('Verifier'), 'Principal': 'events.amazonaws.com',
            'SourceArn': arn('StopRule'), 'SourceAccount': ref('AWS::AccountId')}},
        'SchedulerRole': {'Type': 'AWS::IAM::Role', 'Properties': {
            'RoleName': 'stock-paper-timer-scheduler', 'Path': '/stock-paper/',
            'AssumeRolePolicyDocument': trust('scheduler.amazonaws.com'),
            'Policies': [{'PolicyName': 'one-off-check-and-stop', 'PolicyDocument': scheduler_policy}]}},
        'TimeoutCheck': {'Type': 'AWS::Scheduler::Schedule', 'Properties': {
            'Name': 'stock-paper-timer-timeout', 'State': ref('ObservationState'),
            'ScheduleExpression': sub('at(${CheckAt})'), 'ScheduleExpressionTimezone': 'UTC',
            'FlexibleTimeWindow': {'Mode': 'OFF'},
            'Target': {'Arn': arn('Verifier'), 'RoleArn': arn('SchedulerRole'),
                'Input': '{"action":"TIMEOUT"}',
                'RetryPolicy': {'MaximumEventAgeInSeconds': 60, 'MaximumRetryAttempts': 0}}}},
        'FallbackStop': {'Type': 'AWS::Scheduler::Schedule', 'Properties': {
            'Name': 'stock-paper-timer-fallback-stop', 'State': ref('ObservationState'),
            'ScheduleExpression': sub('at(${FailSafeAt})'), 'ScheduleExpressionTimezone': 'UTC',
            'FlexibleTimeWindow': {'Mode': 'OFF'},
            'Target': {'Arn': sub('arn:${AWS::Partition}:scheduler:::aws-sdk:ec2:stopInstances'),
                'RoleArn': arn('SchedulerRole'), 'Input': sub('{"InstanceIds":["${NatInstanceId}"]}'),
                'RetryPolicy': {'MaximumEventAgeInSeconds': 60, 'MaximumRetryAttempts': 1}}}},
        'OperatorReviewPolicy': {'Type': 'AWS::IAM::ManagedPolicy', 'Properties': {
            'ManagedPolicyName': 'StockPaperTimerVerifierReview', 'Users': [ref('OperatorUserName')],
            'PolicyDocument': {'Version': '2012-10-17', 'Statement': [
                {'Effect': 'Allow', 'Action': ['s3:PutObject'], 'Resource': obj},
                {'Effect': 'Allow', 'Action': ['cloudformation:DescribeStacks', 'cloudformation:DescribeStackEvents',
                    'cloudformation:DescribeStackResources', 'cloudformation:GetTemplate'],
                    'Resource': sub('arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/stock-automation-paper-timer-test/*')},
                {'Effect': 'Allow', 'Action': ['lambda:GetFunction', 'lambda:GetFunctionConfiguration', 'lambda:InvokeFunction'],
                    'Resource': arn('Verifier')},
                {'Effect': 'Allow', 'Action': ['scheduler:GetSchedule'],
                    'Resource': [arn('TimeoutCheck'), arn('FallbackStop')]},
                {'Effect': 'Allow', 'Action': ['events:DescribeRule', 'events:ListTargetsByRule'], 'Resource': arn('StopRule')},
                {'Effect': 'Allow', 'Action': ['logs:DescribeLogStreams', 'logs:GetLogEvents', 'logs:FilterLogEvents'],
                    'Resource': sub('arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/stock-paper-timer-verifier:*')}]}}},
    }
    parameters = {name: {'Type': 'String'} for name in
        ('NatInstanceId', 'ArtifactBucketName', 'TelegramSecretArn', 'TestId', 'CheckAt', 'FailSafeAt')}
    parameters['ObservationState'] = {'Type': 'String', 'Default': 'DISABLED', 'AllowedValues': ['DISABLED', 'ENABLED']}
    parameters['TestId']['AllowedPattern'] = '[a-f0-9]{32}'
    parameters['OperatorUserName'] = {'Type': 'String', 'Default': 'stock-paper-operator', 'AllowedValues': ['stock-paper-operator']}
    return {'AWSTemplateFormatVersion': '2010-09-09',
        'Description': 'One existing NAT timer trial only; no host start, broker or trading permissions',
        'Parameters': parameters, 'Resources': resources,
        'Outputs': {'VerifierArn': {'Value': arn('Verifier')}, 'ResultKey': {'Value': sub('validation/timer/${TestId}.json')}}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    args = parser.parse_args(); output = Path(args.output)
    if output.exists(): raise SystemExit('Preserve existing output; review before regenerating')
    output.write_text(json.dumps(build(), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('ONE_OFF_TIMER_TEMPLATE_BUILT; no AWS calls')
