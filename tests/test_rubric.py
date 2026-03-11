"""Tests for lib/rubric — all 12 check functions (pass and fail cases)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure lib/ is importable when running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
# Helpers — build minimal plugin fixture
# ---------------------------------------------------------------------------

def _make_plugin(
    tmp_path: Path,
    *,
    skill_name: str = "my-skill",
    skill_md_content: str | None = None,
    plugin_json: dict | None = None,
    bench_task_files: list[str] | None = None,
    extra_py: dict[str, str] | None = None,
) -> Path:
    """Create a minimal well-formed plugin directory under tmp_path."""
    root = tmp_path / "plugin"
    root.mkdir()

    if skill_md_content is not None:
        skill_dir = root / "skills" / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

    if plugin_json is not None:
        meta_dir = root / ".claude-plugin"
        meta_dir.mkdir()
        (meta_dir / "plugin.json").write_text(json.dumps(plugin_json), encoding="utf-8")

    if bench_task_files is not None:
        tasks_dir = root / "bench" / "tasks"
        tasks_dir.mkdir(parents=True)
        for fname in bench_task_files:
            (tasks_dir / fname).write_text("# task", encoding="utf-8")

    if extra_py is not None:
        for rel_path, content in extra_py.items():
            py_file = root / rel_path
            py_file.parent.mkdir(parents=True, exist_ok=True)
            py_file.write_text(content, encoding="utf-8")

    return root


_GOOD_SKILL_MD = """\
---
name: my-skill
description: Does something useful.
version: 1.0.0
---

## Usage

Run `/my-skill` to do the thing.

```bash
/my-skill --flag
```

## Known Failure Modes

- Network may be unavailable.
"""


# ---------------------------------------------------------------------------
# check_skill_md
# ---------------------------------------------------------------------------

class TestCheckSkillMd:
    def test_pass_skill_md_exists(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, detail = check_skill_md(root)
        assert passed is True
        assert "SKILL.md" in detail.lower() or "found" in detail.lower()

    def test_fail_no_skills_dir(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)  # no skill_md_content
        passed, detail = check_skill_md(root)
        assert passed is False
        assert "SKILL.md" in detail or "skills" in detail.lower()

    def test_fail_plugin_root_missing(self, tmp_path: Path) -> None:
        passed, detail = check_skill_md(tmp_path / "does-not-exist")
        assert passed is False
        assert "not found" in detail

    def test_pass_accepts_string_path(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, _ = check_skill_md(str(root))
        assert passed is True


# ---------------------------------------------------------------------------
# check_required_sections
# ---------------------------------------------------------------------------

class TestCheckRequiredSections:
    def test_pass_all_sections_present(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, detail = check_required_sections(root)
        assert passed is True
        assert "present" in detail

    def test_fail_missing_usage(self, tmp_path: Path) -> None:
        content = """\
---
name: my-skill
description: Does something.
---

## Known Failure Modes

- none
"""
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_required_sections(root)
        assert passed is False
        assert "usage" in detail.lower()

    def test_fail_missing_failure_modes(self, tmp_path: Path) -> None:
        content = """\
---
name: my-skill
description: Does something.
---

## Usage

Run `/skill`.
"""
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_required_sections(root)
        assert passed is False
        assert "failure" in detail.lower() or "known" in detail.lower()

    def test_fail_missing_description(self, tmp_path: Path) -> None:
        content = """\
## Usage

Run `/skill`.

## Known Failure Modes

- none
"""
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_required_sections(root)
        assert passed is False
        assert "description" in detail.lower()

    def test_fail_no_skill_md(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_required_sections(root)
        assert passed is False
        assert "SKILL.md" in detail

    def test_pass_description_as_heading(self, tmp_path: Path) -> None:
        content = """\
## Description

Does something.

## Usage

Run `/skill`.

## Known Failure Modes

- none
"""
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_required_sections(root)
        assert passed is True

    def test_pass_section_alias_commands(self, tmp_path: Path) -> None:
        """'## Commands' is an alias for usage."""
        content = """\
---
description: Does something.
---

## Commands

/skill run

## Errors

