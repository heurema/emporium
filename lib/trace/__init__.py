"""lib/trace — Trace capture and redaction for Signum artifacts.

Provides:
  redact_text(text)          -- replace secrets/PII with [REDACTED]
  archive_signum_run(...)    -- copy .signum/ to archive with redaction
  prune_old_runs(...)        -- delete old run directories from archive
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from lib.rubric import _SECRET_PATTERNS

# run_id format: signum-YYYY-MM-DD-<hex> (e.g. signum-2026-03-04-ab12cd)
_RUN_ID_RE = __import__("re").compile(r"^signum-\d{4}-\d{2}-\d{2}-[a-z0-9]+$")

# Text file extensions that receive redaction treatment.
_TEXT_EXTENSIONS = {".json", ".md", ".jsonl", ".log", ".txt"}


def redact_text(text: str) -> str:
    """Return text with all secrets and PII replaced by [REDACTED].

    Uses _SECRET_PATTERNS from lib.rubric (includes email + IP patterns).
    """
    for pat in _SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def archive_signum_run(
    signum_dir: str | Path,
    archive_root: str | Path,
) -> Path:
    """Copy a .signum/ run directory to archive_root/<run_id>/ with redaction.

    Steps:
      1. Read proofpack.json for run_id.
      2. Create archive_root/<run_id>/ (parents=True).
      3. Copy every file: text files get redact_text() applied; .patch files copied as binary.
      4. Set file permissions to 0o600 (owner-only).
      5. Return Path to the archived run directory.

    Raises:
      FileNotFoundError  -- if signum_dir or proofpack.json does not exist.
      json.JSONDecodeError -- if proofpack.json is not valid JSON.
      KeyError           -- if 'run_id' field is missing from proofpack.json.
    """
    signum_path = Path(signum_dir).resolve()
    if not signum_path.exists():
        raise FileNotFoundError(f"signum_dir not found: {signum_path}")

    proofpack = signum_path / "proofpack.json"
    if not proofpack.exists():
        raise FileNotFoundError(f"proofpack.json not found: {proofpack}")

    data = json.loads(proofpack.read_text(encoding="utf-8"))
    run_id: str = data["run_id"]

    if not _RUN_ID_RE.match(run_id):
        raise ValueError(
            f"run_id '{run_id}' does not match expected format "
            "(signum-YYYY-MM-DD-<hex>). Possible path traversal."
        )

    archive_path = Path(archive_root).expanduser().resolve() / run_id
    archive_path.mkdir(parents=True, exist_ok=True)

    for src in signum_path.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(signum_path)
        dst = archive_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if src.suffix.lower() in _TEXT_EXTENSIONS:
            content = src.read_text(encoding="utf-8", errors="replace")
            dst.write_text(redact_text(content), encoding="utf-8")
        else:
            # Binary (e.g. .patch) — copy without modification.
            shutil.copy2(src, dst)

        dst.chmod(0o600)

    return archive_path


def prune_old_runs(
    archive_root: str | Path,
    max_age_days: int = 90,
) -> list[Path]:
    """Delete run directories older than max_age_days from archive_root.

    Returns a list of deleted Paths.

    Raises:
      ValueError -- if archive_root does not exist.
    """
    if max_age_days < 0:
        raise ValueError(f"max_age_days must be non-negative, got {max_age_days}")

    root = Path(archive_root).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"archive_root does not exist: {root}")

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted: list[Path] = []

    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir():
            continue
        mtime = datetime.fromtimestamp(candidate.stat().st_mtime)
        if mtime < cutoff:
            shutil.rmtree(candidate)
            deleted.append(candidate)

    return deleted
