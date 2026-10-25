# Legacy Code Inventory

This file is the authoritative inventory for **unverified** legacy-compatibility
candidates — code suspected of being dead, superseded, or no-longer-needed, but
not yet confirmed either way. It is a to-do list for investigation, not a
permanent record.

See `docs/archive/design-documents/activeshims.md` for the companion list: shims
**confirmed** to still have live callers, kept intentionally until those callers
migrate off them. An entry only belongs in one of these two files at a time:

- Investigate an entry here and find it has **zero remaining callers** -> delete
  the code, then remove the entry outright (git history records what was removed).
- Investigate an entry here and find it **still has live callers** -> move the
  entry to `activeshims.md` instead of leaving it here; a candidate list should
  only ever contain things still waiting on investigation.

## What Belongs Here
- Code paths suspected of being kept only to read, translate, ignore, or tolerate
  outdated database entries or pre-cutover persisted state, not yet confirmed to
  still be reachable.
- Temporary compatibility shims between legacy repositories/data models and the
  current API/repository architecture, not yet confirmed to still have callers.
- Legacy fallbacks that should be reviewed before release because they are not
  part of the intended steady-state product.

## What Does Not Belong Here
- Confirmed-live shims — those go in `activeshims.md`.
- Active migration status snapshots that belong in `docs/archive/design-documents/Instructions/mongo_cutover_status.md`.
- General future work or product ideas that belong in `backlog.md`.
- Permanent architectural adapters that are expected to remain after release.

## Inventory Rules
- Add an entry when code is suspected of being legacy/dead but hasn't been
  verified yet.
- Keep entries specific and evidence-based; do not mark code as removable unless
  the removal condition is clear.
- Once investigated: delete-and-remove the entry (if dead) or move it to
  `activeshims.md` (if still live). Either way, remove it from this file — do not
  leave a struck-through "DELETED"/"REMOVED" stub; git history is the record of
  what was removed and when.
- Treat this file as the pre-release review list for legacy compatibility cleanup.

## Entry Template

Copy this section for each tracked item.

```md
### Short Name
- Location: `path/to/file.py`
- Purpose: brief description of the compatibility behavior
- Legacy Source: what old data shape, persisted field, SQLite-era behavior, or migration gap this supports
- Removal Condition: exact condition that must be true before deletion is safe
- Verification: how to confirm the removal condition (and whether it's been run yet)
```

## Inventory

Add entries below this line.

