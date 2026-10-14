"""Opt-in Docker regression for the ECS temporary-volume permission contract.

Set STOCK_AUTOMATION_TEST_IMAGE to the freshly built image. The scanner and
containers do not connect to any registry or external API during these tests.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid


PROBE = """
import json, os, pathlib, stat, tempfile
result = {"uid": os.getuid(), "gid": os.getgid(), "tmpdir": os.getenv("TMPDIR")}
info = os.stat("/tmp")
result.update(tmp_owner=info.st_uid, tmp_mode=stat.S_IMODE(info.st_mode))
try:
    with tempfile.TemporaryDirectory(dir="/tmp") as directory:
        path = pathlib.Path(directory) / "report.md"
        path.write_text("paper-only local regression", encoding="utf-8")
        result["tmp_write"] = path.read_text(encoding="utf-8") == "paper-only local regression"
        result["default_tmpdir"] = tempfile.gettempdir()
    result["tmp_cleaned"] = not pathlib.Path(directory).exists()
except OSError as error:
    result.update(tmp_write=False, error=type(error).__name__)
try:
    pathlib.Path("/app/permission-regression").write_text("must remain blocked")
    result["root_write_blocked"] = False
except OSError:
    result["root_write_blocked"] = True
status = pathlib.Path("/proc/self/status").read_text()
result["capabilities_dropped"] = "CapEff:\\t0000000000000000" in status
result["privilege_escalation_blocked"] = "NoNewPrivs:\\t1" in status
print(json.dumps(result))
"""


@unittest.skipUnless(
    os.getenv("STOCK_AUTOMATION_TEST_IMAGE") and shutil.which("docker"),
    "Set STOCK_AUTOMATION_TEST_IMAGE to run the local Docker integration checks",
)
class ContainerTemporaryVolumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = os.environ["STOCK_AUTOMATION_TEST_IMAGE"]
        context = os.getenv(
            "STOCK_AUTOMATION_DOCKER_CONTEXT",
            "desktop-linux" if sys.platform == "win32" else "default",
        )
        cls.docker = ["docker", "--context", context]
        details = json.loads(cls.command("context", "inspect", context))[0]
        endpoint = details["Endpoints"]["docker"]["Host"]
        if not endpoint.startswith(("npipe://", "unix://")):
            raise RuntimeError("These tests require a local Docker engine")
        # Inspect only a local image; never pull a missing image from a registry.
        cls.image_info = json.loads(cls.command("image", "inspect", cls.image))[0]
        cls.image = cls.image_info["Id"]

    @classmethod
    def command(cls, *args):
        result = subprocess.run(cls.docker + list(args), capture_output=True, timeout=30)
        if result.returncode:
            raise RuntimeError(f"Local Docker {args[0]} failed (exit {result.returncode})")
        return result.stdout

    def probe(self, *, copy_image_directory):
        volume = "stock-tmp-test-" + uuid.uuid4().hex
        container = "stock-tmp-test-" + uuid.uuid4().hex
        self.command("volume", "create", volume)
        mount = f"type=volume,source={volume},target=/tmp"
        if not copy_image_directory:
            mount += ",volume-nocopy"
        try:
            raw = self.command(
                "run", "--rm", "--name", container, "--pull", "never",
                "--network", "none", "--read-only", "--user", "65534:65534",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--init", "--mount", mount, "--entrypoint", "python",
                self.image, "-c", PROBE,
            )
            return json.loads(raw)
        finally:
            subprocess.run(
                self.docker + ["container", "rm", "--force", container],
                capture_output=True, timeout=30,
            )
            self.command("volume", "rm", volume)

    def test_image_volume_initialization_allows_only_nonroot_tmp_writes(self):
        self.assertIn("/tmp", self.image_info["Config"].get("Volumes", {}))
        self.assertEqual(self.image_info["Config"]["User"], "65534:65534")
        result = self.probe(copy_image_directory=True)
        self.assertEqual((result["uid"], result["gid"], result["tmp_owner"]), (65534, 65534, 65534))
        self.assertEqual(result["tmpdir"], "/tmp")
        self.assertEqual(result["default_tmpdir"], "/tmp")
        self.assertEqual(result["tmp_mode"], 0o700)
        self.assertTrue(result["tmp_write"])
        self.assertTrue(result["tmp_cleaned"])
        self.assertTrue(result["root_write_blocked"])
        self.assertTrue(result["capabilities_dropped"])
        self.assertTrue(result["privilege_escalation_blocked"])

    def test_uninitialized_default_volume_reproduces_the_permission_failure(self):
        result = self.probe(copy_image_directory=False)
        self.assertEqual((result["tmp_owner"], result["tmp_mode"]), (0, 0o755))
        self.assertFalse(result["tmp_write"])
        self.assertEqual(result["error"], "PermissionError")
        self.assertTrue(result["root_write_blocked"])


if __name__ == "__main__":
    unittest.main()
