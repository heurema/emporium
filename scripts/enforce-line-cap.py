#!/usr/bin/env python3
"""enforce-line-cap.py — Batch scanner: check 300-line cap on all plugins in a directory.

Scans every subdirectory under --plugin-root for a SKILL.md file and reports
line counts with PASS/FAIL status. Exit 0 if all plugins pass, exit 1 if any fail.

Usage:
    python3 scripts/enforce-line-cap.py
    python3 scripts/enforce-line-cap.py --plugin-root /path/to/plugins
    python3 scripts/enforce-line-cap.py --plugin-root /path/to/plugins --output /tmp/report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

from lib.rubric import check_line_count

PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINE_LIMIT = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="enforce-line-cap.py",
        description=(
            "Batch scanner: check 300-line cap on all plugins. "
            "Exit 0 if all pass, exit 1 if any exceed the limit."
        ),
    )
    parser.add_argument(
        "--plugin-root",
        metavar="DIR",
        default=None,
        help="Directory containing plugin subdirectories (default: ~/personal/skill7/devtools/).",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write JSON report to FILE (default: print human-readable table to stdout).",
    )
    return parser.parse_args()


def _parse_line_count(detail: str) -> int | None:
    """Extract integer line count from a detail string like 'SKILL.md has 42 lines'."""
    for token in detail.split():
        if token.isdigit():
            return int(token)
    return None


def scan_plugins(plugin_root: Path) -> list[dict]:
    """Scan all plugin directories and return per-plugin line count results."""
    results: list[dict] = []

    if not plugin_root.is_dir():
        return results

    for candidate in sorted(plugin_root.iterdir()):
        if not candidate.is_dir():
            continue
        if not PLUGIN_NAME_RE.match(candidate.name):
            continue

        passed, detail = check_line_count(candidate)
        line_count = _parse_line_count(detail)

        results.append({
            "name": candidate.name,
            "plugin_root": str(candidate),
            "line_count": line_count,
            "limit": LINE_LIMIT,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        })

    return results


def main() -> int:
    args = parse_args()

    if args.plugin_root:
        plugin_root = Path(args.plugin_root).resolve()
    else:
        plugin_root = Path.home() / "personal" / "skill7" / "devtools"

    plugins = scan_plugins(plugin_root)
    all_passed = len(plugins) > 0 and all(p["status"] == "PASS" for p in plugins)

    report = {
        "plugin_root": str(plugin_root),
        "limit": LINE_LIMIT,
        "overall": "PASS" if all_passed else "FAIL",
        "plugins": plugins,
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Scanned {len(plugins)} plugin(s) | Overall: {report['overall']}")
        print(f"Report written to: {out_path}")
        for p in plugins:
            lc = p["line_count"] if p["line_count"] is not None else "?"
            print(f"  {p['name']:20s} {str(lc):>5} lines  {p['status']}")
        return 0 if all_passed else 1
    else:
        # Human-readable table to stdout (grep-friendly)
        print(f"plugin-root: {plugin_root}")
        print(f"{'plugin':<20s} {'lines':>6}  status")
        print("-" * 38)
        for p in plugins:
            lc = p["line_count"] if p["line_count"] is not None else "?"
            print(f"{p['name']:<20s} {str(lc):>6}  {p['status']}")
        print("-" * 38)
        print(f"overall: {report['overall']}")
        return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
