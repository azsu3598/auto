"""User-operated status and STOP for the dated paper pilot. No start command."""
import argparse
import json
from pathlib import Path
import sys
import time
import uuid
from datetime import datetime,timezone

WORKSPACE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(WORKSPACE/'stock-automation/src'))
from stock_automation.paper_wallet import wallet_key  # noqa: E402
DEFAULT_PLAN=WORKSPACE/'runtime/paper-pilot-plan-20261022-final.json'
BATCH_PLAN=WORKSPACE/'runtime/paper-batch-plan-20261022-reviewed4.json'
KEEP_CLEANUP={'STOP_PM','STOP_AM','REPORT_PM','REPORT_AM','FALLBACK_PM','FALLBACK_AM'}


class Operations:
    def __init__(self,plan,clients,sleep=time.sleep,monotonic=time.monotonic):
        if plan.get('stack_name')!='stock-automation-paper-pilot' or plan['pilot_plan'].get('paper_only') is not True:
            raise ValueError('APPROVED_PAPER_PILOT_REQUIRED')
        self.plan,self.clients,self.sleep,self.monotonic=plan,clients,sleep,monotonic
        self.params=plan['parameters'];self.prefix='validation/pilot/'+self.params['PilotId']

    def get(self,name):
        try:
            return json.loads(self.clients['s3'].get_object(Bucket=self.params['ArtifactBucketName'],
                Key=self.prefix+'/'+name+'.json')['Body'].read())
        except Exception as error:
            if getattr(error,'response',{}).get('Error',{}).get('Code') in ('NoSuchKey','404','NotFound'):return None
            raise

    def status(self):
        vm=self.clients['ec2'].describe_instances(InstanceIds=[self.params['NatInstanceId']])['Reservations'][0]['Instances'][0]
        cluster=self.clients['ecs'].describe_clusters(clusters=[self.params['ClusterArn']])['clusters'][0]
        phases={}
        for name in ('ARMED','STOP','GATE','START_PM','SCAN_1450','SHORTLIST_1510','ENTRY_1520',
                'STOP_PM','REPORT_PM','START_AM','EXIT_0905','EXIT_0910','STOP_AM','REPORT_AM'):
            item=self.get(name)
            phases[name]={k:item[k] for k in ('status','reason','report') if k in item} if item else {'status':'NO_RECORD'}
        # The stack's PaperWalletEpoch names the wallet; an older plan has none.
        key=wallet_key('CLOSING_BET','KRX_1520',epoch=self.params.get('PaperWalletEpoch',''))
        wallet=self.clients['dynamodb'].get_item(TableName='stock-automation-paper',
            Key={'pk':{'S':key}},ConsistentRead=True).get('Item',{})
        opened=self.clients['dynamodb'].get_item(TableName='stock-automation-paper',
            Key={'pk':{'S':'OPEN#CLOSING_BET#KRX_1520'}},ConsistentRead=True).get('Item',{})
        return {'paper_only':True,'entry_date':self.params['EntryDate'],'exit_date':self.params['ExitDate'],
            'server_state':vm['State']['Name'],'running_tasks':cluster['runningTasksCount'],
            'pending_tasks':cluster['pendingTasksCount'],'wallet_key':key,
            'virtual_available_cash':wallet.get('available_cash',{}).get('N','NOT_CREATED'),
            'open_virtual_quantity':opened.get('remaining_quantity',{}).get('N','0'),'phases':phases}

    def stop(self):
        # Persist the entry fence before disabling any schedule or asking the
        # controller to drain tasks. No reset/delete/start capability exists here.
        marker={'status':'STOPPED_BY_OPERATOR','at':datetime.now(timezone.utc).isoformat()}
        try:
            self.clients['s3'].put_object(Bucket=self.params['ArtifactBucketName'],Key=self.prefix+'/STOP.json',
                Body=json.dumps(marker).encode(),ContentType='application/json',IfNoneMatch='*')
        except Exception as error:
            if getattr(error,'response',{}).get('Error',{}).get('Code')!='PreconditionFailed':raise
        cf=self.clients['cloudformation']
        stack=cf.describe_stacks(StackName='stock-automation-paper-pilot')['Stacks'][0]
        outputs={r['OutputKey']:r['OutputValue'] for r in stack['Outputs']}
        schedule=self.clients['scheduler'];disabled=0;errors=[]
        allowed=set(schedule.meta.service_model.operation_model('UpdateSchedule').input_shape.members)
        for name in self.plan['pilot_plan']['events']:
            if name in KEEP_CLEANUP:continue
            logical=''.join(x.title() for x in name.split('_'))+'Schedule'
            try:
                item=schedule.get_schedule(Name='stock-paper-pilot-'+name.lower().replace('_','-'))
                if item['Arn']!=outputs[logical+'Arn']:raise ValueError('SCHEDULE_IDENTITY_CHANGED')
                args={k:v for k,v in item.items() if k in allowed};args['State']='DISABLED'
                schedule.update_schedule(**args)
                if schedule.get_schedule(Name=item['Name'])['State']!='DISABLED':raise ValueError('DISABLE_NOT_CONFIRMED')
                disabled+=1
            except Exception as error:
                errors.append(getattr(error,'response',{}).get('Error',{}).get('Code',type(error).__name__))
        control=cf.describe_stacks(StackName='stock-automation-paper-control')['Stacks'][0]
        function={r['OutputKey']:r['OutputValue'] for r in control['Outputs']}['ControlFunctionArn']
        if function!=self.params['ControlFunctionArn']:raise ValueError('CONTROL_IDENTITY_CHANGED')
        response=self.clients['lambda'].invoke(FunctionName=function,InvocationType='RequestResponse',
            Payload=json.dumps({'action':'VERIFY_STOP','test_id':'operator-'+uuid.uuid4().hex}).encode())
        result=json.loads(response['Payload'].read())
        if response.get('FunctionError') or result.get('state')!='STOP_REQUESTED' or not result.get('cleanup_complete'):
            raise ValueError('CONTROLLER_CLEANUP_NOT_CONFIRMED')
        deadline=self.monotonic()+150
        while self.monotonic()<deadline:
            state=self.status()
            if state['server_state']=='stopped' and not state['running_tasks'] and not state['pending_tasks']:break
            self.sleep(3)
        else:raise ValueError('SERVER_STOP_NOT_CONFIRMED')
        return {'status':'STOPPED','entry_fence_saved':True,'entry_schedules_disabled':disabled,
            'cleanup_and_reports_preserved':True,'schedule_errors':errors,
            'forced_cleanup':bool(result.get('forced_cleanup')),'open_virtual_quantity':state['open_virtual_quantity']}


