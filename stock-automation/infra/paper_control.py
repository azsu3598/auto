"""Bounded network control and sanitized task-failure alerts; no broker access."""
import json
import hashlib
import ipaddress
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

KST = timezone(timedelta(hours=9))
WINDOWS = {"morning": ((8, 55), (9, 25)), "afternoon": ((14, 40), (16, 10)),
           "saturday": ((7, 50), (8, 40))}
CODE_MEANINGS = {
    "NETWORK_CONTROL_FAILED": "의미: 중계 서버(네트워크) 켜기·끄기를 확인하지 못했습니다. "
        "서버가 켜진 채 남았는지 status 명령으로 확인하세요. 독립 정지 예약은 계속 동작합니다.",
    "TASK_CLEANUP_RECONCILE_REQUIRED": "의미: 정해진 시간 안에 끝나지 않은 분석 작업을 강제로 정리했습니다. "
        "가상 장부가 중간 상태일 수 있어 대사(장부 확인)가 필요합니다.",
    "ECS_TASK_FAILED_RECONCILE_REQUIRED": "의미: 분석 작업이 오류로 종료되었습니다. "
        "해당 단계 결과와 가상 장부를 확인하기 전에는 다시 실행하지 마세요.",
}


def validate_event(event, now):
    action = event.get("action")
    if action in ("VERIFY_START", "VERIFY_STOP"):
        if not event.get("test_id"):
            raise ValueError("TEST_ID_REQUIRED")
        return action.removeprefix("VERIFY_"), "manual-" + str(event["test_id"]), now + timedelta(minutes=110)
    if action not in ("START", "STOP") or event.get("window") not in WINDOWS:
        raise ValueError("UNSUPPORTED_CONTROL_EVENT")
    occurrence = datetime.fromisoformat(event["scheduled_at"])
    if occurrence.tzinfo is None:
        raise ValueError("CONTROL_TIMEZONE_REQUIRED")
    occurrence = occurrence.astimezone(KST)
    window = event["window"]
    hm = WINDOWS[window][action == "STOP"]
    if (occurrence.hour, occurrence.minute, occurrence.second, occurrence.microsecond) != (*hm, 0, 0):
        raise ValueError("WRONG_CONTROL_OCCURRENCE")
    if (occurrence.weekday() == 5 if window == "saturday" else occurrence.weekday() < 5) is False:
        raise ValueError("WRONG_CONTROL_DAY")
    if not occurrence <= now <= occurrence + timedelta(seconds=180 if action == "START" else 300):
        raise ValueError("EXPIRED_OR_EARLY_CONTROL_EVENT")
    stop = occurrence.replace(hour=WINDOWS[window][1][0], minute=WINDOWS[window][1][1])
    return action, window + "-" + occurrence.isoformat(), stop


