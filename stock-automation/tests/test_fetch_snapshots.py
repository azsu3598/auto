from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fetch_snapshots", ROOT / "tools" / "fetch_snapshots.py")
fetcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetcher)


class _Missing(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self, objects: dict[str, bytes], failures: dict[str, str] | None = None) -> None:
        self.objects = objects
        self.failures = failures or {}
        self.calls: list[tuple[str, str]] = []

    def get_object(self, *, Bucket: str, Key: str):
        self.calls.append((Bucket, Key))
        if Key in self.failures:
            raise _Missing(self.failures[Key])
        if Key not in self.objects:
            raise _Missing("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[Key])}

    def __getattr__(self, name):  # any other S3 operation must never be reached
        raise AssertionError(f"unexpected S3 call: {name}")


class FetchSnapshotsTests(unittest.TestCase):
    def test_keys_match_runtime_layout(self):
        self.assertEqual(
            [
                "runs/2026/10/27/KRX_1520/scan_1450-snapshot.json",
                "runs/2026/10/27/KRX_1520/shortlist_1510-snapshot.json",
                "runs/2026/10/27/KRX_1520/entry_1520-snapshot.json",
            ],
            fetcher.snapshot_keys(date(2026, 10, 27)),
        )

    def test_downloads_found_files_and_reports_missing_and_denied(self):
        keys = fetcher.snapshot_keys(date(2026, 10, 27))
        s3 = FakeS3({keys[0]: b'{"a":1}'}, failures={keys[2]: "AccessDenied"})
        with tempfile.TemporaryDirectory() as directory:
            rows = fetcher.fetch(s3, "bucket-x", [date(2026, 10, 27)], Path(directory))
            self.assertEqual(["DOWNLOADED", "NOT_FOUND", "ERROR"], [row["status"] for row in rows])
            self.assertIn("AccessDenied", rows[2]["detail"])
            saved = Path(directory) / "20261027" / "scan_1450-snapshot.json"
            self.assertEqual(b'{"a":1}', saved.read_bytes())
        self.assertEqual({("bucket-x", key) for key in keys}, set(s3.calls))

    def test_existing_file_is_never_overwritten(self):
        keys = fetcher.snapshot_keys(date(2026, 10, 27))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "20261027" / "scan_1450-snapshot.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old")
            rows = fetcher.fetch(FakeS3({keys[0]: b"new"}), "b", [date(2026, 10, 27)], Path(directory))
            self.assertEqual("SKIPPED_EXISTS", rows[0]["status"])
            self.assertEqual(b"old", target.read_bytes())

    def test_output_inside_repository_is_refused(self):
        inside = fetcher.REPO_ROOT / "stock-automation" / "runtime-snapshots"
        with self.assertRaises(ValueError):
            fetcher.fetch(FakeS3({}), "b", [date(2026, 10, 27)], inside)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            fetcher.main(["--bucket", "b", "--date", "2026-10-27", "--out", str(inside)], s3_factory=lambda: FakeS3({}))

    def test_main_needs_bucket_and_valid_date(self):
        with tempfile.TemporaryDirectory() as directory:
            base = ["--out", directory, "--date", "2026-10-27"]
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    fetcher.main(["--bucket", "", *base], s3_factory=lambda: FakeS3({}))
                with self.assertRaises(SystemExit):
                    fetcher.main(["--bucket", "b", "--out", directory, "--date", "10/27"], s3_factory=lambda: FakeS3({}))

    def test_main_returns_nonzero_when_nothing_downloaded(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            code = fetcher.main(
                ["--bucket", "b", "--date", "2026-10-27", "--out", directory], s3_factory=lambda: FakeS3({})
            )
        self.assertEqual(1, code)


if __name__ == "__main__":
    unittest.main()
