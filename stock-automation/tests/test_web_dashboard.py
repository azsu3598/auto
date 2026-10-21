import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
api=module('paper_web_api',ROOT/'infra/paper_web_api.py')
builder=module('web_template',ROOT/'tools/build_web_dashboard_template.py')
packager=module('web_package',ROOT/'tools/package_web_dashboard.py')


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.env={'PAPER_TABLE':'stock-automation-paper','LIVE_ORDER_ENABLED':'0','CLIENT_ID':'client',
            'TOKEN_ISSUER':'https://issuer.example/pool'}
        self.event={'rawPath':'/api/dashboard','rawQueryString':'','requestContext':{
            'http':{'method':'GET'},'authorizer':{'jwt':{'claims':{'token_use':'access','client_id':'client',
                'iss':'https://issuer.example/pool','scope':'openid'}}}}}
        self.client=Mock();self.client.scan.return_value={'Items':[]}

    def test_authentication_required_before_any_ledger_read(self):
        for update in ({'token_use':'id'},{'client_id':'other'},{'iss':'https://other.example'},{'scope':''}):
            event=json.loads(json.dumps(self.event));event['requestContext']['authorizer']['jwt']['claims'].update(update)
            self.assertEqual(api.handle(event,client=self.client,env=self.env)['statusCode'],401)
        self.client.scan.assert_not_called()

    def test_anonymous_request_and_writes_never_reach_the_table(self):
        event=json.loads(json.dumps(self.event));event['requestContext'].pop('authorizer')
        self.assertEqual(api.handle(event,client=self.client,env=self.env)['statusCode'],401)
        event['requestContext']['http']['method']='POST'
        self.assertEqual(api.handle(event,client=self.client,env=self.env)['statusCode'],405)
        self.client.scan.assert_not_called()

    def test_live_environment_or_table_switch_is_rejected(self):
        for change in ({'LIVE_ORDER_ENABLED':'1'},{'PAPER_TABLE':'live-table'}):
            self.assertEqual(api.handle(self.event,client=self.client,env={**self.env,**change})['statusCode'],503)
        self.client.scan.assert_not_called()

    def test_query_cannot_select_an_account_or_another_table(self):
        self.event['rawQueryString']='table=live'
        self.assertEqual(api.handle(self.event,client=self.client,env=self.env)['statusCode'],400)
        self.client.scan.assert_not_called()

    def test_valid_empty_paper_ledger_is_not_replaced_with_sample_positions(self):
        response=api.handle(self.event,client=self.client,env=self.env)
        data=json.loads(response['body'])
        self.assertEqual(response['statusCode'],200);self.assertEqual(data['positions'],[])
        self.assertEqual(data['metrics']['available_cash'],0)
        self.assertEqual(response['headers']['Cache-Control'],'no-store')
        self.assertEqual([c[0] for c in self.client.method_calls],['scan'])

    def test_accidental_live_records_and_account_guards_are_not_returned(self):
        self.client.scan.return_value={'Items':[
            {'pk':{'S':'CONTROL#ACCOUNT_GUARD'},'account_fingerprint':{'S':'private-account'}},
            {'pk':{'S':'EQUITY#LIVE#2026-10-19'},'mode':{'S':'LIVE'},'total_assets':{'N':'9000'}},
            {'pk':{'S':'LIVE_ORDER#private-id'},'account_alias':{'S':'private-alias'}}]}
        response=api.handle(self.event,client=self.client,env=self.env)
        self.assertNotIn('private-account',response['body']);self.assertNotIn('private-alias',response['body'])
        self.assertEqual(json.loads(response['body'])['equity_history']['LIVE'],[])

    def test_scan_limit_fails_instead_of_presenting_partial_cash_as_a_total(self):
        self.client.scan.return_value={'Items':[],'LastEvaluatedKey':{'pk':{'S':'next'}}}
        response=api.handle(self.event,client=self.client,env=self.env)
        self.assertEqual(response['statusCode'],503);self.assertEqual(self.client.scan.call_count,5)


