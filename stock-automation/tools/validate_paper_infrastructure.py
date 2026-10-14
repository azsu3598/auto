"""Offline template schema and deployment safety checks.

Install infra/requirements-validation.txt in a separate tools directory. This
does not call AWS, create resources, download schemas or submit package metadata.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from cfnlint.decode import decode
from cfnlint.runner import main as lint_main


INFRA = Path(__file__).resolve().parents[1] / "infra"


def validate() -> None:
    names = ["cloudformation.yaml", "paper-fixed-egress.yaml", "paper-network-iam-bootstrap.yaml"]
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
    app = templates[names[0]]
    nat = templates[names[1]]
    iam = templates[names[2]]
    assert app["Parameters"]["AssignPublicIp"]["AllowedValues"] == ["DISABLED"]
    for parameter in ("CoreScheduleState", "NxtScheduleState"):
        assert app["Parameters"][parameter]["Default"] == "DISABLED"
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
            config = resource["Properties"]["Target"]["EcsParameters"]["NetworkConfiguration"]["AwsvpcConfiguration"]
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
    for resource in iam["Resources"].values():
        if resource["Type"] == "AWS::IAM::Role":
            size = sum(len(json.dumps(p["PolicyDocument"], separators=(",", ":")))
                       for p in resource["Properties"].get("Policies", []))
            assert size < 10240
    print("CFN_SCHEMA_AND_IAM_LINT: PASS")
    print("PAPER_NETWORK_AND_CONTAINER_SAFETY: PASS")
    print("NO_AWS_CALLS; NO_RESOURCES_CREATED")


if __name__ == "__main__":
    validate()
