#!/usr/bin/env python3
"""trace-archive.py — Archive and prune Signum run artifacts with redaction.

Usage:
    python3 scripts/trace-archive.py --archive
    python3 scripts/trace-archive.py --archive --archive-root /tmp/traces
    python3 scripts/trace-archive.py --prune --max-age 30
    python3 scripts/trace-archive.py --archive --prune
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

from lib.trace import archive_signum_run, prune_old_runs

_DEFAULT_ARCHIVE_ROOT = Path.home() / ".local" / "share" / "emporium" / "traces"
_DEFAULT_SIGNUM_DIR = _REPO_ROOT / ".signum"
_DEFAULT_MAX_AGE = 90


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="trace-archive.py",
        description="Archive and prune Signum run artifacts with mandatory secret redaction.",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Archive the current .signum/ run to archive-root (reads run_id from proofpack.json).",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete archived runs older than --max-age days.",
    )
    parser.add_argument(
        "--archive-root",
        metavar="DIR",
        default=str(_DEFAULT_ARCHIVE_ROOT),
        help=f"Root directory for archived runs (default: {_DEFAULT_ARCHIVE_ROOT}).",
    )
    parser.add_argument(
        "--max-age",
        metavar="DAYS",
        type=int,
        default=_DEFAULT_MAX_AGE,
        help=f"Maximum age in days for --prune (default: {_DEFAULT_MAX_AGE}).",
    )
    parser.add_argument(
        "--signum-dir",
        metavar="DIR",
        default=str(_DEFAULT_SIGNUM_DIR),
        help=f"Path to .signum/ directory (default: {_DEFAULT_SIGNUM_DIR}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.archive and not args.prune:
        print(
            json.dumps({"error": "specify --archive and/or --prune"}),
            file=sys.stderr,
        )
        return 1

    exit_code = 0

    if args.archive:
        signum_dir = Path(args.signum_dir)
        archive_root = Path(args.archive_root)
        try:
            archived_path = archive_signum_run(signum_dir, archive_root)
            proofpack = signum_dir / "proofpack.json"
            run_id = json.loads(proofpack.read_text(encoding="utf-8"))["run_id"]
            print(f"archived run_id={run_id} to {archived_path}")
        except FileNotFoundError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            exit_code = 1
        except (json.JSONDecodeError, KeyError) as exc:
            print(json.dumps({"error": f"proofpack.json invalid: {exc}"}), file=sys.stderr)
            exit_code = 1

    if args.prune:
        archive_root = Path(args.archive_root)
        try:
            deleted = prune_old_runs(archive_root, max_age_days=args.max_age)
            print(f"{len(deleted)} run(s) deleted (older than {args.max_age} days)")
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
