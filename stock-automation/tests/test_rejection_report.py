from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from test_engine import quote, snapshot

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("rejection_report", ROOT / "tools" / "rejection_report.py")
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)


def _write(directory: Path, name: str, *quotes) -> Path:
    def default(value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, tuple):
            return list(value)
        raise TypeError(type(value).__name__)

    path = directory / name
    path.write_text(json.dumps(asdict(snapshot(*quotes)), default=default), encoding="utf-8")
    return path


class RejectionReportTests(unittest.TestCase):
    def test_counts_first_failed_filter_across_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write(root, "a-snapshot.json", quote(code="000001"), quote(code="000002", trading_value=1))
            _write(
                root,
                "b-snapshot.json",
                quote(code="000003", catalyst_verified=False),
                quote(code="000004", trading_value=1),
            )
            rows, skipped = report.collect(sorted(root.glob("*-snapshot.json")))
            self.assertEqual([], skipped)
            self.assertEqual([2, 2], [row["quotes"] for row in rows])
            self.assertEqual([1, 0], [row["passed_hard_filters"] for row in rows])
            text = report.render(rows, skipped)
            self.assertIn("거래대금 부족 (`LOW_TRADING_VALUE`) | 2 | 66.7%", text)
            self.assertIn("촉매 미확인 (`CATALYST_NOT_VERIFIED`) | 1 | 33.3%", text)

    def test_unreadable_or_delayed_files_are_reported_not_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = _write(root, "good-snapshot.json", quote())
            bad = root / "bad-snapshot.json"
            bad.write_text("{not json", encoding="utf-8")
            missing = root / "missing-snapshot.json"
            rows, skipped = report.collect([good, bad, missing])
            self.assertEqual(1, len(rows))
            self.assertEqual({str(bad), str(missing)}, {item["file"] for item in skipped})

    def test_main_requires_input_and_reads_only(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            report.main([])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write(root, "x-snapshot.json", quote(code="000001", trading_value=1))
            before = sorted(p.name for p in root.iterdir())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, report.main(["--dir", str(root)]))
            self.assertEqual(before, sorted(p.name for p in root.iterdir()))


if __name__ == "__main__":
    unittest.main()
