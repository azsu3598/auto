"""Paper role permission contracts; this is not the AWS IAM simulator."""
import fnmatch
import json
from pathlib import Path
import unittest


INFRA = Path(__file__).resolve().parents[1] / "infra"


def allows_unconditional(document, action, resource):
    for statement in document["Statement"]:
        if statement.get("Condition"):
            continue
        actions = statement["Action"]
        actions = actions if isinstance(actions, list) else [actions]
        resources = statement["Resource"]
        resources = resources if isinstance(resources, list) else [resources]
        patterns = [p["Fn::Sub"] if isinstance(p, dict) else p for p in resources]
        if any(fnmatch.fnmatchcase(action.lower(), a.lower()) for a in actions) and any(
            fnmatch.fnmatchcase(resource, pattern) for pattern in patterns
        ):
            return statement["Effect"] == "Allow"
    return False


def arn(service, resource):
    return "arn:${AWS::Partition}:" + service + ":${AWS::Region}:${AWS::AccountId}:" + resource


class PaperAppPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = json.loads((INFRA / "paper-app-iam-bootstrap.yaml").read_text(encoding="utf-8"))
        cls.resources = cls.template["Resources"]

    def boundary(self, name):
        return self.resources[name + "Boundary"]["Properties"]["PolicyDocument"]

    def test_execution_can_read_only_demo_and_dart_secrets(self):
        boundary = self.boundary("Execution")
        for name, allowed in (("kiwoom-demo", True), ("dart", True), ("telegram", False),
                              ("kiwoom-live", False), ("real-account", False)):
            with self.subTest(name=name):
                self.assertEqual(allows_unconditional(boundary, "secretsmanager:GetSecretValue",
                    arn("secretsmanager", "secret:stock-automation-paper/" + name + "-ABC123")), allowed)

    def test_task_cannot_read_broker_secrets_or_modify_credentials(self):
        boundary = self.boundary("Task")
        telegram = arn("secretsmanager", "secret:stock-automation-paper/telegram-ABC123")
        self.assertTrue(allows_unconditional(boundary, "secretsmanager:GetSecretValue", telegram))
        self.assertFalse(allows_unconditional(boundary, "secretsmanager:PutSecretValue", telegram))
        self.assertFalse(allows_unconditional(boundary, "secretsmanager:GetSecretValue",
            arn("secretsmanager", "secret:stock-automation-paper/kiwoom-demo-ABC123")))
        self.assertFalse(allows_unconditional(boundary, "iam:CreateRole", "*"))

    def test_task_write_permission_does_not_extend_to_live_table_or_bucket(self):
        boundary = self.boundary("Task")
        for name in ("stock-automation-paper", "stock-automation-live", "other"):
            self.assertEqual(allows_unconditional(boundary, "dynamodb:PutItem",
                arn("dynamodb", "table/" + name)), name == "stock-automation-paper")
        self.assertFalse(allows_unconditional(boundary, "s3:PutObject", "arn:aws:s3:::unrelated-bucket/key"))

    def test_execution_cannot_pull_unrelated_image_or_write_unrelated_logs(self):
        boundary = self.boundary("Execution")
        self.assertTrue(allows_unconditional(boundary, "ecr:BatchGetImage", arn("ecr", "repository/stock-automation")))
        self.assertFalse(allows_unconditional(boundary, "ecr:BatchGetImage", arn("ecr", "repository/other")))
        self.assertFalse(allows_unconditional(boundary, "logs:PutLogEvents", arn("logs", "log-group:/other:*")))

    def test_scheduler_can_pass_only_two_named_ecs_roles_to_ecs(self):
        statements = self.boundary("Scheduler")["Statement"]
        self.assertEqual({a for s in statements for a in s["Action"]}, {"ecs:RunTask", "iam:PassRole"})
        run = next(s for s in statements if "ecs:RunTask" in s["Action"])
        self.assertEqual(run["Condition"]["ArnEquals"]["ecs:cluster"]["Fn::Sub"], arn("ecs", "cluster/stock-automation-paper"))
        passthrough = next(s for s in statements if "iam:PassRole" in s["Action"])
        self.assertEqual(passthrough["Condition"]["StringEquals"]["iam:PassedToService"], "ecs-tasks.amazonaws.com")
        self.assertEqual(len(passthrough["Resource"]), 2)

    def test_operator_has_no_credential_read_or_iam_edit_actions(self):
        doc = self.resources["OperatorAppPolicy"]["Properties"]["PolicyDocument"]
        actions = {a for s in doc["Statement"] for a in s["Action"]}
        self.assertEqual({a for a in actions if a.startswith("iam:")}, {"iam:PassRole"})
        self.assertFalse(any(a.startswith("secretsmanager:") for a in actions))
        deploy = next(s for s in doc["Statement"] if "cloudformation:CreateStack" in s["Action"])
        self.assertTrue(deploy["Condition"]["ArnEquals"]["cloudformation:RoleArn"]["Fn::Sub"].endswith(":role/stock-paper-app-deployer"))

    def test_deployer_requires_boundaries_and_cannot_remove_them(self):
        statements = self.resources["AppDeploymentRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        create = next(s for s in statements if "iam:CreateRole" in s["Action"])
        self.assertEqual(len(create["Resource"]), 3)
        self.assertEqual(len(create["Condition"]["ArnEquals"]["iam:PermissionsBoundary"]), 3)
        actions = {a for s in statements for a in s["Action"]}
        self.assertNotIn("iam:DeleteRolePermissionsBoundary", actions)
        self.assertNotIn("secretsmanager:GetSecretValue", actions)
        self.assertNotIn("s3:DeleteBucket", actions)
        self.assertNotIn("dynamodb:DeleteTable", actions)

    def test_absent_role_lookup_does_not_allow_unbounded_role_creation_or_policy_writes(self):
        statements = self.resources["AppDeploymentRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        fallback = next(s for s in statements if s["Sid"] == "InspectAbsentNamedRoles")
        self.assertEqual(len(fallback["Resource"]), 3)
        self.assertNotIn("iam:CreateRole", fallback["Action"])
        self.assertNotIn("iam:PutRolePolicy", fallback["Action"])
        cleanup = next(s for s in statements if s["Sid"] == "CleanFailedAbsentRolePolicies")
        self.assertEqual(len(cleanup["Resource"]), 3)
        for resource in cleanup["Resource"]:
            self.assertNotIn("*", resource["Fn::Sub"])
        operator = self.resources["OperatorAppPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        actions = {a for s in operator for a in s["Action"]}
        self.assertNotIn("s3:DeleteBucket", actions)
        self.assertNotIn("dynamodb:DeleteTable", actions)

    def test_task_definition_inspection_uses_supported_read_scope_without_global_deregistration(self):
        deploy = self.resources["AppDeploymentRole"]["Properties"]["Policies"][0]["PolicyDocument"]
        operator = self.resources["OperatorAppPolicy"]["Properties"]["PolicyDocument"]
        for document in (deploy, operator):
            actions = {a for s in document["Statement"] for a in s["Action"]}
            self.assertNotIn("ecs:DeregisterTaskDefinition", actions)
            reads = [s for s in document["Statement"] if "ecs:DescribeTaskDefinition" in s["Action"]]
            self.assertEqual(len(reads), 1)
            self.assertEqual(reads[0]["Resource"], "*")
            self.assertEqual(reads[0]["Action"], ["ecs:DescribeTaskDefinition"])
            self.assertEqual(reads[0]["Condition"]["StringEquals"]["aws:RequestedRegion"], "ap-northeast-2")


if __name__ == "__main__":
    unittest.main()
