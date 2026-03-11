#!/usr/bin/env python3
"""ingestion-gate.py — Security ingestion gate for Claude Code plugin marketplace.

Runs 6 safety checks on a plugin (hardcoded_secrets, dangerous_commands,
suspicious_urls, shell_true, line_count, required_sections). Fails (exit 1) if ANY check fails.
Outputs a JSON report with per-check results and a top-level gate_result (PASS/FAIL).

Usage:
    python3 scripts/ingestion-gate.py --plugin herald
    python3 scripts/ingestion-gate.py --plugin-root /path/to/plugins --plugin myplugin
    python3 scripts/ingestion-gate.py --plugin herald --output /tmp/herald-gate.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Resolve lib/ relative to this script so it works from any cwd.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.ingestion_gate import (
    validate_plugin_name,
    run_ingestion_gate,
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ingestion-gate.py",
        description=(
            "Security ingestion gate for Claude Code plugin marketplace. "
            "Runs 5 safety checks. Exit 0 = PASS, exit 1 = FAIL or error."
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

    # Resolve plugin root base
    if args.plugin_root:
        plugin_root_base = Path(args.plugin_root).resolve()
    else:
        plugin_root_base = Path.home() / "personal" / "skill7" / "devtools"

    # Run ingestion gate — errors produce JSON report with gate_result=FAIL
    try:
        validate_plugin_name(args.plugin)
        report = run_ingestion_gate(args.plugin, plugin_root_base)
    except (ValueError, FileNotFoundError) as exc:
        report = {
            "plugin": args.plugin,
            "plugin_root": str(plugin_root_base / args.plugin),
            "gate_result": "FAIL",
            "error": str(exc),
            "checks": {},
        }

    json_output = json.dumps(report, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_output + "\n", encoding="utf-8")
        print(f"Plugin: {args.plugin} | Gate: {report['gate_result']}")
        print(f"Report written to: {out_path}")
    else:
        print(json_output)

    return 0 if report["gate_result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