### Hardcoded certification catalog (cert_catalog.py)
- Location: `modules/personnel/models/cert_catalog.py` (`CATALOG`, `CertType`, `CATALOG_VERSION`)
- Purpose: was "authoritative in production" per its own former docstring — every certification type (id, code, name, category, tags, is_medical) was a hardcoded Python list, editable only via a DEV_MODE-only tool that rewrote this file's source and required a rebuild/redeploy to ship. Replaced 2026-10-10 by a real Mongo-backed catalog (`MasterCollections.CERTIFICATION_TYPES`, `server/sarapp_db/sarapp_db/api/routers/certification_types.py`, central-catalog-authoritative "lockdown" collection like `organizations`/`resource_types`), editable from the central dashboard. `cert_api.py`/`catalog_io.py` now call the API/router instead of importing `CATALOG`; `modules/operations/taskings/repository.py`'s own separate hardcoded `CAPF109_CERT_TYPE_CODES` dict (a duplicate of 5 of these ids) was replaced by a cached lookup against the same catalog.
- Legacy Source: pre-cutover, when there was no Mongo-backed way to store this catalog at all.
- Removal Condition: this module is kept only as the seed source for `server/sarapp_db/sarapp_db/migrations/seed_certification_types_from_hardcoded_catalog.py` (a one-time migration, already run against this installation's local catalog). Safe to delete — along with that migration script and the dev-only `modules/devtools/panels/dev_cert_catalog_editor.py` (already removed) — once every server that needs the seed has run it and no one needs to re-derive it from this file again.
- Verification: `rg -n "from modules.personnel.models.cert_catalog import|models\.cert_catalog" --glob '!*/migrations/*'` confirmed 2026-10-21 that the only remaining import is the already-run migration script. **Not yet verified**: whether every deployed server (not just this local install) has run that migration — confirm before deleting.

### Legacy `certification_types`/`certification_tags` pre-cutover data
- Location: `sarapp_master.certification_types` / `sarapp_master.certification_tags` documents that predate the 2026-10-10 seed (identifiable by `certification_type_id` being a plain numeric *string* like `"1"`, `"2"`, `"7"` — an independent, unrelated sequential scheme, not the catalog's bucketed integer `id` field like `1001`/`2001`/`6004`).
- Purpose: an older, differently-sourced CAP certification list (e.g. `"ADIS"`, `"AOBD"` under id `"2"`) that predates the current hardcoded-then-migrated catalog and was never read by any current code path.
- Legacy Source: unknown prior data-entry/import pass; not traceable to any current importer.
- Removal Condition: safe to delete (`db.certification_types.delete_many({"certification_type_id": {"$type": "string"}})` and the analogous `certification_tags` rows) once confirmed no historical/audit reason to keep them. Not deleted automatically by the seed migration, which only inserts alongside them.
- Verification: `server/sarapp_db/sarapp_db/migrations/seed_certification_types_from_hardcoded_catalog.py`'s docstring and the research that found this during the certification-catalog migration. **Not yet verified**: this requires a live Mongo connection to inspect `sarapp_master`; not actionable from a session without `SARAPP_MONGO_URI` configured.

### Hardcoded validation profiles (validation_profiles.py)
- Location: `modules/personnel/models/validation_profiles.py` (`PROFILES`, `QualProfile`, `PROFILES_VERSION`, `get_profile`)
- Purpose: was the live source for qualification profile checks until the 2026-10-10 migration to a real Mongo-backed `qualification_types` catalog, now read via `cert_api.list_qualifications()`/`qualifications_met()`.
- Legacy Source: pre-cutover, when there was no Mongo-backed way to store this catalog at all.
- Removal Condition: this module is kept only as the seed source for `server/sarapp_db/sarapp_db/migrations/seed_qualification_types_from_hardcoded_profiles.py` (a one-time migration, already run against this installation's local catalog). Safe to delete, along with that migration script, once every server that needs the seed has run it and no one needs to re-derive it from this file again.
- Verification: `rg -n "from modules.personnel.models.validation_profiles import|models\.validation_profiles" --glob '!*/migrations/*'` confirmed 2026-10-21 that the only remaining import is the already-run migration script. **Not yet verified**: whether every deployed server has run that migration — confirm before deleting.

### Finance Attachments Use Filesystem Paths Instead Of GridFS
- Location: `server/sarapp_db/sarapp_db/api/routers/finance.py` (`AttachmentBody.file_path`, `create_attachment`)
- Purpose: Finance/admin attachments (fuel receipts, expense backup, etc.) store a local filesystem `file_path` string on the `finance_attachments` document instead of storing the file's bytes in GridFS like every other incident attachment (`IncidentCollections.ATTACHMENTS`, via `server/sarapp_db/sarapp_db/api/routers/attachments.py`).
- Legacy Source: Predates the GridFS attachment convention adopted for the main `attachments` collection; never migrated to match.
- Removal Condition: `finance_attachments` uploads go through the same GridFS pattern as `attachments` (store bytes in `attachment_files`, reference by `gridfs_file_id`), and existing `finance_attachments` rows with a bare `file_path` are migrated or backfilled. This is feature work (a rewrite), not a dead-code deletion.
- Verification: Confirmed while building the universal incident export/import format (`server/sarapp_db/sarapp_db/export_import/`) — exporting an incident bundles every GridFS attachment, but a finance attachment's actual file lives outside Mongo entirely and does not travel with the export, only its metadata row does.

### Outdated forms guidance
- Location: `README.md` (repo root)
- Purpose: the root README's "Repository layout"/"Working with data" sections describe a pre-Mongo, pre-reorg architecture — a SQLite `data/master.db`/`data/incidents/<id>.db` layer, `main.py`/`modules/` at the repo root, `modules/forms.FormRegistry`/`FormSession` as current guidance, and no mention of `sarapp_db`/MongoDB, `apps/desktop/sarapp_desktop/`, or `apps/web/`. Not specific to forms — the whole document is stale. This is a documentation-accuracy task, not a dead-code deletion.
- Legacy Source: predates the Mongo cutover and the `apps/desktop/sarapp_desktop` reorg; never updated afterward.
- Removal Condition: README rewritten to describe the current architecture (MongoDB via `sarapp_db`, `apps/desktop/sarapp_desktop/` as the desktop app root, `apps/web/`, the shared FastAPI app) and to mark `forms/sets/**/mapping.json` as canonical with profile/`data/templates` flows called out as legacy only.
- Verification: diff README.md against `agents.md`'s Overview/Directory Orientation sections for architecture drift.
- Note 2026-10-21: an exact duplicate copy at `data/library/README.md` (inside the Reference Library module's runtime storage, left over from a repo reorg commit) was deleted — that was a stray artifact, not real reference-library content. `modules/forms_creator/BINDING_PIPELINE.md`'s incorrect "`bindings.py` is dead code" claim was also corrected in the same pass; that file is otherwise actively maintained and accurate, and `bindings.py` itself is tracked as a confirmed-live shim in `activeshims.md` now, not part of this entry.

### logistics_resource_requests collection
- Location: `server/sarapp_db/sarapp_db/migrations/migrate_logistics_resource_requests_to_resource_requests.py`
- Purpose: duplicate Mongo collection name used briefly by the Logistics Resource Request / ICS-213RR router. Runtime code now writes the canonical `resource_requests` collection only.
- Legacy Source: Mongo-era naming drift from module/table name `logistics_resource_requests` while incident overview and mobile planning already expected `resource_requests`
- Removal Condition: all deployed incident databases have run the one-time migration with `--drop-legacy`, or inspection confirms no `logistics_resource_requests` collection exists in any incident database
- Verification: run `python -m sarapp_db.migrations.migrate_logistics_resource_requests_to_resource_requests --dry-run` and confirm zero legacy docs remain before deleting this entry. **Not yet verified**: requires a live Mongo connection; not actionable from a session without `SARAPP_MONGO_URI` configured.
