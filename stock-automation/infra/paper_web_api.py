"""Authenticated, read-only HTTP API for the paper ledger; no broker modules."""
import json
import os
from stock_automation.dashboard import dashboard_payload


def reply(status, body):
    return {'statusCode': status, 'headers': {'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
        'body': json.dumps(body, ensure_ascii=False)}


def handle(event, *, client, env):
    context = event.get('requestContext', {})
    if context.get('http', {}).get('method') != 'GET':
        return reply(405, {'error': 'READ_ONLY'})
    if event.get('rawPath') != '/api/dashboard':
        return reply(404, {'error': 'NOT_FOUND'})
    claims = context.get('authorizer', {}).get('jwt', {}).get('claims', {})
    scopes = str(claims.get('scope', '')).split()
    if (claims.get('token_use') != 'access' or claims.get('client_id') != env['CLIENT_ID']
            or claims.get('iss') != env['TOKEN_ISSUER'] or 'openid' not in scopes):
        return reply(401, {'error': 'SIGN_IN_REQUIRED'})
    if event.get('rawQueryString'):
        return reply(400, {'error': 'QUERY_NOT_SUPPORTED'})
    if env.get('PAPER_TABLE') != 'stock-automation-paper' or env.get('LIVE_ORDER_ENABLED') != '0':
        return reply(503, {'error': 'PAPER_ONLY_CONFIGURATION_REQUIRED'})
    from stock_automation.dashboard import _decode_item
    items = []
    request = {'TableName': env['PAPER_TABLE'], 'Limit': 200}
    for _ in range(5):
        page = client.scan(**request)
        items.extend(_decode_item(row) for row in page.get('Items', []))
        if not page.get('LastEvaluatedKey'):
            break
        request['ExclusiveStartKey'] = page['LastEvaluatedKey']
    else:
        return reply(503, {'error': 'LEDGER_TOO_LARGE_FOR_SUMMARY'})
    # Only the paper table is reachable by IAM. Exclude accidental live records
    # defensively as well; account guard details never leave this API.
    items = [row for row in items if not str(row.get('pk', '')).startswith(
        ('LIVE_', 'EQUITY#LIVE#', 'WALLET#LIVE#', 'CONTROL#LIVE', 'CONTROL#ACCOUNT_GUARD'))]
    data = dashboard_payload(items)
    data['mode'] = 'LIVE_LOCKED'
    data['live_orders'] = []
    data['equity_history']['LIVE'] = []
    data['warnings'].append('표시된 시간표는 운영 계획이며 실제 AWS 예약 활성 상태를 나타내지 않습니다.')
    return reply(200, data)


def handler(event, context):
    import boto3
    from botocore.config import Config
    try:
        return handle(event, client=boto3.client('dynamodb', config=Config(
            connect_timeout=3, read_timeout=5, retries={'max_attempts': 1})), env=os.environ)
    except Exception:
        return reply(503, {'error': 'DASHBOARD_DATA_UNAVAILABLE'})
