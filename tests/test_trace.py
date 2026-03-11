"""Tests for lib/trace — archive, prune, and file integrity."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from pathlib import Path

import pytest

# Ensure lib/ is importable when running from repo root.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.trace import archive_signum_run, prune_old_runs, redact_text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_signum_dir(tmp_path: Path, run_id: str = "signum-2026-03-04-abc123") -> Path:
    """Create a minimal .signum/ directory with proofpack.json and sample files."""
    signum = tmp_path / ".signum"
    signum.mkdir()

    # proofpack.json with run_id
    (signum / "proofpack.json").write_text(
        json.dumps({"run_id": run_id, "note": "user@example.com"}),
        encoding="utf-8",
    )

    # contract.json with a secret
    (signum / "contract.json").write_text(
        json.dumps({"goal": "test", "key": "OPENAI_API_KEY='sk-1234567890'"}),
        encoding="utf-8",
    )

    # execute_log.json with IP
    (signum / "execute_log.json").write_text(
        json.dumps({"status": "SUCCESS", "server": "192.168.1.1"}),
        encoding="utf-8",
    )

    # combined.patch — binary-ish file
    (signum / "combined.patch").write_bytes(
        b"--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new\n"
    )

    # a markdown file with an email
    (signum / "notes.md").write_text(
        "# Notes\nContact: admin@secret.org\n",
        encoding="utf-8",
    )

    return signum


# ---------------------------------------------------------------------------
# test_archive_signum_run
# ---------------------------------------------------------------------------

def test_archive_signum_run(tmp_path: Path) -> None:
    signum = _make_signum_dir(tmp_path)
    archive_root = tmp_path / "archive"

    result = archive_signum_run(signum, archive_root)

    assert result == archive_root / "signum-2026-03-04-abc123"
    assert result.is_dir()

    # All source files should be present in archive.
    for src in signum.rglob("*"):
        if src.is_file():
            dst = result / src.relative_to(signum)
            assert dst.exists(), f"missing in archive: {dst}"

    # Text files must have secrets redacted.
    contract = json.loads((result / "contract.json").read_text())
    assert "[REDACTED]" in contract["key"], "API key not redacted in contract.json"

    log_data = json.loads((result / "execute_log.json").read_text())
    assert "[REDACTED]" in log_data["server"], "IP not redacted in execute_log.json"

    proofpack = json.loads((result / "proofpack.json").read_text())
    assert "[REDACTED]" in proofpack["note"], "email not redacted in proofpack.json"

    notes = (result / "notes.md").read_text()
    assert "[REDACTED]" in notes, "email not redacted in notes.md"

    # Patch file must NOT be modified (compare bytes).
    original_patch = (signum / "combined.patch").read_bytes()
    archived_patch = (result / "combined.patch").read_bytes()
    assert original_patch == archived_patch, ".patch file was modified (should be binary copy)"

    # File permissions must be 644.
    for dst in result.rglob("*"):
        if dst.is_file():
            mode = stat.S_IMODE(dst.stat().st_mode)
            assert mode == 0o600, f"{dst} has mode {oct(mode)}, expected 0o600"


def test_archive_signum_run_missing_proofpack(tmp_path: Path) -> None:
    signum = tmp_path / ".signum"
    signum.mkdir()
    archive_root = tmp_path / "archive"

    with pytest.raises(FileNotFoundError):
        archive_signum_run(signum, archive_root)


def test_archive_signum_run_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        archive_signum_run(tmp_path / "nonexistent", tmp_path / "archive")


def test_archive_idempotent(tmp_path: Path) -> None:
    """archive_signum_run called twice with same run_id overwrites without error."""
    signum = _make_signum_dir(tmp_path)
    archive_root = tmp_path / "archive"

    path1 = archive_signum_run(signum, archive_root)
    path2 = archive_signum_run(signum, archive_root)

    assert path1 == path2
    # Verify archive is consistent (contract.json redacted correctly).
    contract = json.loads((path2 / "contract.json").read_text())
    assert "[REDACTED]" in contract["key"]


# ---------------------------------------------------------------------------
# test_prune_old_runs
# ---------------------------------------------------------------------------

def test_prune_old_runs(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()

    # Create two "recent" run dirs and one "old" dir.
    recent1 = archive_root / "run-recent-1"
    recent1.mkdir()
    recent2 = archive_root / "run-recent-2"
    recent2.mkdir()
    old_run = archive_root / "run-old"
    old_run.mkdir()

    # Set old_run mtime to 100 days ago.
    old_ts = time.time() - (100 * 86400)
    os.utime(old_run, (old_ts, old_ts))

    deleted = prune_old_runs(archive_root, max_age_days=90)

    assert len(deleted) == 1
    assert old_run in deleted
    assert not old_run.exists()
    assert recent1.exists()
    assert recent2.exists()


def test_prune_old_runs_empty(tmp_path: Path) -> None:
    archive_root = tmp_path / "archive"
    archive_root.mkdir()

    deleted = prune_old_runs(archive_root)
    assert deleted == []


def test_prune_old_runs_missing_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        prune_old_runs(tmp_path / "nonexistent")


# ---------------------------------------------------------------------------
# test_archive_file_integrity
# ---------------------------------------------------------------------------

def test_archive_file_integrity(tmp_path: Path) -> None:
    """Redacted text files are valid JSON where applicable; .patch is binary-safe; perms 644."""
    signum = _make_signum_dir(tmp_path)
    archive_root = tmp_path / "archive"
    result = archive_signum_run(signum, archive_root)

    # All .json files in archive must be valid JSON.
    for json_file in result.glob("*.json"):
        try:
            json.loads(json_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"{json_file.name} is not valid JSON after redaction: {exc}")

    # .patch file must be binary-identical to source.
    src_patch = (signum / "combined.patch").read_bytes()
    dst_patch = (result / "combined.patch").read_bytes()
    assert src_patch == dst_patch, ".patch file corrupted during archive"

    # All files have 644 permissions.
    for dst in result.rglob("*"):
        if dst.is_file():
            mode = stat.S_IMODE(dst.stat().st_mode)
            assert mode == 0o600, f"{dst} mode {oct(mode)} != 0o600"
