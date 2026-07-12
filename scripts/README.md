# Validation Scripts

Universal validation scripts for the Incident Management Assistant repo. Used by:
- Claude Code hooks (`.claude/settings.json`)
- Git pre-commit hooks
- CI/CD pipelines
- Direct invocation by any developer or tool

## Quick Start

Run all validators:
```bash
bash scripts/validate-all.sh
```

Run individual validators:
```bash
bash scripts/validate-hardcoded-uri.sh
bash scripts/validate-direct-db-access.sh
bash scripts/validate-structure.sh
bash scripts/validate-ui-styles.sh
```

## What Each Script Checks

| Script | Checks | Fails on |
|--------|--------|----------|
| `validate-hardcoded-uri.sh` | Hardcoded `SARAPP_MONGO_URI`, API keys, database URLs | Found hardcoded secrets |
| `validate-direct-db-access.sh` | Direct MongoDB calls in UI code | Direct DB access outside `data/db/` |
| `validate-structure.sh` | New QML files, `backend/` directory | Structural violations |
| `validate-ui-styles.sh` | Hardcoded colors, inline stylesheets in UI | (Warning only) |
| `validate-all.sh` | Runs all validators, provides summary | Any hard failure |

## Exit Codes

- `0` — All checks passed (or warnings only)
- `1` — Hard failures found
- `2` — Warnings (non-blocking)

## Setting Up Git Hooks

To auto-validate before commits:

```bash
#!/bin/bash
# .git/hooks/pre-commit (make executable: chmod +x .git/hooks/pre-commit)
bash scripts/validate-all.sh
```

## Requirements

- Bash 4.0+
- Git
- Standard tools: `grep`, `sed`, `awk`

## Architecture

These scripts validate against rules in:
- `agents.md` — Hard rules, directory structure, architecture patterns
- `Design Documents/Instructions/` — Detailed guidance documents

Violations block commits to enforce standards across all tools and developers.
