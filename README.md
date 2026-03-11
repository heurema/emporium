# Emporium

Claude Code plugin marketplace for all [heurema](https://github.com/heurema) open-source AI agent tools. Craft, not conjuring.

## Install

<!-- INSTALL:START — auto-synced from emporium/INSTALL_REFERENCE.md -->
```bash
claude plugin marketplace add heurema/emporium
```
<!-- INSTALL:END -->

Then install any plugin:

```bash
claude plugin install signum@emporium
claude plugin install herald@emporium
claude plugin install arbiter@emporium
claude plugin install anvil@emporium
claude plugin install reporter@emporium
claude plugin install genesis@emporium
claude plugin install sentinel@emporium
claude plugin install teams-field-guide@emporium
```

## Catalog

| Plugin | Description | Repo |
|--------|-------------|------|
| **signum** | Risk-adaptive development pipeline with adversarial consensus code review | [signum](https://github.com/heurema/signum) |
| **herald** | Daily curated news digest — zero API keys, fully local | [herald](https://github.com/heurema/herald) |
| **arbiter** | Multi-AI orchestrator — Codex CLI + Gemini CLI for review, ask, implement, panel | [arbiter](https://github.com/heurema/arbiter) |
| **anvil** | Plugin dev/test toolkit — scaffold, validate, test, review | [anvil](https://github.com/heurema/anvil) |
| **reporter** | Report bugs, request features, and ask questions for any heurema product | [reporter](https://github.com/heurema/reporter) |
| **sentinel** | AI workstation security audit — secrets, MCP, plugins, hooks, trust | [sentinel](https://github.com/heurema/sentinel) |
| **genesis** | Evolve startup ideas through AI-powered natural selection with 3 agent personas | [genesis](https://github.com/heurema/genesis) |
| **teams-field-guide** | Comprehensive guide to Claude Code multi-agent systems | [teams-field-guide](https://github.com/heurema/teams-field-guide) |

## Quality Infrastructure

Emporium includes tooling to enforce plugin quality before acceptance into the marketplace.

### Architecture

```
lib/rubric/     12 pure check functions (no IO in core logic)
lib/trace/      Signum artifact archival with PII/secret redaction
scripts/        CLI tools for running checks
tests/          pytest test suite
```

### CLI Tools

All scripts follow a common pattern: `--plugin-root DIR` (default: `~/personal/skill7/devtools/`), `--output FILE` (JSON report), exit 0 = PASS, exit 1 = FAIL.

#### Ingestion Gate — 6 safety checks

```bash
python3 scripts/ingestion-gate.py --plugin herald
python3 scripts/ingestion-gate.py --plugin signum --output /tmp/report.json
python3 scripts/ingestion-gate.py --plugin arbiter --plugin-root /path/to/plugins
```

Checks: `hardcoded_secrets`, `dangerous_commands`, `suspicious_urls`, `shell_true`, `line_count` (300 max), `required_sections`.

#### Quality Rubric — 12-point scoring

```bash
python3 scripts/quality-rubric.py --plugin=herald
python3 scripts/quality-rubric.py --plugin=arbiter --output=/tmp/arbiter.json
```

4 structural + 4 safety + 4 quality checks. Score 0-12, gate PASS at >= 9.

#### Line Cap Enforcer — batch 300-line scanner

```bash
python3 scripts/enforce-line-cap.py
python3 scripts/enforce-line-cap.py --plugin-root /path/to/plugins --output /tmp/linecap.json
```

Scans all plugins, reports files exceeding 300 lines.

#### Failure Modes Checker — required SKILL.md sections

```bash
python3 scripts/check-failure-modes.py
python3 scripts/check-failure-modes.py --plugin-root /path/to/plugins
```

Verifies every plugin SKILL.md has description, usage, and known failure modes sections.

#### Trace Archive — Signum artifact archival

```bash
python3 scripts/trace-archive.py --archive
python3 scripts/trace-archive.py --prune --max-age 30
python3 scripts/trace-archive.py --archive --prune
```

Archives `.signum/` run artifacts with automatic redaction of secrets, API keys, emails, and IP addresses. Prunes old archives by age.

### Library API

#### lib/rubric — Check Functions

```python
from lib.rubric import (
    # Structural
    check_skill_md,           # SKILL.md exists and non-empty
    check_required_sections,  # description + usage + failure modes
    check_line_count,         # no file > 300 lines
    check_skill_id_format,    # valid skill_id pattern

    # Safety
    check_hardcoded_secrets,  # no embedded credentials
    check_no_dangerous_commands,  # no rm -rf, eval, etc.
    check_no_suspicious_urls,     # no non-HTTPS URLs
    check_no_shell_true,          # no shell=True in subprocess

    # Quality
    check_has_bench_tasks,    # bench/ tasks exist
    check_has_examples,       # usage examples present
    check_semver,             # valid semver version
    check_metadata_complete,  # author, description, category
)

# Every function: (Path) -> (bool, str)
passed, detail = check_hardcoded_secrets(Path("/path/to/plugin"))
```

#### lib/trace — Archive & Redaction

```python
from lib.trace import redact_text, archive_signum_run, prune_old_runs

# Redact secrets/PII from text
clean = redact_text("key=sk-1234567890abcdef, email: user@example.com")

# Archive .signum/ with redaction (returns Path to archived run)
archive_path = archive_signum_run(".signum", "~/.local/share/emporium/traces")

# Delete runs older than 90 days
deleted = prune_old_runs("~/.local/share/emporium/traces", max_age_days=90)
```

### Tests

```bash
cd ~/personal/heurema/emporium
python3 -m pytest tests/ -v
```

8 tests covering archive, redaction, pruning, file integrity, and error handling.

## Adding a New Plugin

See [CONTRIBUTING.md](CONTRIBUTING.md).

## See Also

- **[signum](https://github.com/heurema/signum)** — risk-adaptive development pipeline with adversarial code review
- **[herald](https://github.com/heurema/herald)** — daily curated news digest plugin for Claude Code
- **[arbiter](https://github.com/heurema/arbiter)** — multi-AI orchestrator (Codex + Gemini)
- **[anvil](https://github.com/heurema/anvil)** — plugin dev/test toolkit
- **[reporter](https://github.com/heurema/reporter)** — issue reporter for heurema products
- **[genesis](https://github.com/heurema/genesis)** — evolve startup ideas with memetic algorithm and 3 AI agent personas
- **[sentinel](https://github.com/heurema/sentinel)** — AI workstation security audit
- **[teams-field-guide](https://github.com/heurema/teams-field-guide)** — comprehensive guide to Claude Code multi-agent teams
- **[proofpack](https://github.com/heurema/proofpack)** — proof-carrying CI gate for AI agent changes

## License

MIT