- network fail
"""
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, _ = check_required_sections(root)
        assert passed is True


# ---------------------------------------------------------------------------
# check_line_count
# ---------------------------------------------------------------------------

class TestCheckLineCount:
    def test_pass_short_file(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, detail = check_line_count(root)
        assert passed is True
        assert "lines" in detail

    def test_fail_over_300_lines(self, tmp_path: Path) -> None:
        long_content = "\n".join(["# line"] * 301)
        root = _make_plugin(tmp_path, skill_md_content=long_content)
        passed, detail = check_line_count(root)
        assert passed is False
        assert "301" in detail

    def test_pass_exactly_300_lines(self, tmp_path: Path) -> None:
        content = "\n".join(["x"] * 300)
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_line_count(root)
        assert passed is True
        assert "300" in detail

    def test_fail_no_skill_md(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_line_count(root)
        assert passed is False
        assert "SKILL.md" in detail


# ---------------------------------------------------------------------------
# check_skill_id_format
# ---------------------------------------------------------------------------

class TestCheckSkillIdFormat:
    def test_pass_valid_id(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, detail = check_skill_id_format(root)
        assert passed is True
        assert "my-skill" in detail

    def test_fail_id_with_uppercase(self, tmp_path: Path) -> None:
        content = "---\nname: MySkill\n---\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_skill_id_format(root)
        assert passed is False
        assert "MySkill" in detail

    def test_fail_id_with_spaces(self, tmp_path: Path) -> None:
        content = "---\nname: my skill\n---\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_skill_id_format(root)
        assert passed is False

    def test_fail_no_name_field(self, tmp_path: Path) -> None:
        content = "---\nversion: 1.0.0\n---\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_skill_id_format(root)
        assert passed is False
        assert "name" in detail

    def test_pass_numeric_segments(self, tmp_path: Path) -> None:
        content = "---\nname: skill2\n---\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, _ = check_skill_id_format(root)
        assert passed is True

    def test_fail_no_skill_md(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_skill_id_format(root)
        assert passed is False
        assert "SKILL.md" in detail


# ---------------------------------------------------------------------------
# check_hardcoded_secrets
# ---------------------------------------------------------------------------

class TestCheckHardcodedSecrets:
    def test_pass_no_secrets(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, detail = check_hardcoded_secrets(root)
        assert passed is True

    def test_fail_api_key_in_skill_md(self, tmp_path: Path) -> None:
        content = _GOOD_SKILL_MD + '\nOPENAI_API_KEY = "sk-abcdefgh1234"\n'
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_hardcoded_secrets(root)
        assert passed is False
        assert "secret" in detail.lower() or "OPENAI" in detail

    def test_fail_secret_in_python_file(self, tmp_path: Path) -> None:
        root = _make_plugin(
            tmp_path,
            skill_md_content=_GOOD_SKILL_MD,
            extra_py={"skills/my-skill/runner.py": 'GITHUB_TOKEN = "ghp_abcdefghij1234"\n'},
        )
        passed, detail = check_hardcoded_secrets(root)
        assert passed is False
        assert "secret" in detail.lower() or "GITHUB" in detail

    def test_pass_no_skills_dir(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_hardcoded_secrets(root)
        assert passed is True
        assert "no files" in detail.lower() or "missing" in detail.lower()

    def test_fail_email_in_skill_md(self, tmp_path: Path) -> None:
        content = _GOOD_SKILL_MD + "\nContact: admin@example.com\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_hardcoded_secrets(root)
        assert passed is False


# ---------------------------------------------------------------------------
# check_no_dangerous_commands
# ---------------------------------------------------------------------------

class TestCheckNoDangerousCommands:
    def test_pass_safe_content(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, detail = check_no_dangerous_commands(root)
        assert passed is True

    def test_fail_rm_rf_root(self, tmp_path: Path) -> None:
        content = _GOOD_SKILL_MD + "\n```\nrm -rf /\n```\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_no_dangerous_commands(root)
        assert passed is False
        assert "dangerous" in detail.lower()

    def test_fail_sudo_in_skill_md(self, tmp_path: Path) -> None:
        content = _GOOD_SKILL_MD + "\nRun `sudo apt install foo`.\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_no_dangerous_commands(root)
        assert passed is False
        assert "dangerous" in detail.lower()

    def test_fail_sudo_in_bench_task(self, tmp_path: Path) -> None:
        root = _make_plugin(
            tmp_path,
            skill_md_content=_GOOD_SKILL_MD,
            bench_task_files=["task1.md"],
        )
        # Overwrite task with dangerous content
        task_file = root / "bench" / "tasks" / "task1.md"
        task_file.write_text("# task\n\nsudo rm -rf /tmp/x\n", encoding="utf-8")
        passed, detail = check_no_dangerous_commands(root)
        assert passed is False

    def test_pass_no_files(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_no_dangerous_commands(root)
        assert passed is True
        assert "no files" in detail.lower()


# ---------------------------------------------------------------------------
# check_no_suspicious_urls
# ---------------------------------------------------------------------------

class TestCheckNoSuspiciousUrls:
    def test_pass_https_url(self, tmp_path: Path) -> None:
        content = _GOOD_SKILL_MD + "\nSee https://example.com for details.\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_no_suspicious_urls(root)
        assert passed is True

    def test_fail_http_url(self, tmp_path: Path) -> None:
        content = _GOOD_SKILL_MD + "\nSee http://example.com/docs.\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_no_suspicious_urls(root)
        assert passed is False
        assert "non-https" in detail.lower() or "http" in detail.lower()

    def test_fail_suspicious_tld(self, tmp_path: Path) -> None:
        content = _GOOD_SKILL_MD + "\nDownload from https://malware.xyz/payload.\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_no_suspicious_urls(root)
        assert passed is False
        assert "suspicious" in detail.lower() or ".xyz" in detail

    def test_pass_localhost_http(self, tmp_path: Path) -> None:
        content = _GOOD_SKILL_MD + "\nAPI at http://localhost:8080/health.\n"
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_no_suspicious_urls(root)
        assert passed is True

    def test_pass_no_skill_md(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_no_suspicious_urls(root)
        assert passed is True
        assert "no SKILL.md" in detail


# ---------------------------------------------------------------------------
# check_no_shell_true
# ---------------------------------------------------------------------------

class TestCheckNoShellTrue:
    def test_pass_no_python_files(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, detail = check_no_shell_true(root)
        assert passed is True

    def test_pass_shell_true_with_trust_comment(self, tmp_path: Path) -> None:
        py_content = """\
