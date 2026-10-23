"""Offline template schema and deployment safety checks.

Install infra/requirements-validation.txt in a separate tools directory. This
does not call AWS, create resources, download schemas or submit package metadata.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from cfnlint.decode import decode
from cfnlint.runner import main as lint_main
from botocore.session import Session
from botocore.validate import validate_parameters


INFRA = Path(__file__).resolve().parents[1] / "infra"
TEMPLATE_NAMES = (
    "cloudformation.yaml", "paper-fixed-egress.yaml", "paper-network-iam-bootstrap.yaml",
    "paper-app-iam-bootstrap.yaml", "paper-control.yaml", "paper-timer-verification.yaml",
    "paper-web-dashboard.yaml", "paper-worker-verification.yaml", "paper-one-session-pilot.yaml",
    "paper-five-session-batch.yaml",
)


def validate() -> None:
    names = TEMPLATE_NAMES
    saved_args = sys.argv
    try:
        sys.argv = ["cfn-lint", "-r", "ap-northeast-2", "-t", *(str(INFRA / n) for n in names)]
        try:
            lint_main()
        except SystemExit as error:
            if error.code not in (None, 0):
                raise RuntimeError("CloudFormation schema/IAM lint failed") from error
    finally:
        sys.argv = saved_args
    templates = {}
    for name in names:
        template, errors = decode(str(INFRA / name))
        assert not errors, name
        templates[name] = template
    spec = importlib.util.spec_from_file_location("paper_batch_checks", Path(__file__).with_name("paper_batch_checks.py"))
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    checks.validate_batch_template(templates["paper-five-session-batch.yaml"])
    app = templates[names[0]]
    nat = templates[names[1]]
    iam = templates[names[2]]
    app_iam = templates[names[3]]
    control = templates[names[4]]
    assert control["Parameters"]["ScheduleState"]["AllowedValues"] == ["DISABLED"]
    function = control["Resources"]["ControlFunction"]["Properties"]
    assert function["MemorySize"] == 128 and function["Timeout"] == 600
    assert function["ReservedConcurrentExecutions"] == 2 and "VpcConfig" not in function
    control_actions = {a for s in control["Resources"]["ControlBoundary"]["Properties"]["PolicyDocument"]["Statement"] for a in s["Action"]}
    assert "ecs:RunTask" not in control_actions and "iam:PassRole" not in control_actions
    assert "s3:DeleteObject" not in control_actions and "dynamodb:DeleteTable" not in control_actions
    assert "kiwoom" not in json.dumps(control).lower()
    control_schedules = [r["Properties"] for r in control["Resources"].values() if r["Type"] == "AWS::Scheduler::Schedule"]
    assert len(control_schedules) == 6
    for schedule in control_schedules:
        assert schedule["State"] == {"Ref": "ScheduleState"}
        assert schedule["Target"]["RetryPolicy"]["MaximumRetryAttempts"] == 0
    assert "OnBootSec=120min" in json.dumps(nat)
    assert len(app_iam["Resources"]) == 5
    for logical, kind in (("ExecutionRole", "Execution"), ("TaskRole", "Task"), ("SchedulerRole", "Scheduler")):
        role = app["Resources"][logical]["Properties"]
        assert role["Path"] == "/stock-paper/"
        assert role["PermissionsBoundary"]["Fn::Sub"].endswith(f":policy/StockPaperApp{kind}Boundary")
    app_operator = app_iam["Resources"]["OperatorAppPolicy"]["Properties"]["PolicyDocument"]
    operator_text = json.dumps(app_operator)
    assert "secretsmanager:GetSecretValue" not in operator_text
    assert "iam:CreateRole" not in operator_text and "iam:PutRolePolicy" not in operator_text
    assert len(json.dumps(app_operator, separators=(",", ":"))) < 6144
    deployment = app_iam["Resources"]["AppDeploymentRole"]["Properties"]["Policies"][0]["PolicyDocument"]
    assert len(json.dumps(deployment, separators=(",", ":"))) < 10240
    assert "iam:DeleteRolePermissionsBoundary" not in json.dumps(deployment)
    for name in ("ExecutionBoundary", "TaskBoundary", "SchedulerBoundary"):
        boundary = app_iam["Resources"][name]["Properties"]["PolicyDocument"]
        assert len(json.dumps(boundary, separators=(",", ":"))) < 6144
    assert app["Parameters"]["AssignPublicIp"]["AllowedValues"] == ["DISABLED"]
    for logical in ("ArtifactBucket", "PaperTable", "TaskDefinition"):
        assert app["Resources"][logical]["DeletionPolicy"] == "Retain"
        assert app["Resources"][logical]["UpdateReplacePolicy"] == "Retain"
    for parameter in ("CoreScheduleState", "NxtScheduleState"):
        assert app["Parameters"][parameter]["Default"] == "DISABLED"
        assert app["Parameters"][parameter]["AllowedValues"] == ["DISABLED"]
    container = app["Resources"]["TaskDefinition"]["Properties"]["ContainerDefinitions"][0]
    assert container["User"] == "65534:65534" and container["ReadonlyRootFilesystem"] is True
    assert container["LinuxParameters"]["Capabilities"]["Drop"] == ["ALL"]
    assert {e["Name"]: e["Value"] for e in container["Environment"]}["LIVE_ORDER_ENABLED"] == "0"
    table_statements = app["Resources"]["TaskRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    required_transaction_actions = {"dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                                    "dynamodb:DeleteItem", "dynamodb:ConditionCheckItem"}
    transaction_policy = next(s for s in table_statements if "dynamodb:PutItem" in s.get("Action", []))
    assert required_transaction_actions.issubset(transaction_policy["Action"])
    assert transaction_policy["Resource"] == {"Fn::GetAtt": ["PaperTable", "Arn"]}
    assert "dynamodb:TransactWriteItems" not in transaction_policy["Action"]
    for resource in app["Resources"].values():
        if resource["Type"] == "AWS::Scheduler::Schedule":
            target = resource["Properties"]["Target"]
            payload = json.loads(target["Input"])
            validate_parameters(payload, Session().get_service_model("ecs").shape_for("TaskOverride"))
            env = payload["containerOverrides"][0]["environment"]
            assert {e["name"]: e["value"] for e in env}["SCHEDULED_AT"] == "<aws.scheduler.scheduled-time>"
            assert target["RetryPolicy"]["MaximumEventAgeInSeconds"] <= 300
            config = target["EcsParameters"]["NetworkConfiguration"]["AwsvpcConfiguration"]
            assert config["AssignPublicIp"] == {"Ref": "AssignPublicIp"}
    types = [r["Type"] for r in nat["Resources"].values()]
    assert types.count("AWS::EC2::Instance") == types.count("AWS::EC2::EIP") == 1
    assert not any(t in types for t in ("AWS::EC2::NatGateway", "AWS::RDS::DBInstance", "AWS::ECS::Service"))
    instance = nat["Resources"]["NatInstance"]["Properties"]
    assert instance["InstanceType"] == "t3.micro"
    assert instance["CreditSpecification"] == {"CPUCredits": "standard"}
    assert instance["MetadataOptions"]["HttpTokens"] == "required"
    assert instance["SourceDestCheck"] is False
    disk = instance["BlockDeviceMappings"][0]["Ebs"]
    assert disk["VolumeSize"] == 8 and disk["VolumeType"] == "gp3" and disk["Encrypted"] is True
    assert instance["InstanceInitiatedShutdownBehavior"] == "stop"
    userdata = instance["UserData"]["Fn::Base64"]["Fn::Sub"]
    assert userdata.index("systemctl enable --now paper-nat-stop.timer") < userdata.index("dnf install")
    assert "OnBootSec=120min" in userdata
    assert "timeout 600 dnf install" in userdata and "for attempt in 1 2; do" in userdata
    assert "iptables -P FORWARD DROP" in userdata
    assert nat["Parameters"]["StartScheduleState"]["Default"] == "DISABLED"
    for resource in nat["Resources"].values():
        if resource["Type"] == "AWS::Scheduler::Schedule":
            assert resource["Properties"]["State"] == {"Ref": "StartScheduleState"}
    ingress = nat["Resources"]["NatSecurityGroup"]["Properties"]["SecurityGroupIngress"]
    assert ingress == [{"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "CidrIp": {"Ref": "PrivateSubnetCidr"}}]
    serialized = json.dumps(iam)
    assert "secretsmanager:" not in serialized and "AdministratorAccess" not in serialized
    operator = iam["Resources"]["OperatorNetworkPolicy"]["Properties"]["PolicyDocument"]
    assert len(json.dumps(operator, separators=(",", ":"))) < 6144
    bootstrap_read = next(s for s in operator["Statement"] if s.get("Sid") == "InspectNetworkBootstrap")
    assert set(bootstrap_read["Action"]) == {"cloudformation:DescribeStacks", "cloudformation:GetTemplate"}
    assert bootstrap_read["Resource"]["Fn::Sub"].endswith(":stack/stock-automation-paper-network-iam/*")
    deployment_statements = iam["Resources"]["NetworkDeploymentRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    restart = next(s for s in deployment_statements if s.get("Sid") == "RestartOnlyApprovedNat")
    assert restart["Action"] == "ec2:StartInstances"
    assert restart["Resource"]["Fn::Sub"].endswith(":instance/*")
    assert restart["Condition"]["StringEquals"] == {"aws:RequestedRegion": "ap-northeast-2",
        "ec2:ResourceTag/Project": "paper-fixed-egress", "ec2:ResourceTag/Name": "stock-automation-paper-nat"}
    inspection = next(s for s in deployment_statements if s.get("Sid") == "InspectSeoulNetwork")
    # Typed CloudFormation AZ parameters require this read before resource creation.
    assert "ec2:DescribeAvailabilityZones" in inspection["Action"]
    cleanup = next(s for s in operator["Statement"] if "cloudformation:DeleteStack" in s.get("Action", []))
    assert all("/stock-automation-paper-network/" in r["Fn::Sub"]
               or ":changeSet/paper-network-" in r["Fn::Sub"] for r in cleanup["Resource"])
    for resource in iam["Resources"].values():
        if resource["Type"] == "AWS::IAM::Role":
            size = sum(len(json.dumps(p["PolicyDocument"], separators=(",", ":")))
                       for p in resource["Properties"].get("Policies", []))
            assert size < 10240
    print("CFN_SCHEMA_AND_IAM_LINT: PASS")
    print("PAPER_NETWORK_AND_CONTAINER_SAFETY: PASS")
    print(f"TEMPLATES_VALIDATED: {len(names)}; BATCH_BOUNDS_AND_PAPER_SAFETY: PASS")
    print("NO_AWS_CALLS; NO_RESOURCES_CREATED")


if __name__ == "__main__":
    validate()
