# Check Architecture

Audit a file or module for compliance with repo patterns and hard rules.

## Usage

```
/check-architecture modules/operations/services.py
/check-architecture modules/logistics/
/check-architecture --all
```

## What It Checks

**Hard Rules** (blocks):
- ❌ Direct MongoDB access in UI code
- ❌ Hardcoded `SARAPP_MONGO_URI`
- ❌ Missing repository pattern for DB writes
- ❌ Invalid directory structure

**Architecture Patterns** (guidance):
- ⚠️ Naming conventions (snake_case, descriptive)
- ⚠️ Module structure (services, repos, UI separation)
- ⚠️ Type hints coverage
- ⚠️ Docstring presence
- ⚠️ Logging setup
- ⚠️ Test file existence

**UI Standards** (warnings):
- ⚠️ Hardcoded colors (use shared palette)
- ⚠️ Inline stylesheets (use `utils.styles`)
- ⚠️ Table design compliance
- ⚠️ Dialog patterns

## Output

```
✅ Hard Rules: PASS
⚠️  Architecture: 3 guidance items
  - Missing docstring on get_incidents()
  - Type hints needed: create_task() parameter
  - Consider extracting query logic to repository

📋 Summary: File follows core patterns, minor improvements suggested
```

## Options

- `--strict` — Fail on warnings (not just errors)
- `--fix` — Auto-fix simple issues (naming, imports)
- `--all` — Scan entire repo

## Common Issues Found

| Issue | How to Fix |
|-------|-----------|
| Direct `.find()` in UI | Move to repository, call via API |
| Missing type hints | Add `: Type` to function params |
| Hardcoded color | Use `get_palette()` from `utils.styles` |
| No docstring | Add `"""Purpose"""` to functions |

## Next Steps

- Review guidance items (not blocking, but improve code quality)
- Fix hard rule violations before commit
- Run `/run-tests` after refactoring

## Related

- `/validate-repo` — Hard validation (blocks on errors)
- `/repo-rules` — Quick reference of rules