import subprocess
# TRUST BOUNDARY: controlled input from config
result = subprocess.run(cmd, shell=True)
"""
        root = _make_plugin(
            tmp_path,
            skill_md_content=_GOOD_SKILL_MD,
            extra_py={"skills/my-skill/runner.py": py_content},
        )
        passed, detail = check_no_shell_true(root)
        assert passed is True

    def test_fail_bare_shell_true(self, tmp_path: Path) -> None:
        py_content = """\
import subprocess
result = subprocess.run(cmd, shell=True)
"""
        root = _make_plugin(
            tmp_path,
            skill_md_content=_GOOD_SKILL_MD,
            extra_py={"skills/my-skill/runner.py": py_content},
        )
        passed, detail = check_no_shell_true(root)
        assert passed is False
        assert "shell=True" in detail

    def test_pass_no_skills_dir(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_no_shell_true(root)
        assert passed is True
        assert "skills/" in detail or "no skills" in detail.lower()

    def test_pass_shell_true_with_lowercase_trust_comment(self, tmp_path: Path) -> None:
        py_content = """\
import subprocess
# trust: validated by caller
result = subprocess.run(cmd, shell=True)
"""
        root = _make_plugin(
            tmp_path,
            skill_md_content=_GOOD_SKILL_MD,
            extra_py={"skills/my-skill/runner.py": py_content},
        )
        passed, _ = check_no_shell_true(root)
        assert passed is True


# ---------------------------------------------------------------------------
# check_has_bench_tasks
# ---------------------------------------------------------------------------

class TestCheckHasBenchTasks:
    def test_pass_has_task_files(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, bench_task_files=["task1.md", "task2.md"])
        passed, detail = check_has_bench_tasks(root)
        assert passed is True
        assert "2" in detail

    def test_fail_no_bench_dir(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_has_bench_tasks(root)
        assert passed is False
        assert "bench/tasks" in detail

    def test_fail_tasks_dir_empty(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        tasks_dir = root / "bench" / "tasks"
        tasks_dir.mkdir(parents=True)
        passed, detail = check_has_bench_tasks(root)
        assert passed is False
        assert "no .md" in detail.lower() or "contains no" in detail.lower()

    def test_fail_non_md_files_ignored(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        tasks_dir = root / "bench" / "tasks"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "task.txt").write_text("not a task", encoding="utf-8")
        passed, detail = check_has_bench_tasks(root)
        assert passed is False


# ---------------------------------------------------------------------------
# check_has_examples
# ---------------------------------------------------------------------------

class TestCheckHasExamples:
    def test_pass_has_code_block(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path, skill_md_content=_GOOD_SKILL_MD)
        passed, detail = check_has_examples(root)
        assert passed is True

    def test_pass_has_examples_section(self, tmp_path: Path) -> None:
        content = """\
