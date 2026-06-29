# Legacy Code Inventory

This file is the authoritative inventory for legacy compatibility code that remains in the repo only to bridge gaps between current application behavior and older persisted data shapes, migration states, or outdated database entries.

Use this file to track code that is intentionally retained for compatibility and may become removable during pre-release cleanup after verification.

## What Belongs Here
- Code paths kept only to read, translate, ignore, or tolerate outdated database entries or pre-cutover persisted state.
- Temporary compatibility shims between legacy repositories/data models and the current API/repository architecture.
- Legacy fallbacks that should be reviewed before release because they are not part of the intended steady-state product.

## What Does Not Belong Here
- Active migration status snapshots that belong in `Design Documents/Instructions/mongo_cutover_status.md`.
- General future work or product ideas that belong in `backlog.md`.
- Permanent architectural adapters that are expected to remain after release.

## Inventory Rules
- Add an entry when code is intentionally preserved for legacy compatibility instead of current product behavior.
- Keep entries specific and evidence-based; do not mark code as removable unless the removal condition is clear.
- Update or remove an entry when the compatibility path is verified unnecessary or is deleted.
- Treat this file as the pre-release review list for legacy compatibility cleanup.

## Entry Template

Copy this section for each tracked item.

```md
### Short Name
- Status: `legacy-compat-active` | `legacy-compat-candidate`
- Location: `path/to/file.py`
- Purpose: brief description of the compatibility behavior
- Legacy Source: what old data shape, persisted field, SQLite-era behavior, or migration gap this supports
- Removal Condition: exact condition that must be true before deletion is safe
- Verification: how to confirm the removal condition
- Notes: optional extra context, linked issue, or dates
```

## Inventory

Add entries below this line.
