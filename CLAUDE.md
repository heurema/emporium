# Emporium — AI Agent Instructions

Plugin marketplace and quality infrastructure for the heurema Claude Code plugin ecosystem.

## Project Structure

```
lib/rubric/__init__.py    Pure check functions (12 checks, no IO in core)
lib/trace/__init__.py     Archive + PII redaction for Signum artifacts
scripts/                  CLI wrappers (all exit 0=PASS, 1=FAIL)
tests/                    pytest suite (8 tests)
.claude-plugin/           Marketplace manifest (marketplace.json)
```

## Key Patterns

- Every check function signature: `(plugin_root: Path) -> tuple[bool, str]`
- `passed=True` means check passed, `detail` is human-readable explanation
- Fail-closed: on any read error, return `(False, "error description")` — never silently PASS
- Vacuous truth guard: `len(items) > 0 and all(...)` — empty list is FAIL, not PASS
- Plugin name regex: `^[a-z0-9]+(-[a-z0-9]+)*$` — lowercase alphanum with optional hyphens
- Two-file CLI pattern: `ingestion_gate.py` (importable, underscore) + `ingestion-gate.py` (CLI, hyphen)
- All scripts share: `--plugin-root DIR` (default ~/personal/skill7/devtools/), `--output FILE`

## Import Paths

From emporium root:
```python
import sys; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.rubric import check_hardcoded_secrets, check_line_count
from lib.trace import redact_text, archive_signum_run
```

Scripts resolve `lib/` relative to themselves via `_REPO_ROOT = _SCRIPT_DIR.parent`.

## Safety Checks (Ingestion Gate)

6 checks run in order on every plugin submission:

| Check | What it catches |
|-------|----------------|
| hardcoded_secrets | Embedded API keys, passwords, credentials |
| dangerous_commands | rm -rf, eval, exec, dangerous shell calls |
| suspicious_urls | Non-HTTPS URLs, known malicious domains |
| shell_true | subprocess.run(shell=True) patterns |
| line_count | Any file > 300 lines |
| required_sections | SKILL.md missing description/usage/failure modes |

## Trace Module

- `redact_text()` uses `_SECRET_PATTERNS` from lib/rubric (includes email + IP regex)
- `archive_signum_run()` validates run_id format: `^signum-\d{4}-\d{2}-\d{2}-[a-z0-9]+$`
- Text files (.json, .md, .jsonl, .log, .txt) get redacted; .patch copied as binary
- Archived files set to 0o600 (owner-only)
- `prune_old_runs()` deletes by mtime, requires max_age_days >= 0

## Running Tests

```bash
python3 -m pytest tests/ -v
```

## Adding New Checks

1. Add the check function to `lib/rubric/__init__.py`
2. Add it to `_SAFETY_CHECKS` list in `scripts/ingestion_gate.py` if it's a gate check
3. Add it to the rubric imports in `scripts/quality-rubric.py` if it's a quality check
4. Write tests
5. Keep check functions pure — accept Path, return (bool, str)

## Conventions

- Language: Python 3.10+
- No external dependencies (stdlib only)
- All scripts executable via `python3 scripts/<name>.py`
- JSON output with `indent=2` for reports
- Default plugin root: `~/personal/skill7/devtools/`
- Default archive root: `~/.local/share/emporium/traces/`
