import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LockedLiveInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = json.loads((ROOT / "infra/live-locked.yaml").read_text(encoding="utf-8"))
        cls.resources = cls.t["Resources"]
        cls.container = cls.resources["TaskDefinition"]["Properties"]["ContainerDefinitions"][0]
        cls.env = {e["Name"]: e["Value"] for e in cls.container["Environment"]}

    def test_live_orders_are_locked_off_in_the_template(self):
        parameter = self.t["Parameters"]["LiveOrderEnabled"]
        self.assertEqual(["0"], parameter["AllowedValues"])
        self.assertEqual("0", parameter["Default"])
        self.assertEqual({"Ref": "LiveOrderEnabled"}, self.env["LIVE_ORDER_ENABLED"])
        self.assertEqual("real", self.env["KIWOOM_MODE"])

    def test_nothing_runs_automatically(self):
        types = {r["Type"] for r in self.resources.values()}
        for forbidden in ("AWS::Scheduler::Schedule", "AWS::Events::Rule", "AWS::ECS::Service",
                          "AWS::Lambda::Function", "AWS::EC2::Instance"):
            self.assertNotIn(forbidden, types)
        self.assertEqual(["--help"], self.container["Command"])

    def test_kill_switch_is_not_seeded_so_it_defaults_on(self):
        # DynamoLiveOrderStore.kill_switch_active treats a missing CONTROL#LIVE item as ON.
        self.assertNotIn("CONTROL#LIVE\"", json.dumps(self.t))
        self.assertNotIn("Custom::", json.dumps(self.t))

    def test_broker_secret_is_optional_and_only_injected_when_linked(self):
        parameter = self.t["Parameters"]["KiwoomRealSecretArn"]
        self.assertEqual("", parameter["Default"])
        self.assertIn("stock-automation-live/kiwoom-real-", parameter["AllowedPattern"])
        secrets = self.container["Secrets"]["Fn::If"]
        self.assertEqual("HasRealSecret", secrets[0])
        self.assertEqual({"Ref": "AWS::NoValue"}, secrets[2])
        self.assertEqual(
            {"APP_KEY", "APP_SECRET", "KIWOOM_ACCOUNT_NUMBER", "LIVE_ACCOUNT_FINGERPRINT_SALT",
             "LIVE_APPROVED_ACCOUNT_FINGERPRINT"},
            {s["Name"] for s in secrets[1]},
        )
        policies = self.resources["ExecutionRole"]["Properties"]["Policies"]["Fn::If"]
        self.assertEqual({"Ref": "AWS::NoValue"}, policies[2])
        self.assertNotIn("secretsmanager", json.dumps(self.resources["TaskRole"]))

    def test_task_role_is_limited_to_the_live_table_and_denies_the_paper_ledger(self):
        statements = self.resources["TaskRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        allows = [s for s in statements if s["Effect"] == "Allow"]
        for statement in allows:
            self.assertEqual({"Fn::GetAtt": ["LiveOrderTable", "Arn"]}, statement["Resource"])
        actions = {a for s in allows for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])}
        self.assertEqual({"dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                          "dynamodb:ConditionCheckItem", "dynamodb:Scan", "dynamodb:DeleteItem"}, actions)
        delete = next(s for s in allows if s["Action"] == "dynamodb:DeleteItem")
        self.assertEqual(["CONTROL#LIVE_EXECUTION_LOCK"],
                         delete["Condition"]["ForAllValues:StringEquals"]["dynamodb:LeadingKeys"])
        deny = next(s for s in statements if s["Effect"] == "Deny")
        self.assertIn("table/stock-automation-paper", json.dumps(deny["Resource"]))
        self.assertIn("stock-automation-paper-*", json.dumps(deny["Resource"]))
        self.assertNotIn("stock-automation-paper", json.dumps(allows))
        text = json.dumps(self.t)
        for forbidden in ("iam:PassRole", "ecs:RunTask", "s3:PutObject", "sns:Publish"):
            self.assertNotIn(forbidden, text)

    def test_live_ledger_is_separate_retained_and_recoverable(self):
        table = self.resources["LiveOrderTable"]
        self.assertEqual("stock-automation-live", table["Properties"]["TableName"])
        self.assertEqual("Retain", table["DeletionPolicy"])
        self.assertTrue(table["Properties"]["DeletionProtectionEnabled"])
        self.assertTrue(table["Properties"]["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"])
        self.assertEqual({"Ref": "LiveOrderTable"}, self.env["LIVE_ORDER_TABLE"])

    def test_limits_cannot_be_raised_above_reviewed_defaults(self):
        parameters = self.t["Parameters"]
        for name, env_name in (("MaxOrderAmount", "LIVE_MAX_ORDER_AMOUNT"),
                               ("MaxTotalExposure", "LIVE_MAX_TOTAL_EXPOSURE"),
                               ("MaxDailyLoss", "LIVE_MAX_DAILY_LOSS"),
                               ("MaxOpenPositions", "LIVE_MAX_OPEN_POSITIONS"),
                               ("MaxDailyBuyOrdersPerCode", "LIVE_MAX_DAILY_BUY_ORDERS_PER_CODE")):
            self.assertEqual(parameters[name]["Default"], parameters[name]["MaxValue"])
            self.assertEqual({"Ref": name}, self.env[env_name])

    def test_container_is_hardened_like_the_paper_task(self):
        self.assertEqual("65534:65534", self.container["User"])
        self.assertTrue(self.container["ReadonlyRootFilesystem"])
        self.assertEqual(["ALL"], self.container["LinuxParameters"]["Capabilities"]["Drop"])


if __name__ == "__main__":
    unittest.main()