---
description: Does something.
---

## Usage

Run it.

## Examples

Some example.

## Known Failure Modes

- none
"""
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_has_examples(root)
        assert passed is True

    def test_fail_no_examples(self, tmp_path: Path) -> None:
        content = """\
---
description: Does something.
---

## Usage

Plain text only, no code blocks.

## Known Failure Modes

- none
"""
        root = _make_plugin(tmp_path, skill_md_content=content)
        passed, detail = check_has_examples(root)
        assert passed is False
        assert "no examples" in detail.lower()

    def test_fail_no_skill_md(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_has_examples(root)
        assert passed is False
        assert "SKILL.md" in detail


# ---------------------------------------------------------------------------
# check_semver
# ---------------------------------------------------------------------------

class TestCheckSemver:
    def test_pass_valid_semver(self, tmp_path: Path) -> None:
        pj = {"name": "my-skill", "version": "1.2.3", "description": "x", "author": "vi"}
        root = _make_plugin(tmp_path, plugin_json=pj)
        passed, detail = check_semver(root)
        assert passed is True
        assert "1.2.3" in detail

    def test_fail_missing_version(self, tmp_path: Path) -> None:
        pj = {"name": "my-skill", "description": "x", "author": "vi"}
        root = _make_plugin(tmp_path, plugin_json=pj)
        passed, detail = check_semver(root)
        assert passed is False
        assert "version" in detail

    def test_fail_invalid_version_format(self, tmp_path: Path) -> None:
        pj = {"name": "my-skill", "version": "1.2", "description": "x", "author": "vi"}
        root = _make_plugin(tmp_path, plugin_json=pj)
        passed, detail = check_semver(root)
        assert passed is False
        assert "1.2" in detail

    def test_fail_no_plugin_json(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_semver(root)
        assert passed is False
        assert "plugin.json" in detail

    def test_pass_semver_with_prerelease(self, tmp_path: Path) -> None:
        pj = {"name": "my-skill", "version": "2.0.0-beta.1", "description": "x", "author": "vi"}
        root = _make_plugin(tmp_path, plugin_json=pj)
        passed, detail = check_semver(root)
        assert passed is True

    def test_fail_invalid_json(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        meta_dir = root / ".claude-plugin"
        meta_dir.mkdir()
        (meta_dir / "plugin.json").write_text("{bad json", encoding="utf-8")
        passed, detail = check_semver(root)
        assert passed is False
        assert "JSON" in detail


# ---------------------------------------------------------------------------
# check_metadata_complete
# ---------------------------------------------------------------------------

class TestCheckMetadataComplete:
    def test_pass_all_fields_present(self, tmp_path: Path) -> None:
        pj = {"name": "my-skill", "version": "1.0.0", "description": "Does things", "author": "vi"}
        root = _make_plugin(tmp_path, plugin_json=pj)
        passed, detail = check_metadata_complete(root)
        assert passed is True
        assert "all required" in detail.lower()

    def test_fail_missing_author(self, tmp_path: Path) -> None:
        pj = {"name": "my-skill", "version": "1.0.0", "description": "Does things"}
        root = _make_plugin(tmp_path, plugin_json=pj)
        passed, detail = check_metadata_complete(root)
        assert passed is False
        assert "author" in detail

    def test_fail_missing_name_and_description(self, tmp_path: Path) -> None:
        pj = {"version": "1.0.0", "author": "vi"}
        root = _make_plugin(tmp_path, plugin_json=pj)
        passed, detail = check_metadata_complete(root)
        assert passed is False
        assert "name" in detail or "description" in detail

    def test_fail_no_plugin_json(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        passed, detail = check_metadata_complete(root)
        assert passed is False
        assert "plugin.json" in detail

    def test_fail_empty_field_counts_as_missing(self, tmp_path: Path) -> None:
        pj = {"name": "", "version": "1.0.0", "description": "Does things", "author": "vi"}
        root = _make_plugin(tmp_path, plugin_json=pj)
        passed, detail = check_metadata_complete(root)
        assert passed is False
        assert "name" in detail

    def test_fail_invalid_json(self, tmp_path: Path) -> None:
        root = _make_plugin(tmp_path)
        meta_dir = root / ".claude-plugin"
        meta_dir.mkdir()
        (meta_dir / "plugin.json").write_text("not json at all", encoding="utf-8")
        passed, detail = check_metadata_complete(root)
        assert passed is False
        assert "JSON" in detail
