"""ingestion_gate — Core logic for the emporium security ingestion gate.

Importable module: from scripts.ingestion_gate import run_ingestion_gate
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Resolve lib/ relative to this file so imports work from any cwd.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_REPO_ROOT))

from lib.rubric import (
    check_hardcoded_secrets,
    check_no_dangerous_commands,
    check_no_suspicious_urls,
    check_no_shell_true,
    check_line_count,
    check_required_sections,
    check_examples_cap,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

_SAFETY_CHECKS = [
    ("hardcoded_secrets", check_hardcoded_secrets),
    ("dangerous_commands", check_no_dangerous_commands),
    ("suspicious_urls", check_no_suspicious_urls),
    ("shell_true", check_no_shell_true),
    ("line_count", check_line_count),
    ("required_sections", check_required_sections),
    ("examples_cap", check_examples_cap),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_plugin_name(name: str) -> None:
    """Validate plugin name to prevent path traversal. Raises ValueError on failure."""
    if not PLUGIN_NAME_RE.match(name):
        raise ValueError(
            f"Invalid plugin name '{name}'. "
            "Use lowercase alphanumeric with optional hyphens (e.g. 'herald', 'my-plugin')."
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


def run_ingestion_gate(plugin: str, plugin_root_base: Path | str | None = None) -> dict:
    """Run all 6 safety checks on a plugin. Returns the JSON report dict.

    Args:
        plugin: Plugin name (validated against PLUGIN_NAME_RE).
        plugin_root_base: Directory containing plugin subdirectories.
                          Defaults to ~/personal/skill7/devtools/.

    Returns:
        Report dict with keys: plugin, plugin_root, gate_result, checks.
        gate_result is "PASS" if all checks passed, "FAIL" otherwise.

    Raises:
        ValueError: If plugin name is invalid.
        FileNotFoundError: If plugin directory does not exist.
    """
    if plugin_root_base is None:
        plugin_root_base = Path.home() / "personal" / "skill7" / "devtools"
    plugin_root_base = Path(plugin_root_base)

    plugin_root = find_plugin_root(plugin, plugin_root_base)

    checks: dict[str, dict] = {}
    all_passed = True

    for check_name, fn in _SAFETY_CHECKS:
        try:
            passed, detail = fn(plugin_root)
        except Exception as exc:
            passed = False
            detail = f"check raised exception: {exc}"
        checks[check_name] = {"passed": passed, "detail": detail}
        if not passed:
            all_passed = False

    gate_result = "PASS" if all_passed else "FAIL"

    return {
        "plugin": plugin,
        "plugin_root": str(plugin_root),
        "gate_result": gate_result,
        "checks": checks,
    }
