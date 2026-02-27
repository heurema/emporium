#!/usr/bin/env python3
"""Cross-source documentation consistency checker for heurema plugin ecosystem.

Canonical source of truth: each plugin's .claude-plugin/plugin.json
Mirrors that must stay in sync: skill7.dev plugin-meta.json, CHANGELOG.md

Designed to run from the fabrica workspace root (parent of all plugin repos).
When run from emporium/scripts/, FABRICA_ROOT is auto-detected as ../..

Usage:
    python3 scripts/check_consistency.py              # check all
    python3 scripts/check_consistency.py --json       # machine-readable output
    FABRICA_ROOT=/path/to/fabrica python3 scripts/check_consistency.py  # explicit root
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Auto-detect workspace root: env var > script location (../../ from emporium/scripts/)
_script_dir = Path(__file__).resolve().parent
if os.environ.get("FABRICA_ROOT"):
    FABRICA_ROOT = Path(os.environ["FABRICA_ROOT"]).resolve()
else:
    # emporium/scripts/check_consistency.py → emporium → fabrica
    FABRICA_ROOT = _script_dir.parent.parent

SITE_META = FABRICA_ROOT / "skill7.dev" / "src" / "data" / "plugin-meta.json"
SITE_MARKETPLACE = FABRICA_ROOT / "skill7.dev" / "src" / "data" / "marketplace.json"
EMPORIUM_MARKETPLACE = FABRICA_ROOT / "emporium" / ".claude-plugin" / "marketplace.json"

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CHANGELOG_VERSION_RE = re.compile(r"##\s*\[(\d+\.\d+\.\d+)\]")


def _discover_plugins() -> list[Path]:
    if not FABRICA_ROOT.exists():
        return []
    return [
        d
        for d in FABRICA_ROOT.iterdir()
        if d.is_dir()
        and (d / ".claude-plugin").is_dir()
        and d.name not in {"skill7.dev", ".git", ".claude", "scripts", "docs"}
    ]


PLUGIN_DIRS = _discover_plugins()


class Finding:
    def __init__(self, severity: str, plugin: str, message: str, sources: dict[str, str] | None = None):
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW
        self.plugin = plugin
        self.message = message
        self.sources = sources or {}

    def __str__(self) -> str:
        src = ""
        if self.sources:
            pairs = [f"{k}={v}" for k, v in self.sources.items()]
            src = f" ({', '.join(pairs)})"
        return f"[{self.severity}] {self.plugin}: {self.message}{src}"

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "plugin": self.plugin,
            "message": self.message,
            "sources": self.sources,
        }


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_plugin_json(plugin_dir: Path) -> dict | None:
    p = plugin_dir / ".claude-plugin" / "plugin.json"
    return load_json(p)


def get_marketplace_json(plugin_dir: Path) -> dict | None:
    p = plugin_dir / ".claude-plugin" / "marketplace.json"
    return load_json(p)


def get_changelog_version(plugin_dir: Path) -> str | None:
    p = plugin_dir / "CHANGELOG.md"
    if not p.exists():
        return None
    m = CHANGELOG_VERSION_RE.search(p.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def check_plugin_json_schema(plugin_dir: Path, findings: list[Finding]) -> None:
    """Validate plugin.json has required fields and valid semver."""
    name = plugin_dir.name
    pj = get_plugin_json(plugin_dir)

    if pj is None:
        # emporium-like repos may not have plugin.json
        mkt = get_marketplace_json(plugin_dir)
        if mkt is not None:
            return  # marketplace-only repo, ok
        findings.append(Finding("MEDIUM", name, "No plugin.json or marketplace.json found"))
        return

    required = ["name", "version", "description", "author", "license"]
    for field in required:
        if field not in pj or pj[field] is None:
            findings.append(Finding("HIGH", name, f"plugin.json missing required field: {field}"))

    # Type safety: version must be a string before regex
    version = pj.get("version")
    if not isinstance(version, str):
        if version is not None:
            findings.append(Finding("HIGH", name, f"plugin.json version is not a string: {type(version).__name__}"))
    elif not SEMVER_RE.match(version):
        findings.append(Finding("HIGH", name, f"plugin.json version is not valid semver: {version}"))

    # Name coherence: plugin.json name should match directory name
    pj_name = pj.get("name")
    if isinstance(pj_name, str) and pj_name != name:
        findings.append(
            Finding("HIGH", name, "plugin.json name doesn't match directory name",
                    {"plugin.json": pj_name, "directory": name})
        )


def check_marketplace_components(plugin_dir: Path, findings: list[Finding]) -> None:
    """Verify marketplace.json component paths actually exist."""
    name = plugin_dir.name
    mkt = get_marketplace_json(plugin_dir)
    if mkt is None:
        return

    for plugin_entry in mkt.get("plugins", []):
        for component_type in ("skills", "commands", "agents", "hooks"):
            declared = plugin_entry.get(component_type, [])
            for path_str in declared:
                component_path = plugin_dir / path_str
                if not component_path.exists():
                    findings.append(
                        Finding(
                            "HIGH",
                            name,
                            f"marketplace.json declares {component_type}: {path_str!r} but path does not exist",
                        )
                    )

        # Validate paths are relative (Codex feedback: absolute paths bypass checks)
        for component_type in ("skills", "commands", "agents", "hooks"):
            for path_str in plugin_entry.get(component_type, []):
                if Path(path_str).is_absolute():
                    findings.append(
                        Finding("HIGH", name, f"marketplace.json {component_type} has absolute path: {path_str!r}")
                    )

        # Check for undeclared components that exist on disk
        for component_type, dir_name in [
            ("hooks", "hooks"),
            ("skills", "skills"),
            ("commands", "commands"),
            ("agents", "agents"),
        ]:
            dir_path = plugin_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                declared = plugin_entry.get(component_type, [])
                matching = any(
                    (plugin_dir / p).resolve() == dir_path.resolve()
                    for p in declared
                )
                if not matching:
                    findings.append(
                        Finding(
                            "MEDIUM",
                            name,
                            f"{dir_name}/ directory exists but not declared in marketplace.json {component_type}",
                        )
                    )


def check_version_consistency(
    plugin_dir: Path, findings: list[Finding], site_meta_cache: dict | None = None
) -> None:
    """Cross-check version across plugin.json, CHANGELOG, and site plugin-meta.json."""
    name = plugin_dir.name
    pj = get_plugin_json(plugin_dir)
    if pj is None:
        return

    canonical_version = pj.get("version")
    if not isinstance(canonical_version, str) or not canonical_version:
        return

    sources: dict[str, str] = {"plugin.json": canonical_version}

    # Check CHANGELOG
    changelog_version = get_changelog_version(plugin_dir)
    if changelog_version:
        sources["CHANGELOG.md"] = changelog_version
        if changelog_version != canonical_version:
            findings.append(
                Finding(
                    "HIGH",
                    name,
                    "Version mismatch: plugin.json vs CHANGELOG.md",
                    {"plugin.json": canonical_version, "CHANGELOG.md": changelog_version},
                )
            )

    # Check site plugin-meta.json (preloaded for efficiency)
    site_meta = site_meta_cache if site_meta_cache is not None else load_json(SITE_META)
    if site_meta:
        plugin_meta = site_meta.get("plugins", {}).get(name)
        if plugin_meta:
            site_version = plugin_meta.get("version", "")
            sources["plugin-meta.json"] = site_version
            if site_version and site_version != canonical_version:
                findings.append(
                    Finding(
                        "CRITICAL",
                        name,
                        "Version mismatch: plugin.json vs skill7.dev plugin-meta.json",
                        {"plugin.json": canonical_version, "plugin-meta.json": site_version},
                    )
                )


def check_description_consistency(findings: list[Finding]) -> None:
    """Cross-check plugin descriptions between plugin.json, marketplace.json, and site."""
    site_marketplace = load_json(SITE_MARKETPLACE)
    emporium_mkt = load_json(EMPORIUM_MARKETPLACE)

    if not site_marketplace or not emporium_mkt:
        return

    # Build lookup: name → description from each source
    site_descs: dict[str, str] = {}
    for p in site_marketplace.get("plugins", []):
        site_descs[p["name"]] = p["description"]

    emporium_descs: dict[str, str] = {}
    for p in emporium_mkt.get("plugins", []):
        emporium_descs[p["name"]] = p["description"]

    # Compare site vs emporium
    for name in site_descs:
        if name in emporium_descs and site_descs[name] != emporium_descs[name]:
            findings.append(
                Finding(
                    "MEDIUM",
                    name,
                    "Description mismatch: skill7.dev marketplace.json vs emporium marketplace.json",
                    {
                        "site": site_descs[name][:80] + "...",
                        "emporium": emporium_descs[name][:80] + "...",
                    },
                )
            )


def check_emporium_vs_site(findings: list[Finding]) -> None:
    """Ensure emporium and site list the same plugins."""
    site_marketplace = load_json(SITE_MARKETPLACE)
    emporium_mkt = load_json(EMPORIUM_MARKETPLACE)

    if not site_marketplace or not emporium_mkt:
        return

    site_names = {p["name"] for p in site_marketplace.get("plugins", [])}
    emporium_names = {p["name"] for p in emporium_mkt.get("plugins", [])}

    for name in emporium_names - site_names:
        findings.append(Finding("HIGH", name, "Plugin in emporium but missing from skill7.dev"))
    for name in site_names - emporium_names:
        findings.append(Finding("HIGH", name, "Plugin on skill7.dev but missing from emporium"))


def check_site_meta_completeness(findings: list[Finding]) -> None:
    """Ensure every plugin in marketplace.json has an entry in plugin-meta.json."""
    site_marketplace = load_json(SITE_MARKETPLACE)
    site_meta = load_json(SITE_META)

    if not site_marketplace or not site_meta:
        return

    meta_plugins = site_meta.get("plugins", {})
    for p in site_marketplace.get("plugins", []):
        name = p["name"]
        if name not in meta_plugins:
            findings.append(Finding("HIGH", name, "Plugin in marketplace.json but missing from plugin-meta.json"))
        else:
            entry = meta_plugins[name]
            if not entry.get("version"):
                findings.append(Finding("MEDIUM", name, "No version in plugin-meta.json"))
            if not entry.get("tags"):
                findings.append(Finding("LOW", name, "No tags in plugin-meta.json"))


def main() -> int:
    json_mode = "--json" in sys.argv
    findings: list[Finding] = []

    # Preload shared data once (Codex feedback: avoid redundant reads)
    site_meta_cache = load_json(SITE_META)

    # Per-plugin checks
    for plugin_dir in sorted(PLUGIN_DIRS):
        check_plugin_json_schema(plugin_dir, findings)
        check_marketplace_components(plugin_dir, findings)
        check_version_consistency(plugin_dir, findings, site_meta_cache)

    # Cross-source checks
    check_description_consistency(findings)
    check_emporium_vs_site(findings)
    check_site_meta_completeness(findings)

    if json_mode:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        if not findings:
            print("All consistency checks passed.")
            return 0

        by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        for f in findings:
            by_severity[f.severity].append(f)

        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            if by_severity[sev]:
                print(f"\n{'=' * 60}")
                print(f"  {sev} ({len(by_severity[sev])})")
                print(f"{'=' * 60}")
                for f in by_severity[sev]:
                    print(f"  {f}")

        total = len(findings)
        crit = len(by_severity["CRITICAL"])
        high = len(by_severity["HIGH"])
        print(f"\n{total} findings: {crit} critical, {high} high, {len(by_severity['MEDIUM'])} medium, {len(by_severity['LOW'])} low")

    has_blocking = any(f.severity in ("CRITICAL", "HIGH") for f in findings)
    return 1 if has_blocking else 0


if __name__ == "__main__":
    sys.exit(main())
