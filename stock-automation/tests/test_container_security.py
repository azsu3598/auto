from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPOSITORY_ROOT / "stock-automation" / "Dockerfile"
TEMPLATE = REPOSITORY_ROOT / "stock-automation" / "infra" / "cloudformation.yaml"


class ContainerSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        cls.template = TEMPLATE.read_text(encoding="utf-8")

    def test_image_runs_as_unprivileged_user(self):
        self.assertIn("USER 65534:65534", self.dockerfile)

    def test_task_reasserts_non_root_and_drops_all_capabilities(self):
        self.assertIn('User: "65534:65534"', self.template)
        self.assertIn("Drop: [ALL]", self.template)
        self.assertNotIn("Privileged: true", self.template)

    def test_task_uses_read_only_root_with_dedicated_tmp_volume(self):
        self.assertIn("ReadonlyRootFilesystem: true", self.template)
        self.assertIn("SourceVolume: runtime-tmp", self.template)
        self.assertIn("ContainerPath: /tmp", self.template)
        self.assertIn("ReadOnly: false", self.template)

    def test_task_explicitly_keeps_live_orders_disabled(self):
        self.assertIn('{Name: LIVE_ORDER_ENABLED, Value: "0"}', self.template)


if __name__ == "__main__":
    unittest.main()
