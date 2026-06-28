# Agent Setup — Hooks & Validation

This document explains the automated hooks and skills set up for agents working on this repo.

## Automated Hooks

Hooks run automatically during development to catch violations early and save tokens.

### PostToolUse Hooks (After File Edit/Write)

When you create or modify a file, hooks automatically validate:

1. **Hardcoded URIs** — Detects `SARAPP_MONGO_URI`, MongoDB URIs, API keys
   - Script: `scripts/validate-hardcoded-uri.sh`
   - Failure blocks the edit (agent must fix immediately)

2. **Direct DB Access** — Catches `insert_one`, `find`, etc. in UI code
   - Script: `scripts/validate-direct-db-access.sh`
   - Failure blocks the edit (agent must refactor to use API)

3. **UI Styling** — Warns about hardcoded colors and inline stylesheets
   - Script: `scripts/validate-ui-styles.sh`
   - Warning only (guides toward shared palette use)

### PreToolUse Hooks (Before Git Commits)

When a `git commit` is issued, hooks validate staged files:

1. **Structural Rules** — Blocks QML files, `backend/` directories
   - Script: `scripts/validate-structure.sh`
   - Hard failure (prevents bad commits)

2. **Cloud Server Mirrors** — Warns if `data/db/` routers lack `cloud_server/` mirrors
   - Script: `scripts/validate-cloud-server-mirror.sh`
   - Warning only (reminds agent to mirror changes)

## Skills for Agents

Skills are manually-invoked commands agents can call to validate work.

### `/repo-rules` — Quick Reference

Displays hard rules, mirroring requirements, architecture constraints, and testing setup.

**Use when**: You need to check a rule or are unsure about a pattern.

```
/repo-rules
```

### `/validate-repo` — Full Validation Check

Runs all validators and reports a summary.

**Use when**: About to commit, or you want a comprehensive status check.

```
/validate-repo
/validate-repo --check=uri      # Only hardcoded URIs
/validate-repo --check=db       # Only direct DB access
/validate-repo --check=structure # Only structural rules
/validate-repo --check=mirrors  # Only cloud_server mirrors
/validate-repo --check=styles   # Only UI styling
```

Exit codes:
- `0` = All passed
- `1` = Hard failures (fix before committing)
- `2` = Warnings (good to fix, not blocking)

## How Hooks Save Tokens

1. **Immediate Feedback** — Agent gets error instantly, not after a failed test
2. **Self-Correction** — Agent fixes immediately without asking for clarification
3. **Validation at Edit Time** — Catches issues before they compound
4. **Staged Validation** — Pre-commit hooks prevent bad commits from landing

Example: Instead of:
1. Agent edits file (10 tokens)
2. Test fails (5 tokens to read error)
3. Agent asks what's wrong (2 tokens)
4. You explain the rule (10 tokens)
5. Agent fixes (10 tokens)

Hooks provide:
1. Agent edits file
2. Hook displays error (0 tokens — automatic)
3. Agent fixes (10 tokens)

**Savings: ~27 tokens per violation.**

## Configuration Files

| File | Purpose |
|------|---------|
| `.claude/settings.json` | Claude Code hook and permission configuration |
| `scripts/validate-*.sh` | Universal validation scripts (used by hooks, CI/CD, git hooks) |
| `scripts/validate-all.sh` | Master validator (can be called directly or by any tool) |
| `.claude/skills/repo-rules.md` | Claude Code quick reference skill |
| `.claude/skills/validate-repo.md` | Claude Code validator skill documentation |
| `.claude/AGENT_SETUP.md` | This file (setup docs for agents) |

## For Codex & Other Agents

Agents using this repo should:

1. **Before starting** — Run `/repo-rules` to understand constraints
2. **During development** — Check hook output for violations
3. **Before committing** — Run `/validate-repo` for final check
4. **When unsure** — Call `/repo-rules --topic=architecture` (or similar)

The hooks provide guardrails without requiring agent intervention. The skills provide self-serve reference and validation.

## Troubleshooting Hooks

**Hook didn't run?**
- Ensure `.claude/settings.json` exists in project root
- Check hook script paths (must be relative to project root)
- Run `bash .claude/validate-all.sh` manually to test

**False positive?**
- Edit the relevant script in `.claude/validate-*.sh`
- Add exception logic (skip files in comments, etc.)
- Re-test with `bash .claude/validate-all.sh`

**Need to bypass?**
- Use `git commit --no-verify` (NOT recommended)
- Better: Fix the violation or adjust the hook

## Adding New Validators

To add a new validator:

1. Create `.claude/validate-newrule.sh` with your checks
2. Add to `.claude/validate-all.sh` with `run_validator "Name" "script.sh"`
3. Add PostToolUse or PreToolUse hook in `.claude/settings.json`
4. Document in `/repo-rules` skill

Example hook:
```json
{
  "type": "command",
  "command": "bash .claude/validate-newrule.sh",
  "statusMessage": "Checking new rule..."
}
```