class BatchOperations:
    """Read the bounded continuation, or permanently fence its own launches."""
    def __init__(self,plan,clients):
        batch=plan.get('batch_plan',{})
        if (plan.get('stack_name')!='stock-automation-paper-batch-v2' or batch.get('paper_only') is not True
                or len(batch.get('sessions',[])) not in (2,3,5) or batch.get('batch_id')!=plan['parameters']['PilotId']):
            raise ValueError('APPROVED_SESSION_BATCH_REQUIRED')
        self.plan,self.clients=plan,clients
        self.params=plan['parameters'];self.prefix='validation/batch/'+self.params['PilotId']

    def get(self,name):
        key=self.prefix+'/'+name+'.json'
        page=self.clients['s3'].list_objects_v2(Bucket=self.params['ArtifactBucketName'],Prefix=key,MaxKeys=1)
        if not any(row['Key']==key for row in page.get('Contents',[])):return {'status':'NO_RECORD'}
        item=json.loads(self.clients['s3'].get_object(Bucket=self.params['ArtifactBucketName'],Key=key)['Body'].read())
        return {k:item[k] for k in ('status','phase','reason','report') if k in item}

    def status(self):
        # A 200,000 KRW batch writes the PaperWalletEpoch wallet, not the pilot's.
        key=wallet_key('CLOSING_BET','KRX_1520',epoch=self.params.get('PaperWalletEpoch',''))
        wallet=self.clients['dynamodb'].get_item(TableName='stock-automation-paper',
            Key={'pk':{'S':key}},ConsistentRead=True).get('Item',{})
        return {'bounded_sessions':len(self.plan['batch_plan']['sessions']),'ARMED':self.get('ARMED'),'HALT':self.get('HALT'),'STOP':self.get('STOP'),
            'wallet_key':key,'virtual_available_cash':wallet.get('available_cash',{}).get('N','NOT_CREATED'),
            'sessions':[{'entry_date':slot['entry_date'],'exit_date':slot['exit_date'],
                'phases':{phase:self.get('sessions/'+slot['entry_date']+'/'+phase) for phase in
                    ('GATE','SCAN_1450','SHORTLIST_1510','ENTRY_1520','EXIT_0910','REPORT_AM')}}
                for slot in self.plan['batch_plan']['sessions']]}

    def stop_entries(self):
        marker={'status':'STOPPED_BY_OPERATOR','at':datetime.now(timezone.utc).isoformat()}
        try:
            self.clients['s3'].put_object(Bucket=self.params['ArtifactBucketName'],Key=self.prefix+'/STOP.json',
                Body=json.dumps(marker).encode(),ContentType='application/json',IfNoneMatch='*')
        except Exception as error:
            if getattr(error,'response',{}).get('Error',{}).get('Code')!='PreconditionFailed':raise
        errors=[];disabled=0
        try:
            stack=self.clients['cloudformation'].describe_stacks(StackName=self.plan['stack_name'])['Stacks'][0]
            outputs={r['OutputKey']:r['OutputValue'] for r in stack['Outputs']}
            scheduler=self.clients['scheduler']
            allowed=set(scheduler.meta.service_model.operation_model('UpdateSchedule').input_shape.members)
            for phase in ('GATE','START_PM','START_AM','SCAN_1450','SHORTLIST_1510','ENTRY_1520',
                          'EQUITY_SNAPSHOT_1550','EXIT_0905','EXIT_0910'):
                try:
                    logical=''.join(x.title() for x in phase.split('_'))+'Schedule'
                    item=scheduler.get_schedule(Name='stock-paper-batch-'+phase.lower().replace('_','-'))
                    if item['Arn']!=outputs[logical+'Arn']:raise ValueError('BATCH_SCHEDULE_IDENTITY_CHANGED')
                    args={k:v for k,v in item.items() if k in allowed};args['State']='DISABLED'
                    scheduler.update_schedule(**args)
                    if scheduler.get_schedule(Name=item['Name'])['State']!='DISABLED':raise ValueError('BATCH_DISABLE_NOT_CONFIRMED')
                    disabled+=1
                except Exception as error:
                    errors.append(getattr(error,'response',{}).get('Error',{}).get('Code',type(error).__name__))
        except Exception as error:
            errors.append(getattr(error,'response',{}).get('Error',{}).get('Code',type(error).__name__))
        # Caller still invokes the established bounded controller STOP even when
        # schedule metadata is unavailable. The permanent entry fence is saved.
        return {'entry_fence_saved':True,'entry_schedules_disabled':disabled,'schedule_errors':errors,
                'cleanup_and_reports_preserved':True}


