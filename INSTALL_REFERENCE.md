# Install Reference

Canonical install instructions for all heurema plugins distributed via the emporium marketplace.

Plugin READMEs should include the snippet below between `<!-- INSTALL:START -->` and `<!-- INSTALL:END -->` markers for automated sync checking.

## Marketplace Setup (once)

```bash
claude plugin marketplace add heurema/emporium
```

## Per-Plugin Install

| Plugin | Command |
|--------|---------|
| sigil | `claude plugin install sigil@emporium` |
| herald | `claude plugin install herald@emporium` |
| arbiter | `claude plugin install arbiter@emporium` |
| anvil | `claude plugin install anvil@emporium` |
| reporter | `claude plugin install reporter@emporium` |
| teams-field-guide | `claude plugin install teams-field-guide@emporium` |

## Expected README Snippet

Each plugin README should contain:

```markdown
<!-- INSTALL:START -- auto-synced from emporium/INSTALL_REFERENCE.md -->
` ` `bash
claude plugin marketplace add heurema/emporium
claude plugin install <name>@emporium
` ` `
<!-- INSTALL:END -->
```

Replace `<name>` with the plugin's `name` field from `plugin.json`.

## Validation

- **anvil**: `validate_install_docs.py` checks README install blocks against `plugin.json`
- **emporium**: `check_consistency.py` verifies markers and correct commands across all plugins
