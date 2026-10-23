import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from package_lab import FILES, package

ROOT = Path(__file__).resolve().parents[2]


class IsolationTests(unittest.TestCase):
    def test_review_archive_is_explicitly_not_deployment_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "review.zip"
            package(target)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()), set(FILES) | {"manifest.json"})
                manifest = json.loads(archive.read("manifest.json"))
                self.assertFalse(manifest["deployment_ready"])
                self.assertFalse(manifest["broker_connection"])
            with self.assertRaises(FileExistsError): package(target)

    def test_operational_dashboard_package_never_contains_lab_files(self):
        spec = importlib.util.spec_from_file_location("operational_web_packager", ROOT / "tools/package_web_dashboard.py")
        packager = importlib.util.module_from_spec(spec); spec.loader.exec_module(packager)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "operational-web"
            packager.package(output)
            with zipfile.ZipFile(output / "api.zip") as archive:
                self.assertFalse(any("recommendation" in name for name in archive.namelist()))
            for file in (output / "static").iterdir():
                self.assertNotIn(b"/api/recommendations", file.read_bytes())

    def test_container_does_not_copy_lab_or_docs(self):
        docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("COPY .", docker)
        self.assertNotIn("recommendation-lab", docker)
        self.assertNotIn("COPY docs", docker)
        self.assertIn("COPY stock-automation/src", docker)

    def test_research_runtime_does_not_import_execution_broker_or_cloud_sdk(self):
        import ast
        lab = Path(__file__).resolve().parents[1]
        for name in ["core.py", "service.py", "server.py"]:
            tree = ast.parse((lab / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import): modules = [x.name for x in node.names]
                elif isinstance(node, ast.ImportFrom): modules = [node.module or ""]
                else: continue
                for module in modules:
                    self.assertNotIn(module.split(".")[0], {"stock_automation", "kiwoom", "boto3", "botocore"})


if __name__ == "__main__": unittest.main()
