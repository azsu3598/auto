import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("handoff_archive_test", ROOT / "tools" / "handoff_archive.py")
archive_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_tool)


def crlf(text):
    return text.replace("\n", "\r\n").encode()


def handoff(count):
    records = "".join(f"### R{n}\n\n- body {n}\n\n" for n in range(count, 0, -1))
    return crlf("# H\n\n## 9. 양식\n\n### YYYY 양식\n\n## 10. 세션 전달 기록\n\n안내\n\n"
                + records + "## 11. 다음\n\n끝\n")


ARCHIVE = crlf("# A\n\n> 안내\n\n## 보관 기록\n\n### OLD\n\n- old\n")


class HandoffArchiveTests(unittest.TestCase):
    def test_rotate_moves_only_overflow_records_verbatim(self):
        new_h, new_a, moved = archive_tool.rotate(handoff(7), ARCHIVE)
        self.assertEqual(moved, 2)
        self.assertIn(b"### R7", new_h)
        self.assertIn(b"### R3", new_h)
        self.assertNotIn(b"### R2", new_h)
        self.assertIn(crlf("## 11. 다음\n\n끝\n"), new_h)
        self.assertIn(crlf("## 보관 기록\n\n### R2\n\n- body 2\n\n### R1\n\n- body 1\n\n### OLD\n"), new_a)
        self.assertEqual(archive_tool.check(new_h, new_a), [])

    def test_template_heading_outside_section_is_not_counted(self):
        new_h, new_a, moved = archive_tool.rotate(handoff(5), ARCHIVE)
        self.assertEqual((moved, new_h, new_a), (0, handoff(5), ARCHIVE))

    def test_rotate_is_idempotent(self):
        once = archive_tool.rotate(handoff(9), ARCHIVE)
        twice = archive_tool.rotate(once[0], once[1])
        self.assertEqual(twice, (once[0], once[1], 0))

    def test_check_reports_overflow_bare_cr_and_conflicts(self):
        self.assertIn("HANDOFF_TOO_MANY_RECORDS", archive_tool.check(handoff(6), ARCHIVE))
        self.assertIn("ARCHIVE_BARE_CR", archive_tool.check(handoff(5), ARCHIVE + b"\rbroken"))
        conflicted = handoff(5).replace(b"### R1", b"<<<<<<< HEAD\r\n### R1")
        self.assertIn("HANDOFF_CONFLICT_MARKER", archive_tool.check(conflicted, ARCHIVE))
        with self.assertRaisesRegex(ValueError, "CONFLICT_MARKER"):
            archive_tool.rotate(conflicted, ARCHIVE)

    def test_missing_section_is_rejected(self):
        self.assertIn("ARCHIVE_SECTION_NOT_FOUND", archive_tool.check(handoff(1), crlf("# A\n")))

    def test_cli_rotates_files_and_preserves_all_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / archive_tool.ARCHIVE).parent.mkdir(parents=True)
            (root / archive_tool.HANDOFF).write_bytes(handoff(8))
            (root / archive_tool.ARCHIVE).write_bytes(ARCHIVE)
            with redirect_stdout(io.StringIO()) as out:
                code = archive_tool.main(["rotate", "--root", str(root)])
            self.assertEqual(code, 0)
            self.assertIn("ROTATED 3", out.getvalue())
            h = (root / archive_tool.HANDOFF).read_bytes()
            a = (root / archive_tool.ARCHIVE).read_bytes()
            self.assertEqual(len(h) + len(a), len(handoff(8)) + len(ARCHIVE))
            self.assertEqual(list(root.rglob("*.tmp")), [])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(archive_tool.main(["check", "--root", str(root)]), 0)

    def test_lf_and_mixed_endings_preserve_record_bytes(self):
        for h, a in [(handoff(7).replace(b"\r\n", b"\n"), ARCHIVE),
                     (handoff(7), ARCHIVE.replace(b"\r\n", b"\n")),
                     (handoff(7).replace(b"- body 2\r\n", b"- body 2\n"), ARCHIVE)]:
            with self.subTest(handoff_crlf=h.count(b"\r\n"), archive_crlf=a.count(b"\r\n")):
                new_h, new_a, moved = archive_tool.rotate(h, a)
                raw_moved = h[h.index(b"### R2"):h.index("## 11. 다음".encode())]
                self.assertIn(raw_moved, new_a)
                self.assertNotIn(b"### R2", new_h)
                self.assertEqual(len(new_h) + len(new_a), len(h) + len(a))
                self.assertEqual(moved, 2)
                self.assertEqual(archive_tool.check(new_h, new_a), [])

    def test_lf_without_overflow_is_not_reformatted(self):
        h, a = handoff(5).replace(b"\r\n", b"\n"), ARCHIVE.replace(b"\r\n", b"\n")
        self.assertEqual(archive_tool.rotate(h, a), (h, a, 0))
        self.assertEqual(archive_tool.check(h, a), [])

    def test_invalid_keep_values_rejected_before_changes(self):
        for keep in [0, -1, True]:
            self.assertEqual(archive_tool.check(handoff(7), ARCHIVE, keep), ["INVALID_KEEP"])
            with self.assertRaisesRegex(ValueError, "INVALID_KEEP"):
                archive_tool.rotate(handoff(7), ARCHIVE, keep)

    def test_missing_archive_layout_rejected_even_without_overflow(self):
        for a in [b"# missing\n", "## 보관 기록\n".encode()]:
            with self.assertRaises(ValueError): archive_tool.rotate(handoff(5), a)

    def test_separator_and_diff3_conflicts_are_rejected(self):
        for marker in [b"=======", b"||||||| base", b">>>>>>> branch"]:
            h = handoff(6).replace(b"### R1", marker + b"\r\n### R1")
            with self.assertRaisesRegex(ValueError, "CONFLICT_MARKER"):
                archive_tool.rotate(h, ARCHIVE)


class HandoffTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / archive_tool.ARCHIVE).parent.mkdir(parents=True)
        self.handoff = self.root / archive_tool.HANDOFF
        self.archive = self.root / archive_tool.ARCHIVE
        self.handoff.write_bytes(handoff(7)); self.archive.write_bytes(ARCHIVE)
        self.expected = archive_tool.rotate(handoff(7), ARCHIVE)

    def cli(self, command):
        with redirect_stdout(io.StringIO()) as out:
            code = archive_tool.main([command, "--root", str(self.root)])
        return code, out.getvalue()

    def interrupt(self, target):
        original = archive_tool.atomic_write
        def write(path, data, expected=None):
            if path == target: raise OSError("simulated interruption")
            return original(path, data, expected)
        with patch.object(archive_tool, "atomic_write", side_effect=write):
            self.assertEqual(self.cli("rotate")[0], 1)

    def test_partial_write_has_backups_and_explicit_recovery(self):
        self.interrupt(self.handoff)
        pending = self.root / archive_tool.CONTROL / archive_tool.PENDING
        self.assertTrue(pending.exists())
        self.assertEqual(self.handoff.read_bytes(), handoff(7))
        self.assertEqual(self.archive.read_bytes(), self.expected[1])
        self.assertIn("RECOVERY_REQUIRED", self.cli("check")[1])
        self.assertIn("RECOVERY_REQUIRED", self.cli("rotate")[1])
        self.assertEqual(self.cli("recover")[0], 0)
        self.assertFalse(pending.exists())
        self.assertEqual(self.handoff.read_bytes(), self.expected[0])
        self.assertEqual(self.archive.read_bytes(), self.expected[1])
        manifests = list((self.root / archive_tool.CONTROL).glob("txn-*/manifest.json"))
        self.assertEqual(len(manifests), 1)
        self.assertEqual((manifests[0].parent / "handoff.before").read_bytes(), handoff(7))
        self.assertEqual((manifests[0].parent / "archive.before").read_bytes(), ARCHIVE)

    def test_interruption_before_first_markdown_replace_is_recoverable(self):
        self.interrupt(self.archive)
        self.assertEqual(self.handoff.read_bytes(), handoff(7))
        self.assertEqual(self.archive.read_bytes(), ARCHIVE)
        self.assertEqual(self.cli("recover")[0], 0)
        self.assertEqual(self.handoff.read_bytes(), self.expected[0])

    def test_recovery_preserves_manual_edits_instead_of_overwriting(self):
        self.interrupt(self.handoff)
        edited = self.handoff.read_bytes() + b"\r\nmanual edit\r\n"
        self.handoff.write_bytes(edited)
        code, output = self.cli("recover")
        self.assertEqual(code, 1)
        self.assertIn("RECOVERY_CONFLICT_PRESERVE_MANUAL_EDITS", output)
        self.assertEqual(self.handoff.read_bytes(), edited)
        self.assertEqual(self.archive.read_bytes(), self.expected[1])

    def test_changed_file_after_preparation_is_preserved(self):
        original = archive_tool.prepare_transaction
        edited = handoff(7) + b"manual edit\n"
        def prepare(*args):
            result = original(*args)
            self.handoff.write_bytes(edited)
            return result
        with patch.object(archive_tool, "prepare_transaction", side_effect=prepare):
            self.assertEqual(self.cli("rotate")[0], 1)
        self.assertEqual(self.handoff.read_bytes(), edited)
        self.assertEqual(self.archive.read_bytes(), ARCHIVE)

    def test_completed_files_with_pending_journal_do_not_duplicate_records(self):
        original = Path.unlink
        pending = self.root / archive_tool.CONTROL / archive_tool.PENDING
        def unlink(path, *args, **kwargs):
            if path == pending: raise OSError("simulated interruption")
            return original(path, *args, **kwargs)
        with patch.object(Path, "unlink", new=unlink):
            self.assertEqual(self.cli("rotate")[0], 1)
        self.assertEqual(self.handoff.read_bytes(), self.expected[0])
        self.assertEqual(self.archive.read_bytes(), self.expected[1])
        self.assertEqual(self.cli("recover")[0], 0)
        self.assertEqual(self.archive.read_bytes(), self.expected[1])

    def test_corrupt_backup_is_rejected_without_changing_documents(self):
        self.interrupt(self.handoff)
        journal = json.loads((self.root / archive_tool.CONTROL / archive_tool.PENDING).read_bytes())
        directory = self.root / archive_tool.CONTROL / ("txn-" + journal["transaction_id"])
        (directory / "handoff.after").write_bytes(b"corrupt")
        self.assertIn("BACKUP_HASH_MISMATCH", self.cli("recover")[1])
        self.assertEqual(self.handoff.read_bytes(), handoff(7))

    def test_invalid_journal_id_never_selects_arbitrary_paths(self):
        self.interrupt(self.handoff)
        pending = self.root / archive_tool.CONTROL / archive_tool.PENDING
        data = json.loads(pending.read_bytes()); data["transaction_id"] = "../../other"
        pending.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("INVALID_JOURNAL_ID", self.cli("recover")[1])

    def test_unique_temporaries_do_not_touch_legacy_tmp_files(self):
        stale = self.handoff.with_name(self.handoff.name + ".tmp")
        stale.write_bytes(b"preserve unrelated backup")
        self.assertEqual(self.cli("rotate")[0], 0)
        self.assertEqual(stale.read_bytes(), b"preserve unrelated backup")
        self.assertEqual(list(self.handoff.parent.glob(".handoff-*.tmp")), [])
        self.assertEqual(list(self.archive.parent.glob(".handoff-*.tmp")), [])

    def test_atomic_replace_failure_leaves_original_and_cleans_own_temporary(self):
        with patch.object(archive_tool.os, "replace", side_effect=OSError("simulated failure")):
            with self.assertRaises(OSError):
                archive_tool.atomic_write(self.handoff, b"new", expected=handoff(7))
        self.assertEqual(self.handoff.read_bytes(), handoff(7))
        self.assertEqual(list(self.root.glob(".handoff-*.tmp")), [])

    def test_another_process_cannot_rotate_under_the_lock(self):
        with archive_tool.repository_lock(self.root):
            result = subprocess.run([sys.executable, str(ROOT / "tools/handoff_archive.py"),
                                     "rotate", "--root", str(self.root)],
                                    capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ARCHIVE_BUSY", result.stdout)
        self.assertEqual(self.handoff.read_bytes(), handoff(7))

    def test_operating_system_releases_lock_after_process_exit(self):
        code = ("import importlib.util, pathlib, os\n"
                f"spec=importlib.util.spec_from_file_location('archiver',{str(ROOT / 'tools/handoff_archive.py')!r})\n"
                "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)\n"
                f"with module.repository_lock(pathlib.Path({str(self.root)!r})):\n"
                "    os._exit(17)\n")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 17)
        self.assertEqual(self.cli("rotate")[0], 0)

    def test_no_pending_recovery_does_not_reformat_or_rotate(self):
        self.assertIn("NO_PENDING_TRANSACTION", self.cli("recover")[1])
        self.assertEqual(self.handoff.read_bytes(), handoff(7))

    def test_repeated_rotation_is_idempotent(self):
        self.assertEqual(self.cli("rotate")[0], 0)
        after = (self.handoff.read_bytes(), self.archive.read_bytes())
        self.assertEqual(self.cli("rotate")[0], 0)
        self.assertEqual((self.handoff.read_bytes(), self.archive.read_bytes()), after)


if __name__ == "__main__":
    unittest.main()
