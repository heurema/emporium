"""lib/rubric — Pure check functions for Claude Code plugin quality scoring.

Each check function returns (passed: bool, detail: str).
All functions are pure and testable in isolation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")

_SKILL_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Secrets: literal patterns that indicate hardcoded credentials.
# Environment variable references (os.environ, $VAR) are excluded.
_SECRET_PATTERNS = [
    re.compile(r'(?i)(AWS_SECRET_ACCESS?_KEY|AWS_SECRET_KEY)\s*=\s*["\'][^"\']{8,}["\']'),
    re.compile(r'(?i)(OPENAI_API_KEY|OPENAI_KEY)\s*=\s*["\'][^"\']{8,}["\']'),
    re.compile(r'(?i)(DATABASE_PASSWORD|DB_PASSWORD)\s*=\s*["\'][^"\']{4,}["\']'),
    re.compile(r'(?i)(API_SECRET|SECRET_KEY|PRIVATE_KEY)\s*=\s*["\'][^"\']{8,}["\']'),
    re.compile(r'(?i)(ANTHROPIC_API_KEY|CLAUDE_API_KEY)\s*=\s*["\'][^"\']{8,}["\']'),
    re.compile(r'(?i)(GITHUB_TOKEN|GH_TOKEN)\s*=\s*["\'][^"\']{8,}["\']'),
    # PII patterns
    re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'),
    re.compile(r'\b(?!127\.0\.0\.1\b)(?!0\.0\.0\.0\b)(?:\d{1,3}\.){3}\d{1,3}\b'),
]

# Dangerous command patterns (direct shell commands, not variable refs).
_DANGEROUS_CMD_PATTERNS = [
    re.compile(r"rm\s+-rf\s+/(?:\s|$)"),
    re.compile(r"\bsudo\b"),
    re.compile(r"eval\s+\$\{?(?:user|input|arg|param|request|query)", re.IGNORECASE),
]

# Suspicious URL patterns: non-https schemes, known malware TLDs.
_SUSPICIOUS_URL_RE = re.compile(r"\bhttp://(?!localhost|127\.0\.0\.1)")
_MALWARE_DOMAIN_RE = re.compile(
    r"https?://[^\s\"']*\.(xyz|tk|ml|ga|cf|gq|pw|top|club|work|party|link)\b",
    re.IGNORECASE,
)

# Required fields in plugin.json.
_REQUIRED_PLUGIN_FIELDS = {"name", "version", "description", "author"}

# Sections that satisfy the "usage" requirement (case-insensitive).
_USAGE_SECTION_ALIASES = {
    "usage",
    "how to use",
    "how to check",
    "command surface",
    "commands",
    "when to use",
    "available commands",
    "typical flow",
}

# Sections that satisfy the "known failure modes" requirement.
_FAILURE_SECTION_ALIASES = {
    "known failure modes",
    "known failures",
    "failure modes",
    "error handling",
    "errors",
    "caveats",
    "limitations",
    "troubleshooting",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> tuple[Optional[str], Optional[str]]:
    """Read file text; return (text, None) or (None, error_detail)."""
    try:
        return path.read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return None, f"file not found: {path}"
    except OSError as exc:
        return None, f"cannot read {path}: {exc}"


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract simple key: value pairs from YAML-style frontmatter (--- ... ---)."""
    result: dict[str, str] = {}
    if not text.startswith("---"):
        return result
    end = text.find("\n---", 3)
    if end == -1:
        return result
    block = text[3:end]
    for line in block.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            # YAML block scalar indicators: store key with sentinel
            if val in (">", ">-", "|", "|-"):
                result[key.strip()] = "(block scalar)"
            else:
                result[key.strip()] = val
    return result


def _extract_sections(text: str) -> set[str]:
    """Return the set of lowercased ## heading names."""
    return {m.group(1).strip().lower() for m in re.finditer(r"^##\s+(.+)$", text, re.MULTILINE)}


def _find_skill_md(plugin_root: Path) -> Optional[Path]:
    """Locate the primary SKILL.md for a plugin (first found under skills/)."""
    skills_dir = plugin_root / "skills"
    if not skills_dir.is_dir():
        return None
    for candidate in sorted(skills_dir.iterdir()):
        skill_file = candidate / "SKILL.md"
        if skill_file.is_file():
            return skill_file
    return None


def _collect_scan_files(plugin_root: Path) -> list[Path]:
    """Return files to scan for secrets/danger/urls: primary SKILL.md + Python files under skills/."""
    files: list[Path] = []
    skill_md = _find_skill_md(plugin_root)
    if skill_md:
        files.append(skill_md)
    skills_dir = plugin_root / "skills"
    if skills_dir.is_dir():
        files.extend(sorted(skills_dir.rglob("*.py")))
    return files


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------

