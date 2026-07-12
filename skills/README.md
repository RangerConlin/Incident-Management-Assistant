# Skills

Universal project knowledge and tasks. Discoverable by all tools and agents (Claude Code, Codex, etc.).

## All Skills

### Setup & Environment
- **`setup-dev`** — Initialize dev environment (Python, MongoDB, env vars)
- **`quick-start`** — Launch the desktop app for manual testing

### Development Workflows
- **`new-module`** — Scaffold new functional module with correct structure
- **`new-router`** — Create API router under `data/db/sarapp_db/api/routers/`
- **`new-repository`** — Create BaseRepository subclass for MongoDB data access
- **`new-ui-panel`** — Scaffold UI panel/widget following design standards

### Quality & Verification
- **`run-tests`** — Execute pytest with QT_QPA_PLATFORM setup
- **`validate-repo`** — Run all validation checks (hardcoded URIs, DB access, structure)
- **`check-architecture`** — Audit file/module for pattern compliance (guidance + hard rules)

### Reference & Documentation
- **`repo-rules`** — Quick reference of hard rules and patterns
- **`design-docs`** — Index of all Design Documents with search
- **`schema-lookup`** — MongoDB schema reference (collections, fields, indexes)
- **`api-endpoints`** — List all API endpoints with examples
- **`migration-checklist`** — Step-by-step guide for SQLite → MongoDB migrations

## How to Use

Each skill is a self-contained markdown file with:
- **Usage** — How to invoke it and available options
- **What It Does** — What action/output to expect
- **Next Steps** — Recommended follow-up actions
- **Troubleshooting** — Common issues and solutions

## Examples

```
/setup-dev --skip-mongodb
/new-module logistics --with-ui --with-api
/run-tests --coverage
/check-architecture modules/operations/
/schema-lookup incidents --fields
/migration-checklist --module=teams
```

## Adding New Skills

To create a new skill:
1. Create `skillname.md` in this directory
2. Follow the format of existing skills (usage, what it does, output, next steps)
3. Keep descriptions practical and actionable
4. Link to related skills at the bottom

## Integration

Skills are:
- **Claude Code** — Invoked with `/skillname`
- **Codex** — Can reference these docs for guidance
- **CI/CD** — Can call underlying scripts/tools referenced in skills
- **Any tool** — Just reference the markdown as documentation

Skills work alongside:
- `scripts/` — Validation scripts (called by skills and hooks)
- `Design Documents/Instructions/` — Detailed guidance
- `agents.md` — Hard rules and architecture decisions
