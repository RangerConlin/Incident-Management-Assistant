# Migration Agent Instructions

This folder is the coordination hub for the repository reorganization.

## Current Status

As of 2026-10-12, `repo_file_inventory.md` has no remaining active rows. The
web app, mobile snapshot, services, server package, archived design docs, tools,
and desktop source tree have been moved into the approved layout.

Do not start additional migration moves from memory or old chat context. If more
work is needed, first generate or write a new explicit inventory row/scope and
confirm the intended ownership/location. A few root files intentionally remain
at repository root as staged launch/test/config entrypoints:

- `main.py`
- `sarapp_server.py`
- `conftest.py`
- `pyproject.toml`
- `pytest.ini`
- `requirements.txt`
- `settings.json`
- `Start SARApp Desktop.bat`
- `.claude/settings.json`
- `.vscode/settings.json`
- `settings/`

Those paths are currently kept for runtime compatibility, cwd-relative config
lookups, and existing launch/test tooling.

Before changing files, read:

1. `docs/architecture/repo_layout.md`
2. `docs/architecture/repo_file_inventory.md`

## Goal

Move the project toward the approved repo layout while keeping the application
working during migration. Work in small, reviewable batches. Prefer one
runtime, package, folder, or tightly related file group at a time.

## Source Of Truth

Use `repo_file_inventory.md` as the active migration queue.

Each row represents remaining work. When a file has been moved, kept, archived,
excluded, or deleted and no more action is needed, delete that row from the
inventory. The file should disappear from the tracker only after the associated
code/import/test/build changes are complete.

## Claiming Work

Markdown has no locking, so claim rows before editing code.

For each row or group you are taking, set:

```text
Actual status: In progress - <agent/task name>
Decision notes: Claimed YYYY-MM-DD for <short scope>.
```

Do not work on rows already marked `In progress`, `Blocked`, or otherwise
claimed unless the user explicitly asks you to take them over.

## Status Values

Use these values in `Actual status` while work is active:

- `Not started`
- `In progress - <agent/task name>`
- `Needs review`
- `Blocked`

Completed rows should normally be deleted from the inventory instead of being
left with a final status.

## Disposition Guidance

- `Move`: Move to the suggested target if investigation confirms it.
- `Move/review`: Inspect first, then move if the target still makes sense.
- `Keep`: Leave in place if it already belongs in the target structure.
- `Keep/review`: Confirm whether the current location is still right.
- `Move/archive`: Move under a documentation/archive location if still useful.
- `Review/archive`: Decide whether to preserve, archive, or remove.
- `Exclude from migration`: Usually generated/local content such as caches,
  build output, virtualenvs, compiled files, IDE metadata, or local tool
  artifacts. Do not migrate these into the new structure.

Do not delete source code only because a row says `Exclude from migration`.
Confirm that the file is truly generated/local or otherwise disposable.

## Dependency Rules

Follow the dependency direction from `repo_layout.md`:

```text
apps/*       -> shared/* -> HTTP API -> server/*
services/*   -> server/* + shared/*
server/*     -> shared/*
shared/*     -> imports nothing project-specific
```

Client apps should not import server implementation directly. Prefer generated
or thin clients from `shared` and API boundaries.

## Migration Workflow

1. Pick a bounded scope from `repo_file_inventory.md`.
2. Claim those rows.
3. Inspect the current code and imports before moving files.
4. Move files according to the approved layout, adjusting target paths when
   investigation shows the suggested location is wrong.
5. Update imports, scripts, tests, packaging paths, and documentation references
   affected by the move.
6. Run focused verification for the changed scope.
7. If the move is complete, delete completed rows from `repo_file_inventory.md`.
8. If blocked, keep the row and set `Actual status` to `Blocked` with a concise
   reason in `Decision notes`.

## Verification Expectations

Use focused checks rather than broad, slow test runs by default.

Examples:

- For Python package moves, run targeted import smoke tests or focused pytest
  files.
- For service moves, run the service's unit tests and import/startup checks.
- For web moves, run package install/build/test commands if dependencies are
  available.
- For mobile moves, run Flutter analysis/tests when practical.
- For documentation-only changes, no runtime tests are required.

If verification cannot be run, record that in the final response and, when
useful, in `Decision notes`.

## Cleanup Rules

Generated/local files should generally be excluded from migration, not moved.
Examples include:

- `__pycache__/`
- `*.pyc`
- `.venv/`
- `.pytest_cache/`
- `.dart_tool/`
- `build/`
- `dist/`
- `node_modules/`
- `tmp/`
- `logs/`
- IDE-local metadata
- local signing or machine-specific configuration

Before deleting anything tracked by Git, confirm it is obsolete and within the
scope of the current migration task.

## Safety Rules

- Do not use destructive Git commands.
- Do not revert unrelated user changes.
- Do not maintain duplicate live implementations in both old and new locations.
- Prefer compatibility shims only as temporary migration aids.
- Keep changes small enough for another agent or human to review.
- When unsure, mark the row `Needs review` instead of guessing.