def check_skill_md(plugin_root: str | Path) -> tuple[bool, str]:
    """Check that a SKILL.md file exists under skills/<name>/SKILL.md.

    Returns (passed, detail).
    """
    root = Path(plugin_root)
    if not root.is_dir():
        return False, f"plugin root not found: {root}"
    skill_md = _find_skill_md(root)
    if skill_md is None:
        return False, f"no SKILL.md found under {root / 'skills'}/"
    return True, f"found {skill_md.relative_to(root)}"


def check_required_sections(plugin_root: str | Path) -> tuple[bool, str]:
    """Check that SKILL.md has description, usage, and known-failure-modes sections.

    Description can be in frontmatter `description:` field or a ## Description heading.
    Usage matches several section name aliases.
    Known failure modes matches several aliases.
    """
    root = Path(plugin_root)
    skill_md = _find_skill_md(root)
    if skill_md is None:
        return False, "SKILL.md not found; cannot check sections"

    text, err = _read_text(skill_md)
    if text is None:
        return False, err

    fm = _parse_frontmatter(text)
    sections = _extract_sections(text)

    missing: list[str] = []

    # Description: frontmatter field OR ## Description heading
    has_description = bool(fm.get("description")) or "description" in sections
    if not has_description:
        missing.append("description (frontmatter or ## Description)")

    # Usage
    has_usage = bool(_USAGE_SECTION_ALIASES & sections)
    if not has_usage:
        missing.append("usage (## Usage / ## Commands / ## When to use / etc)")

    # Known failure modes
    has_failure = bool(_FAILURE_SECTION_ALIASES & sections)
    if not has_failure:
        missing.append("known failure modes (## Error Handling / ## Known Failures / etc)")

    if missing:
        return False, "missing sections: " + "; ".join(missing)
    return True, "all required sections present"


def check_line_count(plugin_root: str | Path) -> tuple[bool, str]:
    """Check that the primary SKILL.md is <= 300 lines."""
    root = Path(plugin_root)
    skill_md = _find_skill_md(root)
    if skill_md is None:
        return False, "SKILL.md not found; cannot check line count"

    text, err = _read_text(skill_md)
    if text is None:
        return False, err

    count = len(text.splitlines())
    if count > 300:
        return False, f"SKILL.md has {count} lines (limit: 300)"
    return True, f"SKILL.md has {count} lines"


def check_skill_id_format(plugin_root: str | Path) -> tuple[bool, str]:
    """Check that the skill_id in SKILL.md frontmatter matches ^[a-z0-9]+(-[a-z0-9]+)*$.

    The `name:` field in frontmatter is used as the skill_id.
    """
    root = Path(plugin_root)
    skill_md = _find_skill_md(root)
    if skill_md is None:
        return False, "SKILL.md not found; cannot check skill_id"

    text, err = _read_text(skill_md)
    if text is None:
        return False, err

    fm = _parse_frontmatter(text)
    skill_id = fm.get("name", "").strip()

    if not skill_id:
        return False, "no 'name' field in SKILL.md frontmatter"
    if not _SKILL_ID_RE.match(skill_id):
        return False, f"skill_id '{skill_id}' does not match ^[a-z0-9]+(-[a-z0-9]+)*$"
    return True, f"skill_id '{skill_id}' is valid"


# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------

def check_hardcoded_secrets(plugin_root: str | Path) -> tuple[bool, str]:
    """Check for hardcoded secrets/API keys in SKILL.md and Python files under skills/."""
    root = Path(plugin_root)
    files = _collect_scan_files(root)
    if not files:
        return True, "no files to scan (skills/ missing or empty)"

    findings: list[str] = []
    read_errors: list[str] = []
    for f in files:
        text, err = _read_text(f)
        if text is None:
            read_errors.append(err)
            continue
        for pat in _SECRET_PATTERNS:
            if pat.search(text):
                findings.append(f"{f.name}: matches {pat.pattern[:40]}...")

    if findings:
        return False, "hardcoded secrets detected: " + "; ".join(findings)
    if read_errors:
        return False, "cannot scan all files (fail-closed): " + "; ".join(read_errors)
    return True, f"no hardcoded secrets found in {len(files)} file(s)"


def check_no_dangerous_commands(plugin_root: str | Path) -> tuple[bool, str]:
    """Check for dangerous shell commands in SKILL.md and bench/tasks/ files."""
    root = Path(plugin_root)

    files: list[Path] = []
    skill_md = _find_skill_md(root)
    if skill_md:
        files.append(skill_md)

    # Also check commands/ and bench/tasks/
    for subdir in ("commands", "bench/tasks"):
        d = root / subdir
        if d.is_dir():
            files.extend(sorted(d.glob("*.md")))

    if not files:
        return True, "no files to scan"

    findings: list[str] = []
    read_errors: list[str] = []
    for f in files:
        text, err = _read_text(f)
        if text is None:
            read_errors.append(err)
            continue
        for pat in _DANGEROUS_CMD_PATTERNS:
            if pat.search(text):
                findings.append(f"{f.name}: matches pattern '{pat.pattern}'")

    if findings:
        return False, "dangerous commands detected: " + "; ".join(findings)
    if read_errors:
        return False, "cannot scan all files (fail-closed): " + "; ".join(read_errors)
    return True, f"no dangerous commands found in {len(files)} file(s)"