def main():
    parser=argparse.ArgumentParser(description='모의운용 상태 확인 / 신규 진입 차단과 서버 중지')
    parser.add_argument('action',choices=('status','stop'))
    parser.add_argument('--plan',type=Path,default=DEFAULT_PLAN)
    args=parser.parse_args()
    plan=json.loads(args.plan.read_text(encoding='utf-8'))
    # Reuse the established Windows system-CA/profile identity wrapper; it reads
    # no broker/Telegram secrets and prints no AWS account or endpoint values.
    sys.path.insert(0,str(WORKSPACE/'runtime'))
    import deploy_paper_app_recovered_20261018 as d
    from botocore.config import Config
    session=d.session()
    if session.client('sts').get_caller_identity()['Account']!=plan['account_id']:
        raise ValueError('AWS_ACCOUNT_MISMATCH')
    clients={name:session.client(name,config=Config(connect_timeout=6,
        read_timeout=230 if name=='lambda' else 15,retries={'max_attempts':0 if name=='lambda' else 1}))
        for name in ('s3','ec2','ecs','dynamodb','cloudformation','scheduler','lambda')}
    operations=Operations(plan,clients)
    batch_plan=json.loads(BATCH_PLAN.read_text(encoding='utf-8')) if args.plan==DEFAULT_PLAN and BATCH_PLAN.exists() else None
    batch=None
    if batch_plan and batch_plan.get('status')=='ARMED_IN_AWS':
        if batch_plan.get('account_id')!=plan['account_id']:raise ValueError('BATCH_ACCOUNT_MISMATCH')
        batch=BatchOperations(batch_plan,clients)
    if args.action=='status':
        result=operations.status()
        if batch:result['follow_on']=batch.status()
        elif batch_plan:result['follow_on']={'status':batch_plan.get('status','UNVERIFIED')}
    else:
        # Fence the continuation first so parent cleanup cannot race a new entry.
        batch_stop=batch.stop_entries() if batch else None
        result=operations.stop()
        if batch_stop:result['follow_on']=batch_stop
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        code=getattr(error,'response',{}).get('Error',{}).get('Code',type(error).__name__)
        print('PAPER_OPERATIONS_FAILED='+code)
        print('로그인 만료라면 CMD: aws login --profile stock-paper-operator --remote')
        print('계좌/키/토큰/원본 로그를 대화나 Git에 올리지 마세요.')
        raise SystemExit(1)
