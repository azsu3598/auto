import ast
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_paper_batch import build_plan


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checks = load("batch_checks_test", "paper_batch_checks.py")
builder = load("batch_checked_builder_test", "build_paper_batch_template.py")


class BatchChecksTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "stack_name": "stock-automation-paper-batch-v2", "batch_plan": build_plan(),
            "parameters": {
                "PilotId": "b" * 32,
                "PmStart": "2026-10-25T15:00:00.000Z", "PmEnd": "2026-10-30T14:59:59.999Z",
                "AmStart": "2026-10-26T15:00:00.000Z", "AmEnd": "2026-11-02T14:59:59.999Z",
            },
        }
        self.template = builder.build()

    def test_real_plan_and_all_ten_templates_are_checked_without_mutation(self):
        original = copy.deepcopy(self.document)
        checks.validate_operational_plan(self.document)
        checks.validate_batch_template(self.template)
        self.assertEqual(self.document, original)
        tree = ast.parse((ROOT / "tools/validate_paper_infrastructure.py").read_text(encoding="utf-8"))
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "TEMPLATE_NAMES" for target in node.targets))
        names = ast.literal_eval(assignment.value)
        self.assertEqual(set(names), {path.name for path in (ROOT / "infra").glob("*.yaml")})
        self.assertEqual(len(names), len(set(names)))

    def test_each_real_bound_rejects_wrong_format_and_impossible_dates(self):
        for name in ("PmStart", "PmEnd", "AmStart", "AmEnd"):
            for value in (None, 123, "not-a-date", "2026-10-25T15:00:00Z",
                          "2026-10-25T15:00:00.000+00:00", "2026-02-30T15:00:00.000Z"):
                with self.subTest(name=name, value=value):
                    document = copy.deepcopy(self.document)
                    document["parameters"][name] = value
                    with self.assertRaises(ValueError):
                        checks.validate_operational_plan(document)

    def test_reversed_windows_are_rejected(self):
        for window in ("Pm", "Am"):
            document = copy.deepcopy(self.document)
            params = document["parameters"]
            params[window + "Start"], params[window + "End"] = params[window + "End"], params[window + "Start"]
            with self.assertRaisesRegex(ValueError, "BOUNDS_REVERSED"):
                checks.validate_operational_plan(document)

    def test_windows_cannot_include_an_extra_unapproved_date(self):
        for name, value in (("PmStart", "2026-10-24T15:00:00.000Z"), ("PmEnd", "2026-10-31T14:59:59.999Z"),
                            ("AmStart", "2026-10-25T15:00:00.000Z"), ("AmEnd", "2026-11-03T14:59:59.999Z")):
            document = copy.deepcopy(self.document)
            document["parameters"][name] = value
            with self.assertRaisesRegex(ValueError, "OUTSIDE_APPROVED"):
                checks.validate_operational_plan(document)

    def test_bounds_cover_gate_reports_and_both_independent_stops(self):
        for name, value in (("PmStart", "2026-10-26T00:45:00.001Z"), ("PmEnd", "2026-10-30T07:19:59.999Z"),
                            ("AmStart", "2026-10-26T23:55:00.001Z"), ("AmEnd", "2026-11-02T00:39:59.999Z")):
            document = copy.deepcopy(self.document)
            document["parameters"][name] = value
            with self.assertRaisesRegex(ValueError, "COVER_ALL_EVENTS"):
                checks.validate_operational_plan(document)

    def test_engine_calendar_identity_and_paper_only_guards_are_reused(self):
        mutations = (
            lambda d: d.update(stack_name="another-stack"),
            lambda d: d["parameters"].update(PilotId="c" * 32),
            lambda d: d["batch_plan"].update(paper_only=False),
            lambda d: d["batch_plan"]["sessions"].pop(),
            lambda d: d["batch_plan"]["sessions"][4].update(exit_date="2026-11-03"),
        )
        for mutate in mutations:
            document = copy.deepcopy(self.document)
            mutate(document)
            with self.assertRaises(ValueError):
                checks.validate_operational_plan(document)

    def test_template_rejects_missing_date_constraints(self):
        for name in ("PmStart", "PmEnd", "AmStart", "AmEnd"):
            template = copy.deepcopy(self.template)
            template["Parameters"][name] = {"Type": "Number"}
            with self.assertRaisesRegex(ValueError, "TIMESTAMP_CONSTRAINT"):
                checks.validate_batch_template(template)

    def test_template_rejects_live_flag_and_container_isolation_regression(self):
        template = copy.deepcopy(self.template)
        container = template["Resources"]["PilotTask"]["Properties"]["ContainerDefinitions"][0]
        next(item for item in container["Environment"] if item["Name"] == "LIVE_ORDER_ENABLED")["Value"] = "1"
        with self.assertRaisesRegex(ValueError, "DEMO_LIVE0"):
            checks.validate_batch_template(template)
        template = copy.deepcopy(self.template)
        template["Resources"]["PilotTask"]["Properties"]["ContainerDefinitions"][0]["ReadonlyRootFilesystem"] = False
        with self.assertRaisesRegex(ValueError, "ISOLATION"):
            checks.validate_batch_template(template)

    def test_template_rejects_missing_stop_widened_schedule_or_mutation_permission(self):
        mutations = (
            lambda t: t["Resources"].pop("FallbackPmSchedule"),
            lambda t: t["Resources"]["GateSchedule"]["Properties"].pop("EndDate"),
            lambda t: t["Parameters"]["PilotState"].update(Default="ENABLED"),
            lambda t: t["Resources"]["Boundary"]["Properties"]["PolicyDocument"]["Statement"].append(
                {"Effect": "Allow", "Action": ["scheduler:UpdateSchedule"], "Resource": "*"}),
        )
        for mutate in mutations:
            template = copy.deepcopy(self.template)
            mutate(template)
            with self.assertRaises((ValueError, KeyError)):
                checks.validate_batch_template(template)

    def test_saved_template_matches_builder_exactly(self):
        saved = json.loads((ROOT / "infra/paper-five-session-batch.yaml").read_text(encoding="utf-8"))
        self.assertEqual(saved, self.template)

    def test_wildcard_or_string_action_cannot_bypass_mutation_guard(self):
        for action in ("scheduler:UpdateSchedule", "scheduler:*", "DYNAMODB:*", "*"):
            template = copy.deepcopy(self.template)
            template["Resources"]["Boundary"]["Properties"]["PolicyDocument"]["Statement"].append(
                {"Effect": "Allow", "Action": action, "Resource": "*"})
            with self.assertRaisesRegex(ValueError, "MUTATION_PERMISSION"):
                checks.validate_batch_template(template)

    def test_cli_accepts_valid_plan_without_aws_calls_or_printing_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(self.document), encoding="utf-8")
            with patch.object(sys, "argv", ["checks", "--plan", str(path)]), patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(checks.main(), 0)
                self.assertEqual(output.getvalue(), "BATCH_PLAN_AND_SCHEDULE_BOUNDS: PASS; NO_AWS_CALLS; NO_MUTATIONS\n")

    def test_engine_import_does_not_replace_existing_pilot_module(self):
        existing = sys.modules.get("paper_pilot")
        checks.validate_operational_plan(self.document)
        self.assertIs(sys.modules.get("paper_pilot"), existing)
        self.document["batch_plan"]["paper_only"] = False
        with self.assertRaises(ValueError):
            checks.validate_operational_plan(self.document)
        self.assertIs(sys.modules.get("paper_pilot"), existing)

    def test_cli_prints_only_safe_failure_code_not_private_plan_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            # Fixture output, never a real runtime plan or credential.
            bad = copy.deepcopy(self.document)
            bad["parameters"]["PmStart"] = "PRIVATE_INPUT_MUST_NOT_BE_PRINTED"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with patch.object(sys, "argv", ["checks", "--plan", str(path)]), patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(checks.main(), 1)
                self.assertEqual(output.getvalue(), "BATCH_PLAN_VALIDATION_FAILED=UTC_MILLISECOND_TIMESTAMP_REQUIRED\n")


if __name__ == "__main__":
    unittest.main()