def check_no_suspicious_urls(plugin_root: str | Path) -> tuple[bool, str]:
    """Check for non-https URLs and suspicious domains in SKILL.md."""
    root = Path(plugin_root)
    skill_md = _find_skill_md(root)
    if skill_md is None:
        return True, "no SKILL.md to scan"

    text, err = _read_text(skill_md)
    if text is None:
        return False, f"cannot read SKILL.md (fail-closed): {err}"

    findings: list[str] = []
    for m in _SUSPICIOUS_URL_RE.finditer(text):
        findings.append(f"non-https URL: {m.group(0)[:60]}")
    for m in _MALWARE_DOMAIN_RE.finditer(text):
        findings.append(f"suspicious domain: {m.group(0)[:60]}")

    if findings:
        return False, "; ".join(findings)
    return True, "no suspicious URLs found"


def check_no_shell_true(plugin_root: str | Path) -> tuple[bool, str]:
    """Check for shell=True in Python files under skills/ without a trust comment."""
    root = Path(plugin_root)
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return True, "no skills/ directory to scan"

    py_files = sorted(skills_dir.rglob("*.py"))
    if not py_files:
        return True, "no Python files under skills/"

    findings: list[str] = []
    read_errors: list[str] = []
    for f in py_files:
        text, err = _read_text(f)
        if text is None:
            read_errors.append(err)
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "shell=True" in line:
                # Allowed if the same line or the preceding lines have a trust comment
                context_lines = text.splitlines()[max(0, i - 4):i]
                context = "\n".join(context_lines)
                if "TRUST BOUNDARY" not in context and "# trust" not in context.lower():
                    findings.append(f"{f.name}:{i}: shell=True without trust comment")

    if findings:
        return False, "shell=True without trust comment: " + "; ".join(findings)
    if read_errors:
        return False, "cannot scan all files (fail-closed): " + "; ".join(read_errors)
    return True, f"no unguarded shell=True in {len(py_files)} Python file(s)"


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def check_has_bench_tasks(plugin_root: str | Path) -> tuple[bool, str]:
    """Check that bench/tasks/ exists and contains at least one .md task file."""
    root = Path(plugin_root)
    tasks_dir = root / "bench" / "tasks"
    if not tasks_dir.is_dir():
        return False, f"bench/tasks/ directory not found at {tasks_dir}"

    task_files = sorted(tasks_dir.glob("*.md"))
    if not task_files:
        return False, f"bench/tasks/ exists but contains no .md task files"
    return True, f"found {len(task_files)} bench task(s)"


def check_has_examples(plugin_root: str | Path) -> tuple[bool, str]:
    """Check that SKILL.md contains examples (code blocks or an Examples section)."""
    root = Path(plugin_root)
    skill_md = _find_skill_md(root)
    if skill_md is None:
        return False, "SKILL.md not found; cannot check for examples"

    text, err = _read_text(skill_md)
    if text is None:
        return False, err

    sections = _extract_sections(text)
    has_examples_section = any(
        s in sections for s in ("examples", "example", "example usage", "usage examples")
    )
    has_code_block = "```" in text

    if has_examples_section or has_code_block:
        return True, "examples present (code block or ## Examples section)"
    return False, "no examples found (no ``` code blocks and no ## Examples section)"


def check_semver(plugin_root: str | Path) -> tuple[bool, str]:
    """Check that version in plugin.json follows semantic versioning (X.Y.Z)."""
    root = Path(plugin_root)
    plugin_json = root / ".claude-plugin" / "plugin.json"

    text, err = _read_text(plugin_json)
    if text is None:
        return False, f"plugin.json not readable: {err}"

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"plugin.json is not valid JSON: {exc}"

    version = data.get("version", "")
    if not version:
        return False, "no 'version' field in plugin.json"
    if not _SEMVER_RE.match(str(version)):
        return False, f"version '{version}' does not match semver X.Y.Z"
    return True, f"version '{version}' is valid semver"


def check_metadata_complete(plugin_root: str | Path) -> tuple[bool, str]:
    """Check that plugin.json has all required fields: name, version, description, author."""
    root = Path(plugin_root)
    plugin_json = root / ".claude-plugin" / "plugin.json"

    text, err = _read_text(plugin_json)
    if text is None:
        return False, f"plugin.json not readable: {err}"

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"plugin.json is not valid JSON: {exc}"

    missing = [f for f in _REQUIRED_PLUGIN_FIELDS if not data.get(f)]
    if missing:
        return False, f"missing required fields in plugin.json: {', '.join(sorted(missing))}"
    return True, f"all required metadata fields present ({', '.join(sorted(_REQUIRED_PLUGIN_FIELDS))})"
