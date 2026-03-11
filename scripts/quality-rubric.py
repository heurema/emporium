#!/usr/bin/env python3
"""quality-rubric.py — 12-point quality rubric for Claude Code plugin evaluation.

Runs 4 structural + 4 safety + 4 quality checks on a plugin.
Outputs a JSON report with per-check pass/fail, total score (0-12),
and a gate result (PASS if score >= 9, FAIL otherwise).

Usage:
    python3 scripts/quality-rubric.py --plugin=herald
    python3 scripts/quality-rubric.py --plugin=arbiter --output=/tmp/arbiter.json
    python3 scripts/quality-rubric.py --plugin=signum --plugin-root=/path/to/devtools
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Resolve lib/ relative to this script so it works from any cwd.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

from lib.rubric import (
    check_skill_md,
    check_required_sections,
    check_line_count,
    check_skill_id_format,
    check_hardcoded_secrets,
    check_no_dangerous_commands,
    check_no_suspicious_urls,
    check_no_shell_true,
    check_has_bench_tasks,
    check_has_examples,
    check_semver,
    check_metadata_complete,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_GATE_THRESHOLD = 9


# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------

STRUCTURAL_CHECKS = [
    ("skill_md_exists", check_skill_md),
    ("required_sections", check_required_sections),
    ("line_count", check_line_count),
    ("skill_id_format", check_skill_id_format),
]

SAFETY_CHECKS = [
    ("no_hardcoded_secrets", check_hardcoded_secrets),
    ("no_dangerous_commands", check_no_dangerous_commands),
    ("no_suspicious_urls", check_no_suspicious_urls),
    ("no_shell_true", check_no_shell_true),
]

QUALITY_CHECKS = [
    ("has_bench_tasks", check_has_bench_tasks),
    ("has_examples", check_has_examples),
    ("semver", check_semver),
    ("metadata_complete", check_metadata_complete),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_plugin_name(name: str) -> None:
    """Validate plugin name to prevent path traversal. Raises ValueError on failure."""
    if not _PLUGIN_NAME_RE.match(name):
        raise ValueError(
            f"Invalid plugin name '{name}'. "
            "Use lowercase alphanumeric with optional hyphens (e.g. 'herald', 'skill-pulse')."
        )


def find_plugin_root(plugin: str, plugin_root_base: Path) -> Path:
    """Locate plugin directory under plugin_root_base/<plugin>."""
    validate_plugin_name(plugin)
    candidate = plugin_root_base / plugin
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(
        f"Plugin '{plugin}' not found at {candidate}. "
        "Use --plugin-root to specify the devtools directory."
    )


def run_checks(
    checks: list[tuple[str, object]],
    plugin_root: Path,
) -> list[dict]:
    """Run a list of (name, fn) checks against plugin_root. Return list of result dicts."""
    results = []
    for check_name, fn in checks:
        try:
            passed, detail = fn(plugin_root)
        except Exception as exc:
            passed = False
            detail = f"check raised exception: {exc}"
        results.append({
            "check_name": check_name,
            "passed": passed,
            "detail": detail,
        })
    return results


def build_report(plugin: str, plugin_root: Path) -> dict:
    """Run all checks and build the full JSON report."""
    structural = run_checks(STRUCTURAL_CHECKS, plugin_root)
    safety = run_checks(SAFETY_CHECKS, plugin_root)
    quality = run_checks(QUALITY_CHECKS, plugin_root)

    all_checks = structural + safety + quality
    total_score = sum(1 for c in all_checks if c["passed"])
    gate_result = "PASS" if total_score >= _GATE_THRESHOLD else "FAIL"

    return {
        "plugin": plugin,
        "plugin_root": str(plugin_root),
        "total_score": total_score,
        "max_score": 12,
        "gate_threshold": _GATE_THRESHOLD,
        "gate_result": gate_result,
        "checks": {
            "structural": structural,
            "safety": safety,
            "quality": quality,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="quality-rubric.py",
        description=(
            "12-point quality rubric for Claude Code plugin evaluation. "
            "Gate: PASS if score >= 9."
        ),
    )
    parser.add_argument(
        "--plugin",
        required=True,
        metavar="NAME",
        help="Plugin name (must exist under --plugin-root/<NAME>/).",
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
        help="Write JSON report to FILE (default: print to stdout).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Validate plugin name first (path traversal protection)
    try:
        validate_plugin_name(args.plugin)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Resolve plugin root base
    if args.plugin_root:
        plugin_root_base = Path(args.plugin_root).resolve()
    else:
        plugin_root_base = Path.home() / "personal" / "skill7" / "devtools"

    # Locate plugin directory
    try:
        plugin_root = find_plugin_root(args.plugin, plugin_root_base)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Run all checks and build report
    report = build_report(args.plugin, plugin_root)

    json_output = json.dumps(report, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_output + "\n", encoding="utf-8")
        print(
            f"Plugin: {args.plugin} | Score: {report['total_score']}/12 | "
            f"Gate: {report['gate_result']}"
        )
        print(f"Report written to: {out_path}")
    else:
        print(json_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
