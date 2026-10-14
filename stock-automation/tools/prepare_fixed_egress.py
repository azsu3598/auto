"""Read AWS inventory and prepare private parameters; never create resources.

Run with the dedicated paper operator. Account IDs, network IDs and the selected
AMI stay in the ignored runtime directory. No secret values are requested.
"""
from __future__ import annotations

import ipaddress
import json
import logging
from pathlib import Path


REGION = "ap-northeast-2"
PROFILE = "stock-paper-operator"
AMI_PARAMETER = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
ROOT = Path(__file__).resolve().parents[2]


def select_network(vpc: dict, subnets: list[dict], route_tables: list[dict], gateways: list[dict]) -> dict:
    """Select an existing public subnet and an unused /24 in the paper VPC."""
    if vpc.get("State") != "available" or vpc.get("CidrBlock") != "10.77.0.0/16":
        raise ValueError("Unexpected paper VPC configuration")
    vpc_id = vpc["VpcId"]
    if not subnets or any(s.get("VpcId") != vpc_id or s.get("State") != "available" for s in subnets):
        raise ValueError("Subnets must be available in the selected VPC")
    active_gateways = {
        g["InternetGatewayId"] for g in gateways
        if any(a.get("VpcId") == vpc_id and a.get("State") == "available" for a in g.get("Attachments", []))
    }
    tables = [t for t in route_tables if t.get("VpcId") == vpc_id]
    public = []
    for subnet in subnets:
        explicit = [t for t in tables if any(a.get("SubnetId") == subnet["SubnetId"] for a in t.get("Associations", []))]
        effective = explicit or [t for t in tables if any(a.get("Main") is True for a in t.get("Associations", []))]
        if len(effective) != 1:
            raise ValueError("Cannot uniquely determine a subnet route table")
        if any(r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("State") == "active"
               and r.get("GatewayId") in active_gateways for r in effective[0].get("Routes", [])):
            public.append(subnet)
    if not public:
        raise ValueError("No verified public subnet connected to the VPC internet gateway")
    chosen = min(public, key=lambda s: (s["AvailabilityZone"], s["SubnetId"]))
    network = ipaddress.ip_network(vpc["CidrBlock"])
    occupied = [ipaddress.ip_network(s["CidrBlock"]) for s in subnets]
    if any(not n.subnet_of(network) for n in occupied):
        raise ValueError("Subnet CIDR lies outside the paper VPC")
    # Existing public subnets are /20; checking only equal CIDRs would miss overlap.
    private = next((n for n in network.subnets(new_prefix=24) if not any(n.overlaps(o) for o in occupied)), None)
    if private is None:
        raise ValueError("No unused private /24 in the paper VPC")
    return {
        "VpcId": vpc_id,
        "PublicSubnetId": chosen["SubnetId"],
        "AvailabilityZone": chosen["AvailabilityZone"],
        "PrivateSubnetCidr": str(private),
    }


def validate_ami(image: dict, ami_id: str) -> None:
    """Reject another OS/architecture or a disk larger than the approved 8 GiB."""
    if (image.get("ImageId") != ami_id or image.get("State") != "available"
            or image.get("Architecture") != "x86_64" or image.get("ImageOwnerAlias") != "amazon"
            or not image.get("Name", "").startswith("al2023-ami-2023.")
            or image.get("RootDeviceType") != "ebs" or image.get("RootDeviceName") != "/dev/xvda"):
        raise ValueError("Expected an available Amazon-owned AL2023 x86_64 EBS image")
    roots = [d.get("Ebs", {}) for d in image.get("BlockDeviceMappings", []) if d.get("DeviceName") == "/dev/xvda"]
    if len(roots) != 1 or not 0 < roots[0].get("VolumeSize", 0) <= 8:
        raise ValueError("AMI root volume exceeds the approved disk assumption")


def collect_parameters(session) -> list[dict]:
    if session.region_name != REGION or session.profile_name != PROFILE:
        raise ValueError("Use the Seoul paper operator profile only")
    identity = session.client("sts").get_caller_identity()
    if not identity["Arn"].endswith(":user/stock-paper-operator"):
        raise ValueError("Unexpected AWS identity")
    ec2 = session.client("ec2")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": ["stock-automation-paper-vpc"]}])["Vpcs"]
    if len(vpcs) != 1:
        raise ValueError("Expected exactly one named paper VPC")
    vpc = vpcs[0]
    for attribute in ("enableDnsSupport", "enableDnsHostnames"):
        response = ec2.describe_vpc_attribute(VpcId=vpc["VpcId"], Attribute=attribute)
        key = attribute[0].upper() + attribute[1:]
        if response.get(key, {}).get("Value") is not True:
            raise ValueError("Both VPC DNS settings must be enabled")
    filters = [{"Name": "vpc-id", "Values": [vpc["VpcId"]]}]
    subnets = ec2.describe_subnets(Filters=filters)["Subnets"]
    routes = ec2.describe_route_tables(Filters=filters)["RouteTables"]
    gateways = ec2.describe_internet_gateways(Filters=[{"Name": "attachment.vpc-id", "Values": [vpc["VpcId"]]}])["InternetGateways"]
    selected = select_network(vpc, subnets, routes, gateways)
    ami_id = session.client("ssm").get_parameter(Name=AMI_PARAMETER)["Parameter"]["Value"]
    images = ec2.describe_images(ImageIds=[ami_id], Owners=["amazon"])["Images"]
    if len(images) != 1:
        raise ValueError("Amazon Linux AMI lookup is incomplete")
    validate_ami(images[0], ami_id)
    selected.update(AmiId=ami_id, StartScheduleState="DISABLED")
    return [{"ParameterKey": key, "ParameterValue": value} for key, value in selected.items()]


def main() -> int:
    # truststore must be injected before importing boto3 on this Windows setup.
    import truststore
    truststore.inject_into_ssl()
    for name in ("boto3", "botocore", "urllib3"):
        logging.getLogger(name).disabled = True
    import boto3
    from botocore.exceptions import ClientError
    try:
        parameters = collect_parameters(boto3.Session(profile_name=PROFILE, region_name=REGION))
        directory = ROOT / "runtime"
        directory.mkdir(exist_ok=True)
        destination = directory / "paper-network-parameters.json"
        if destination.exists():
            raise ValueError("Existing parameters preserved; review them before regenerating")
        destination.write_text(json.dumps(parameters, indent=2), encoding="utf-8")
        print("NETWORK_PARAMETERS_READY: runtime/paper-network-parameters.json")
        print("READ_ONLY_CHECKS_PASSED; ALL_SCHEDULES_DISABLED; NO_RESOURCES_CREATED")
        return 0
    except ClientError as error:
        print("AWS_CHECK_FAILED:", error.response["Error"]["Code"])
    except Exception as error:
        print("NETWORK_PREPARATION_FAILED:", type(error).__name__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