class WebDeploymentTests(unittest.TestCase):
    def test_reader_role_has_only_scan_on_one_paper_table_and_own_logs(self):
        t=builder.build();statements=t['Resources']['ReadBoundary']['Properties']['PolicyDocument']['Statement']
        actions={a for s in statements for a in s['Action']}
        self.assertEqual(actions,{'dynamodb:Scan','logs:CreateLogStream','logs:PutLogEvents'})
        self.assertEqual(t['Parameters']['PaperTableName']['AllowedValues'],['stock-automation-paper'])
        role=t['Resources']['ReadRole']['Properties'];self.assertEqual(role['PermissionsBoundary'],{'Ref':'ReadBoundary'})

    def test_every_api_route_requires_jwt_access_scope_and_no_default_public_route(self):
        t=builder.build();routes=[r['Properties'] for r in t['Resources'].values() if r['Type']=='AWS::ApiGatewayV2::Route']
        self.assertEqual(len(routes),1);self.assertEqual(routes[0]['RouteKey'],'GET /api/dashboard')
        self.assertEqual(routes[0]['AuthorizationType'],'JWT');self.assertEqual(routes[0]['AuthorizationScopes'],['openid'])
        cors=t['Resources']['HttpApi']['Properties']['CorsConfiguration']
        self.assertEqual(cors['AllowOrigins'],[{'Fn::Sub':'https://${Distribution.DomainName}'}])

    def test_hosting_is_https_private_s3_and_has_no_ec2_services_or_trading_schedules(self):
        t=builder.build();types={r['Type'] for r in t['Resources'].values()}
        self.assertFalse(types.intersection({'AWS::EC2::Instance','AWS::ECS::Service','AWS::Scheduler::Schedule'}))
        bucket=t['Resources']['WebBucket']['Properties']['PublicAccessBlockConfiguration']
        self.assertTrue(all(bucket.values()))
        behavior=t['Resources']['Distribution']['Properties']['DistributionConfig']['DefaultCacheBehavior']
        self.assertEqual(behavior['ViewerProtocolPolicy'],'redirect-to-https')
        self.assertEqual(behavior['AllowedMethods'],['GET','HEAD'])

    def test_user_pool_cannot_self_register_and_public_client_has_no_secret_or_implicit_grant(self):
        t=builder.build();pool=t['Resources']['UserPool']['Properties'];client=t['Resources']['WebClient']['Properties']
        self.assertTrue(pool['AdminCreateUserConfig']['AllowAdminCreateUserOnly'])
        self.assertEqual(pool['UserPoolTier'],'LITE');self.assertFalse(client['GenerateSecret'])
        self.assertEqual(client['AllowedOAuthFlows'],['code']);self.assertEqual(client['AccessTokenValidity'],5)

    def test_code_artifact_key_is_hash_pinned_and_template_matches_builder(self):
        t=builder.build()
        self.assertIsNotNone(re.fullmatch(t['Parameters']['ApiCodeKey']['AllowedPattern'],'config/web/'+'a'*64+'.zip'))
        self.assertEqual(json.loads((ROOT/'infra/paper-web-dashboard.yaml').read_text(encoding='utf-8')),t)

    def test_package_contains_no_broker_code_or_private_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'web';manifest=packager.package(output)
            with zipfile.ZipFile(output/'api.zip') as archive:
                self.assertEqual(set(archive.namelist()),{'paper_web_api.py','stock_automation/dashboard.py','stock_automation/__init__.py'})
            self.assertFalse((output/'static/config.js').exists())
            html=(output/'static/index.html').read_text(encoding='utf-8')
            self.assertLess(html.index('/auth.js'),html.index('/app.js'))
            self.assertIn('window.sabuDashboardFetch()', (output/'static/app.js').read_text(encoding='utf-8'))
            with self.assertRaises(ValueError):packager.package(output)


if __name__=='__main__':unittest.main()
