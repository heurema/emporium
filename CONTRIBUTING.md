# Adding a Plugin to the Marketplace

## For External Repos (separate GitHub repository)

1. Add an entry to `.claude-plugin/marketplace.json` in the `plugins` array:

```json
{
  "name": "your-plugin",
  "description": "One-paragraph description of what the plugin does",
  "category": "development",
  "source": {
    "source": "url",
    "url": "https://github.com/Real-AI-Engineering/your-plugin.git"
  },
  "homepage": "https://github.com/Real-AI-Engineering/your-plugin"
}
```

2. Add a row to the Catalog table in `README.md`.

3. Commit and push.

### Required fields

| Field | Description |
|-------|-------------|
| `name` | Plugin name (lowercase, hyphens). Must match the `name` in the plugin's own `plugin.json` |
| `description` | 1-2 sentences. Descriptive, not promotional |
| `category` | `development`, `productivity`, or `documentation` |
| `source.source` | Always `"url"` for external repos |
| `source.url` | Full `.git` URL of the plugin repo |
| `homepage` | GitHub repo URL (without `.git`) |

### Category guide

- **development** — code review, pipelines, testing, implementation tools
- **productivity** — news, automation, scheduling, workflow tools
- **documentation** — guides, references, field guides

## For Inline Plugins (simple, lives in this repo)

For small plugins that don't warrant their own repo:

1. Create a directory under `plugins/`:

```
plugins/your-plugin/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── your-skill/
│       └── SKILL.md
└── (commands/, agents/, hooks/ as needed)
```

2. Add to `.claude-plugin/marketplace.json`:

```json
{
  "name": "your-plugin",
  "description": "...",
  "category": "development",
  "source": "./plugins/your-plugin"
}
```

3. Add a row to the Catalog table in `README.md`.

4. Commit and push.

## Validation

After adding, verify locally:

```bash
claude --plugin-dir ./plugins/your-plugin   # for inline plugins
# or
claude plugin marketplace add /path/to/this/marketplace  # test full marketplace
```

## Naming Conventions

- Plugin names: lowercase, hyphens (`my-tool`, not `myTool` or `my_tool`)
- Descriptions: start with verb or noun, no trailing period
- No emojis in descriptions