class Controller:
    def __init__(self, *, clients=None, env=None, clock=None, sleep=None):
        self.env = env if env is not None else os.environ
        self.clock = clock or (lambda: datetime.now(KST))
        self.sleep = sleep or time.sleep
        self.clients = clients or {n: boto3.client(n, config=Config(connect_timeout=3, read_timeout=8, retries={"max_attempts": 1}))
                                  for n in ("ec2", "ecs", "ssm", "s3", "dynamodb", "secretsmanager")}
        self.bucket = self.env["PAPER_BUCKET"]
        self.table = self.env["PAPER_TABLE"]
        self.instance_id = self.env["NAT_INSTANCE_ID"]
        self.cluster = self.env["PAPER_CLUSTER"]
        self.started_here = False
        self.stop_authorized = False
        if not ipaddress.ip_network(self.env["PRIVATE_SUBNET_CIDR"]).is_private:
            raise ValueError("PRIVATE_SUBNET_REQUIRED")

    def instance(self):
        vm = self.clients["ec2"].describe_instances(InstanceIds=[self.instance_id])["Reservations"][0]["Instances"][0]
        tags = {x["Key"]: x["Value"] for x in vm.get("Tags", [])}
        if tags.get("Project") != "paper-fixed-egress" or tags.get("Name") != "stock-automation-paper-nat" or vm["SourceDestCheck"]:
            raise ValueError("NAT_IDENTITY_CHANGED")
        return vm

    def mark(self, state, **extra):
        body = {"state": state, "instance_id": self.instance_id, "recorded_at": self.clock().isoformat(), **extra}
        self.clients["s3"].put_object(Bucket=self.bucket, Key="control/network/current.json",
            Body=json.dumps(body).encode(), ContentType="application/json")

    def notify(self, code):
        # Never include event bodies, task IDs, environment, stderr or raw exceptions.
        secret = self.clients["secretsmanager"].get_secret_value(SecretId=self.env["NOTIFICATION_SECRET_ARN"])
        credentials = json.loads(secret["SecretString"])
        payload = json.dumps({"chat_id": credentials["chat_id"],
            "text": "[SABU 모의환경] 안전장치 알림: " + code + ". 원장 확인 전 재실행하지 마세요.\n"
                + CODE_MEANINGS.get(code, "의미: 분류되지 않은 제어 오류입니다. status 명령으로 상태를 확인하세요.")
                + "\n※ 실제 계좌 주문과 무관한 모의환경 서버 제어 알림입니다."}).encode()
        request = urllib.request.Request("https://api.telegram.org/bot" + credentials["bot_token"] + "/sendMessage",
            data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=6) as response:
            if json.loads(response.read()).get("ok") is not True:
                raise ValueError("NOTIFICATION_REJECTED")

    def tasks(self):
        # RUNNING desired status includes provisioning tasks; also inspect STOPPED
        # desired status tasks that may still be deprovisioning before stopping NAT.
        active = []
        for desired in ("RUNNING", "STOPPED"):
            token = None
            while True:
                args = {"cluster": self.cluster, "desiredStatus": desired, "maxResults": 100}
                if token: args["nextToken"] = token
                response = self.clients["ecs"].list_tasks(**args)
                arns = response["taskArns"]
                if arns:
                    rows = self.clients["ecs"].describe_tasks(cluster=self.cluster, tasks=arns)
                    if rows.get("failures"): raise ValueError("TASK_INSPECTION_FAILED")
                    active.extend(x for x in rows["tasks"] if x["lastStatus"] != "STOPPED")
                token = response.get("nextToken")
                if not token: break
        return {x["taskArn"]: x for x in active}

    def start(self, expires):
        vm = self.instance()
        # A new start never reuses an earlier proof, including failed readiness.
        if vm["State"]["Name"] != "stopped":
            raise ValueError("NAT_NOT_STOPPED_BEFORE_START")
        self.mark("STARTING")
        self.started_here = True
        self.clients["ec2"].start_instances(InstanceIds=[self.instance_id])
        for _ in range(24):
            vm = self.instance()
            if vm["State"]["Name"] == "running": break
            self.sleep(3)
        else: raise ValueError("NAT_START_TIMEOUT")
        # A new command invocation checks the current kernel/rules/timer, not a file
        # left on disk by a previous boot. No host secret or new host IAM is needed.
        command = """set -eu
test "$(sysctl -n net.ipv4.ip_forward)" = 1
iface=$(ip -4 route show default | awk '{print $5; exit}')
test -n "$iface"
iptables -S FORWARD | grep -q -- '-P FORWARD DROP'
iptables -C FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -C FORWARD -s PRIVATE_CIDR -o "$iface" -p tcp --dport 443 -m conntrack --ctstate NEW -j ACCEPT
iptables -t nat -C POSTROUTING -s PRIVATE_CIDR -o "$iface" -p tcp --dport 443 -j MASQUERADE
systemctl is-active --quiet iptables
systemctl is-active --quiet paper-nat-stop.timer
systemctl is-enabled --quiet paper-nat-stop.timer
systemctl show paper-nat-stop.timer -p TimersMonotonic | grep -q 'OnBootUSec=2h'
echo PAPER_BOOT_VERIFIED
""".replace("PRIVATE_CIDR", self.env["PRIVATE_SUBNET_CIDR"])
        for _ in range(24):
            rows = self.clients["ssm"].describe_instance_information(Filters=[{"Key":"InstanceIds","Values":[self.instance_id]}])["InstanceInformationList"]
            if rows and rows[0]["PingStatus"] == "Online": break
            self.sleep(3)
        else: raise ValueError("SSM_START_TIMEOUT")
        sent = self.clients["ssm"].send_command(InstanceIds=[self.instance_id], DocumentName="AWS-RunShellScript",
            Parameters={"commands":[command],"executionTimeout":["45"]}, TimeoutSeconds=60)
        for _ in range(20):
            try:
                result = self.clients["ssm"].get_command_invocation(CommandId=sent["Command"]["CommandId"],InstanceId=self.instance_id)
            except Exception as error:
                if getattr(error,"response",{}).get("Error",{}).get("Code") != "InvocationDoesNotExist": raise
                result={"Status":"Pending"}
            if result["Status"] not in ("Pending","InProgress","Delayed"): break
            self.sleep(3)
        if result["Status"] != "Success" or "PAPER_BOOT_VERIFIED" not in result.get("StandardOutputContent",""):
            raise ValueError("CURRENT_BOOT_NOT_READY")
        # Pin to the same start that was checked; another stop/start invalidates it.
        current = self.instance()
        if current["State"]["Name"] != "running" or current["LaunchTime"] != vm["LaunchTime"]:
            raise ValueError("BOOT_CHANGED_DURING_READINESS")
        deadline=min(expires,vm["LaunchTime"]+timedelta(minutes=120))
        if self.clock() >= deadline: raise ValueError("READINESS_TOO_LATE")
        self.mark("READY",launch_time=vm["LaunchTime"].isoformat(),ready_at=self.clock().isoformat(),expires_at=deadline.isoformat())
        return {"state":"READY"}

    def stop(self):
        self.instance()
        self.stop_authorized = True
        self.mark("CLOSING")  # Block new workers before waiting for old ones.
        active={}
        for _ in range(12):
            active=self.tasks()
            if not active: break
            self.sleep(5)
        forced=bool(active)
        if active:
            for task in active:
                self.clients["ecs"].stop_task(cluster=self.cluster,task=task,reason="Bounded paper network cleanup")
            for _ in range(12):
                active=self.tasks()
                if not active: break
                self.sleep(5)
        # Even failed task cleanup cannot extend NAT indefinitely. Keep a durable
        # reconciliation marker, notify externally, then respect the network bound.
        self.mark("CLEANUP_FAILED" if active else "STOPPING",forced_cleanup=forced)
        self.clients["ec2"].stop_instances(InstanceIds=[self.instance_id])
        if forced: self.notify("TASK_CLEANUP_RECONCILE_REQUIRED")
        return {"state":"STOP_REQUESTED","forced_cleanup":forced,"cleanup_complete":not bool(active)}

    def handle(self,event):
        # Only the filtered EventBridge rule can invoke this path. Reject unrelated
        # clusters/states even if someone accidentally broadens that rule later.
        if event.get("source") == "aws.ecs":
            detail=event.get("detail",{})
            if detail.get("clusterArn")!=self.cluster or detail.get("lastStatus")!="STOPPED":
                return {"state":"IGNORED"}
            containers=detail.get("containers",[])
            failed=detail.get("stopCode") in ("TaskFailedToStart","UserInitiated") or not containers or any(x.get("exitCode")!=0 for x in containers)
            if failed:
                event_key=hashlib.sha256((detail.get("taskArn","")+detail.get("stoppedAt","")).encode()).hexdigest()
                try:
                    self.clients["dynamodb"].put_item(TableName=self.table,Item={"pk":{"S":"CONTROL#ALERT#"+event_key},"status":{"S":"CLAIMED"}},ConditionExpression="attribute_not_exists(pk)")
                except Exception as error:
                    if getattr(error,"response",{}).get("Error",{}).get("Code")=="ConditionalCheckFailedException":return {"state":"DUPLICATE_BLOCKED"}
                    raise
                self.notify("ECS_TASK_FAILED_RECONCILE_REQUIRED")
            return {"state":"ALERTED" if failed else "IGNORED"}
        action,key,expires=validate_event(event,self.clock())
        if action=="START" and not event["action"].startswith("VERIFY_"):
            from stock_automation.calendar import TradingCalendar
            raw=self.clients["s3"].get_object(Bucket=self.bucket,Key="config/calendar/current.json")["Body"].read()
            calendar=TradingCalendar.from_dict(json.loads(raw))
            if event["window"]=="saturday":
                if not calendar.automatic_schedule_eligible or calendar.reviewed_through is None or self.clock().date()>calendar.reviewed_through:
                    raise ValueError("CALENDAR_NOT_APPROVED")
            else:
                if not calendar.is_trading_day(self.clock().date()) or self.clock().date() in calendar.special_sessions:
                    return {"state":"SKIPPED_NONSTANDARD_OR_CLOSED_SESSION"}
                calendar.require_automatic_session(self.clock().date())
        ddb=self.clients["dynamodb"]
        try:
            ddb.put_item(TableName=self.table,Item={"pk":{"S":"CONTROL#NETWORK#"+action+"#"+key},"status":{"S":"STARTED"}},
                ConditionExpression="attribute_not_exists(pk)")
        except Exception as error:
            if getattr(error,"response",{}).get("Error",{}).get("Code")=="ConditionalCheckFailedException":
                return {"state":"DUPLICATE_BLOCKED"}
            raise
        try:
            return self.start(expires) if action=="START" else self.stop()
        except Exception:
            if action=="START" and self.started_here:
                try:self.mark("FAILED")
                finally:self.clients["ec2"].stop_instances(InstanceIds=[self.instance_id])
            elif action=="STOP" and self.stop_authorized:
                # Failed inspection must not remove the independent 120-minute timer.
                self.clients["ec2"].stop_instances(InstanceIds=[self.instance_id])
            try:self.notify("NETWORK_CONTROL_FAILED")
            except Exception:print(json.dumps({"status":"ALERT_DELIVERY_FAILED","paper_only":True}))
            raise ValueError("NETWORK_CONTROL_FAILED") from None


def handler(event,context):
    # Raw event/exception content is never logged or returned to a caller.
    try:
        result=Controller().handle(event)
    except Exception as error:
        print(json.dumps({"status":"CONTROL_REJECTED_OR_FAILED","reason":type(error).__name__,"paper_only":True}))
        raise ValueError("CONTROL_REJECTED_OR_FAILED") from None
    print(json.dumps(result))
    return result
