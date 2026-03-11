#!/usr/bin/env python3
"""check-failure-modes.py — Batch scanner: check required sections in all plugins.

Scans every subdirectory under --plugin-root for a SKILL.md file and reports
whether each has the required sections (description, usage, known failure modes).
Exit 0 if all plugins pass, exit 1 if any fail.

Usage:
    python3 scripts/check-failure-modes.py
    python3 scripts/check-failure-modes.py --plugin-root /path/to/plugins
    python3 scripts/check-failure-modes.py --plugin-root /path/to/plugins --output /tmp/report.json
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

from lib.rubric import check_required_sections

PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check-failure-modes.py",
        description=(
            "Batch scanner: check required sections (description, usage, "
            "known failure modes) in all plugins. "
            "Exit 0 if all pass, exit 1 if any fail."
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


def scan_plugins(plugin_root: Path) -> list[dict]:
    """Scan all plugin directories and return per-plugin required sections results."""
    results: list[dict] = []

    if not plugin_root.is_dir():
        return results

    for candidate in sorted(plugin_root.iterdir()):
        if not candidate.is_dir():
            continue
        if not PLUGIN_NAME_RE.match(candidate.name):
            continue

        passed, detail = check_required_sections(candidate)

        results.append({
            "name": candidate.name,
            "plugin_root": str(candidate),
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
            print(f"  {p['name']:20s} {p['status']}")
        return 0 if all_passed else 1
    else:
        print(f"plugin-root: {plugin_root}")
        print(f"{'plugin':<20s}  status  detail")
        print("-" * 70)
        for p in plugins:
            print(f"{p['name']:<20s}  {p['status']:<6s}  {p['detail']}")
        print("-" * 70)
        print(f"overall: {report['overall']}")
        return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
