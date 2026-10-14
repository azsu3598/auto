from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "prepare_fixed_egress", Path(__file__).resolve().parents[1] / "tools" / "prepare_fixed_egress.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FixedEgressPreparationTests(unittest.TestCase):
    def setUp(self):
        self.vpc = {"VpcId": "vpc-example", "CidrBlock": "10.77.0.0/16", "State": "available"}
        self.subnets = [
            {"VpcId": "vpc-example", "SubnetId": "subnet-a", "CidrBlock": "10.77.0.0/20", "AvailabilityZone": "ap-northeast-2a", "State": "available"},
            {"VpcId": "vpc-example", "SubnetId": "subnet-b", "CidrBlock": "10.77.16.0/20", "AvailabilityZone": "ap-northeast-2b", "State": "available"},
        ]
        self.routes = [{"VpcId": "vpc-example", "Associations": [{"Main": True}], "Routes": [
            {"DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-example", "State": "active"}
        ]}]
        self.gateways = [{"InternetGatewayId": "igw-example", "Attachments": [{"VpcId": "vpc-example", "State": "available"}]}]
        self.image = {"ImageId": "ami-example", "State": "available", "Architecture": "x86_64",
                      "ImageOwnerAlias": "amazon", "Name": "al2023-ami-2023.10-example-x86_64",
                      "RootDeviceType": "ebs", "RootDeviceName": "/dev/xvda",
                      "BlockDeviceMappings": [{"DeviceName": "/dev/xvda", "Ebs": {"VolumeSize": 8}}]}

    def select(self):
        return MODULE.select_network(self.vpc, self.subnets, self.routes, self.gateways)

    def test_existing_public_slash20s_are_not_overlapped(self):
        selected = self.select()
        self.assertEqual(selected["PrivateSubnetCidr"], "10.77.32.0/24")
        self.assertEqual(selected["AvailabilityZone"], "ap-northeast-2a")

    def test_explicit_private_route_overrides_public_main_table(self):
        self.routes.append({"VpcId": "vpc-example", "Associations": [{"SubnetId": "subnet-a"}], "Routes": []})
        self.assertEqual(self.select()["PublicSubnetId"], "subnet-b")

    def test_detached_gateway_and_blackhole_route_are_rejected(self):
        for field in ("gateway", "route"):
            with self.subTest(field=field):
                routes, gateways = copy.deepcopy(self.routes), copy.deepcopy(self.gateways)
                if field == "gateway": gateways[0]["Attachments"] = []
                else: routes[0]["Routes"][0]["State"] = "blackhole"
                with self.assertRaises(ValueError):
                    MODULE.select_network(self.vpc, self.subnets, routes, gateways)

    def test_full_vpc_and_foreign_subnet_are_rejected(self):
        self.subnets[0]["CidrBlock"] = "10.77.0.0/16"
        with self.assertRaises(ValueError): self.select()
        self.subnets[0]["VpcId"] = "vpc-other"
        with self.assertRaises(ValueError): self.select()

    def test_wrong_vpc_cidr_or_ambiguous_main_route_is_rejected(self):
        self.vpc["CidrBlock"] = "10.0.0.0/16"
        with self.assertRaises(ValueError): self.select()
        self.vpc["CidrBlock"] = "10.77.0.0/16"
        self.routes.append(copy.deepcopy(self.routes[0]))
        with self.assertRaises(ValueError): self.select()

    def test_approved_ami_and_disk_pass(self):
        MODULE.validate_ami(self.image, "ami-example")

    def test_wrong_architecture_owner_or_root_disk_is_rejected(self):
        for key, value in (("Architecture", "arm64"), ("ImageOwnerAlias", "other"),
                           ("Name", "ubuntu-example"), ("RootDeviceName", "/dev/sda1"), ("State", "pending")):
            with self.subTest(key=key):
                image = {**self.image, key: value}
                with self.assertRaises(ValueError): MODULE.validate_ami(image, "ami-example")
        image = copy.deepcopy(self.image)
        image["BlockDeviceMappings"][0]["Ebs"]["VolumeSize"] = 20
        with self.assertRaises(ValueError): MODULE.validate_ami(image, "ami-example")

    def test_wrong_profile_is_rejected_before_any_aws_request(self):
        class WrongSession:
            region_name = "ap-northeast-2"
            profile_name = "stock-paper"
            def client(self, name):
                raise AssertionError("Must not use alternate/root credentials")
        with self.assertRaises(ValueError): MODULE.collect_parameters(WrongSession())

    def fake_session(self, *, dns=True, identity=":user/stock-paper-operator"):
        testcase = self
        class Client:
            def get_caller_identity(self): return {"Arn": "arn:example" + identity}
            def describe_vpcs(self, **kwargs): return {"Vpcs": [testcase.vpc]}
            def describe_vpc_attribute(self, **kwargs):
                key = kwargs["Attribute"][0].upper() + kwargs["Attribute"][1:]
                return {key: {"Value": dns}}
            def describe_subnets(self, **kwargs): return {"Subnets": testcase.subnets}
            def describe_route_tables(self, **kwargs): return {"RouteTables": testcase.routes}
            def describe_internet_gateways(self, **kwargs): return {"InternetGateways": testcase.gateways}
            def get_parameter(self, **kwargs):
                testcase.assertEqual(kwargs, {"Name": MODULE.AMI_PARAMETER})
                return {"Parameter": {"Value": "ami-example"}}
            def describe_images(self, **kwargs):
                testcase.assertEqual(kwargs, {"ImageIds": ["ami-example"], "Owners": ["amazon"]})
                return {"Images": [testcase.image]}
        class Session:
            region_name = "ap-northeast-2"
            profile_name = "stock-paper-operator"
            def client(self, name): return Client()
        return Session()

    def test_inventory_collection_is_read_only_and_disables_all_schedules(self):
        # This client deliberately has no create/update/secret methods.
        values = {p["ParameterKey"]: p["ParameterValue"] for p in MODULE.collect_parameters(self.fake_session())}
        self.assertEqual(values["StartScheduleState"], "DISABLED")
        self.assertEqual(values["PrivateSubnetCidr"], "10.77.32.0/24")
        self.assertEqual(values["AmiId"], "ami-example")

    def test_missing_dns_or_wrong_identity_blocks_preparation(self):
        for session in (self.fake_session(dns=False), self.fake_session(identity=":root")):
            with self.assertRaises(ValueError): MODULE.collect_parameters(session)


if __name__ == "__main__":
    unittest.main()
