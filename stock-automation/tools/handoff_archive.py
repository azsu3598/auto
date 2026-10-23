"""Keep the shared handoff section 10 short by moving old records verbatim.

Record bytes are preserved, including LF/CRLF. A process lock, immutable backups
and a pending journal protect the two-file update. Auxiliary files live in the
Git-ignored archives/handoff-archive directory. No cloud or trading calls.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid


REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF = Path("Codex_세션간_공동_인수인계.md")
ARCHIVE = Path("docs") / "운영 검증" / "공동_인수인계_세션기록_보관.md"
SECTION = "## 10. 세션 전달 기록".encode()
ARCHIVE_SECTION = "## 보관 기록".encode()
KEEP = 5
NL = b"\r\n"
CONTROL = Path("archives") / "handoff-archive"
PENDING = "pending.json"
CONFLICT_MARKERS = (b"<<<<<<<", b">>>>>>>", b"|||||||")


def require(condition, code):
    if not condition:
        raise ValueError(code)


def split_lines(data, code):
    # Keep the actual line endings: moving CRLF records into an LF archive must
    # not rewrite their bytes. Mixed LF/CRLF is consequently supported as well.
    require(b"\r" not in data.replace(NL, b""), code + "_BARE_CR")
    return data.splitlines(keepends=True)


def text(line):
    return line.removesuffix(b"\n").removesuffix(b"\r")


def section_bounds(lines, title, code):
    headings = [text(line) for line in lines]
    require(headings.count(title) == 1, code + "_SECTION_NOT_FOUND")
    start = headings.index(title)
    end = next((i for i in range(start + 1, len(lines)) if headings[i].startswith(b"## ")), len(lines))
    return start, end


def record_heads(lines, start, end):
    return [i for i in range(start + 1, end) if lines[i].startswith(b"### ")]


def conflict_lines(lines):
    return [i + 1 for i, line in enumerate(lines)
            if text(line).startswith(CONFLICT_MARKERS) or text(line) == b"======="]


def check(handoff, archive, keep=KEEP):
    """Return problem codes; an empty list means both files follow the rule."""
    problems = []
    if type(keep) is not int or keep < 1:
        return ["INVALID_KEEP"]
    for name, data, title in (("HANDOFF", handoff, SECTION), ("ARCHIVE", archive, ARCHIVE_SECTION)):
        try:
            lines = split_lines(data, name)
            start, end = section_bounds(lines, title, name)
        except ValueError as error:
            problems.append(str(error))
            continue
        if conflict_lines(lines):
            problems.append(name + "_CONFLICT_MARKER")
        if name == "HANDOFF" and len(record_heads(lines, start, end)) > keep:
            problems.append("HANDOFF_TOO_MANY_RECORDS")
    return problems


def rotate(handoff, archive, keep=KEEP):
    """Return (new_handoff, new_archive, moved_count) without changing record bytes."""
    require(type(keep) is int and keep >= 1, "INVALID_KEEP")
    h = split_lines(handoff, "HANDOFF")
    a = split_lines(archive, "ARCHIVE")
    require(not conflict_lines(h) and not conflict_lines(a), "CONFLICT_MARKER")
    start, end = section_bounds(h, SECTION, "HANDOFF")
    a_start, _ = section_bounds(a, ARCHIVE_SECTION, "ARCHIVE")
    require(a_start + 1 < len(a) and text(a[a_start + 1]) == b"", "ARCHIVE_SECTION_HEADER_LAYOUT")
    heads = record_heads(h, start, end)
    if len(heads) <= keep:
        return handoff, archive, 0
    require(text(h[end - 1]) == b"" and h[end - 1].endswith(b"\n"), "HANDOFF_SECTION_END_NOT_BLANK")
    moved = h[heads[keep]:end]
    new_h = h[:heads[keep]] + h[end:]
    new_a = a[:a_start + 2] + moved + a[a_start + 2:]
    # 옮긴 기록 바이트가 원본과 같고 다른 부분은 그대로인지 다시 확인한다.
    require(new_a[a_start + 2:a_start + 2 + len(moved)] == moved, "MOVE_MISMATCH")
    new_h, new_a = b"".join(new_h), b"".join(new_a)
    require(len(new_h) + len(new_a) == len(handoff) + len(archive), "BYTE_COUNT_MISMATCH")
    require(not check(new_h, new_a, keep), "ROTATION_INVALID")
    return new_h, new_a, len(record_heads(moved, -1, len(moved)))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sync_directory(path):
    # Windows has no portable directory fsync. File contents are fsynced on both
    # platforms; a hardware/filesystem failure is not a two-file atomic commit.
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_write(path, data, expected=None):
    """Unique same-directory temporary, flushed before replacement."""
    fd, filename = tempfile.mkstemp(prefix=".handoff-", suffix=".tmp", dir=path.parent)
    temp = Path(filename)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if expected is not None:
            require(not path.is_symlink() and path.read_bytes() == expected, "FILE_CHANGED_DURING_ROTATION")
        os.replace(temp, path)
        sync_directory(path.parent)
    finally:
        # Only our own unique temporary is removed, never another process's file.
        if temp.exists():
            temp.unlink()


@contextmanager
def repository_lock(root):
    control = root / CONTROL
    control.mkdir(parents=True, exist_ok=True)
    # Keep the lock file permanently. Deleting it could create two lock inodes.
    # The OS releases the lock when a process exits, including a crash.
    with (control / "process.lock").open("a+b") as stream:
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("ARCHIVE_BUSY") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def prepare_transaction(root, old_handoff, old_archive, new_handoff, new_archive, keep):
    """Persist before/after evidence before changing either Markdown file."""
    control = root / CONTROL
    require(not (control / PENDING).exists(), "RECOVERY_REQUIRED")
    transaction_id = uuid.uuid4().hex
    directory = control / ("txn-" + transaction_id)
    directory.mkdir()
    entries = {}
    for key, before, after in (("archive", old_archive, new_archive), ("handoff", old_handoff, new_handoff)):
        for suffix, content in (("before", before), ("after", after)):
            with (directory / (key + "." + suffix)).open("xb") as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
        entries[key] = {"before": digest(before), "after": digest(after)}
    journal = {"version": 1, "transaction_id": transaction_id, "keep": keep, "files": entries}
    encoded = (json.dumps(journal, sort_keys=True) + "\n").encode()
    atomic_write(directory / "manifest.json", encoded)
    sync_directory(control)
    atomic_write(control / PENDING, encoded)
    return journal


def finish_transaction(root, journal):
    """Roll forward only if both files are at the recorded before/after states."""
    require(isinstance(journal, dict) and journal.get("version") == 1, "INVALID_JOURNAL")
    transaction_id = journal.get("transaction_id")
    require(isinstance(transaction_id, str) and re.fullmatch(r"[a-f0-9]{32}", transaction_id), "INVALID_JOURNAL_ID")
    require(type(journal.get("keep")) is int and journal["keep"] >= 1, "INVALID_JOURNAL_KEEP")
    directory = root / CONTROL / ("txn-" + transaction_id)
    require(journal == json.loads((directory / "manifest.json").read_bytes()), "JOURNAL_MISMATCH")
    states = []
    for key, relative in (("archive", ARCHIVE), ("handoff", HANDOFF)):
        before = (directory / (key + ".before")).read_bytes()
        after = (directory / (key + ".after")).read_bytes()
        require(journal["files"][key] == {"before": digest(before), "after": digest(after)}, "BACKUP_HASH_MISMATCH")
        path = root / relative
        require(not path.is_symlink(), "SYMLINK_NOT_SUPPORTED")
        current = path.read_bytes()
        require(current in (before, after), "RECOVERY_CONFLICT_PRESERVE_MANUAL_EDITS")
        states.append((path, before, after))
    require(not check(states[1][2], states[0][2], journal["keep"]), "INVALID_TRANSACTION_RESULT")
    # Archive first: interruption cannot remove a record before archiving it.
    for path, before, after in states:
        current = path.read_bytes()
        require(current in (before, after), "FILE_CHANGED_DURING_ROTATION")
        if current != after:
            atomic_write(path, after, expected=before)
    require(all(path.read_bytes() == after for path, _, after in states), "FINAL_CONTENT_MISMATCH")
    (root / CONTROL / PENDING).unlink()
    sync_directory(root / CONTROL)
    # Retain the uniquely named transaction backups for manual recovery/audit.


def write_pair(root, handoff, archive, new_handoff, new_archive, keep):
    require((root / HANDOFF).read_bytes() == handoff and (root / ARCHIVE).read_bytes() == archive,
            "FILE_CHANGED_DURING_ROTATION")
    journal = prepare_transaction(root, handoff, archive, new_handoff, new_archive, keep)
    finish_transaction(root, journal)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "rotate", "recover"))
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--keep", type=int, default=KEEP)
    args = parser.parse_args(argv)
    try:
        require(args.keep >= 1, "INVALID_KEEP")
        with repository_lock(args.root):
            pending = args.root / CONTROL / PENDING
            if pending.exists():
                require(args.command == "recover", "RECOVERY_REQUIRED")
                journal = json.loads(pending.read_bytes())
                finish_transaction(args.root, journal)
                args.keep = journal["keep"]
                print("RECOVERED")
            elif args.command == "recover":
                print("NO_PENDING_TRANSACTION")
            handoff_path, archive_path = args.root / HANDOFF, args.root / ARCHIVE
            handoff, archive = handoff_path.read_bytes(), archive_path.read_bytes()
            if args.command == "rotate":
                new_handoff, new_archive, moved = rotate(handoff, archive, args.keep)
                if moved:
                    write_pair(args.root, handoff, archive, new_handoff, new_archive, args.keep)
                print("ROTATED", moved)
                handoff, archive = handoff_path.read_bytes(), archive_path.read_bytes()
            problems = check(handoff, archive, args.keep)
            print("PASSED" if not problems else "FAILED " + ",".join(problems))
            return 1 if problems else 0
    except ValueError as error:
        print("FAILED", str(error))
    except (OSError, KeyError, TypeError):
        print("FAILED IO_OR_JOURNAL_ERROR; preserve backups and inspect pending transaction")
    return 1


if __name__ == "__main__":
    sys.exit(main())
