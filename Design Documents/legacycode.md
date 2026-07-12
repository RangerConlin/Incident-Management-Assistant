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
```

## Inventory

Add entries below this line.

### checkins, check_in_out, checkin_history collections
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-12**
- Runtime collection constants, indexes, and router/service reads were removed. Personnel check-in CRUD/history now uses `resource_status`; status history is embedded in `resource_status.status_log`.

### logistics_resource_status_items collection
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-12**
- Old `/logistics/resource-status` router and collection constant removed. Initial Response resource picture writes `resource_status` rows with `entity_type="initial_response"`.

### logistics_resource_requests collection
- Status: `legacy-compat-candidate`
- Location: `data/db/sarapp_db/migrations/migrate_logistics_resource_requests_to_resource_requests.py`
- Purpose: duplicate Mongo collection name used briefly by the Logistics Resource Request / ICS-213RR router. Runtime code now writes the canonical `resource_requests` collection only.
- Legacy Source: Mongo-era naming drift from module/table name `logistics_resource_requests` while incident overview and mobile planning already expected `resource_requests`
- Removal Condition: all deployed incident databases have run the one-time migration with `--drop-legacy`, or inspection confirms no `logistics_resource_requests` collection exists in any incident database
- Verification: run `python -m sarapp_db.migrations.migrate_logistics_resource_requests_to_resource_requests --dry-run` and confirm zero legacy docs remain before deleting this entry

### Personnel legacy-id migration scripts
- Status: `legacy-compat-candidate`
- Location: `data/db/seed_master_from_sqlite.py`, `data/db/seed_incidents_from_sqlite.py`, `data/db/rebuild_demo_personnel.py`
- Purpose: one-time SQLite-to-Mongo migration helpers that still write `personnel_id`, `badge_number`, and other old roster shapes during data conversion
- Legacy Source: pre-Mongo demo/seed data and one-off cutover backfills
- Removal Condition: the repo no longer needs to migrate SQLite-era personnel data or remap demo incidents
- Verification: no code paths or tests import these scripts for normal runtime behavior
- Notes: keep only as offline scripts; do not add new runtime compatibility logic around them

### Demo check-in seeder
- Status: `legacy-compat-active`
- Location: `data/db/seed_demo_checkins.py`
- Purpose: one-off/demo-only Mongo seeder that backfills personnel check-ins and `resource_status` rows from existing incident team rosters
- Legacy Source: temporary demo data population for the Mongo cutover and board validation
- Removal Condition: demo incidents no longer need scripted backfill of check-ins/resource-status rows
- Verification: the seeder is not imported by runtime code and is only used as an offline utility

### models/database.py — raw master catalog reads
- Status: ~~`legacy-compat-active`~~ **DELETED 2026-07-03**
- Had zero callers at time of deletion. All functions were dead code superseded by the API layer.

### models/master_catalog.py — generic SQLite CRUD service
- Status: ~~`legacy-compat-active`~~ **DELETED 2026-07-03**
- Only caller was `bridge/catalog_bridge.py`, which was itself deleted (see below).

### bridge/incident_bridge.py — task narrative CRUD in SQLite
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-03**
- SQLite removed. `IncidentBridge` now calls `POST/PATCH/DELETE /api/incidents/{id}/narratives`.
- Router: `data/db/sarapp_db/api/routers/task_narratives.py`; narrative entries are embedded in `tasks.narrative` and written through a task `BaseRepository` subclass.
- Dead import removed from `main.py`.

### bridge/catalog_bridge.py — SQLite-backed catalog bridge
- Status: ~~`legacy-compat-active`~~ **DELETED 2026-07-03**
- `CatalogBridge` class was imported in `main.py` but never instantiated anywhere in the codebase. Dead import removed from `main.py`, then file deleted along with `models/master_catalog.py`.

### utils/audit.py — SQLite audit log
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-03**
- `write_audit()` and `fetch_last_audit_rows()` now call `POST /api/audit` and `GET /api/audit`.
- New router: `data/db/sarapp_db/api/routers/audit.py` (prefix `/api/audit`).
- Global events → `SystemCollections.AUDIT_GLOBAL`; incident-scoped → `IncidentCollections.AUDIT_LOGS` via `AuditLogRepository(BaseRepository)`.

### utils/session.py — redundant SQLite user_sessions write
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-03**
- SQLite `user_sessions` writes removed. `start_session()` is now a thin wrapper around `_start_api_session()`. `end_session()` only calls the API logout endpoint.
- `main.py` quit handler now gates on `AppState.get_active_api_session_id()`.

### utils/incident_meta.py — ICP location in SQLite
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-03**
- `get_icp_location()` now calls `GET /api/incidents/{id}/profile`.
- Profile PATCH extended to accept direct `latitude`/`longitude` fields (not facility-only).
- Profile GET extended to return `latitude` and `longitude` fields.

### models/sqlite_table_model.py — QML-era table model
- Status: ~~`legacy-compat-active`~~ **DELETED 2026-07-03**
- `SqliteTableModel` was imported in `main.py` but never instantiated anywhere. Dead import removed, file deleted.

### modules/_infra/repository.py + modules/_infra/base.py — SQLAlchemy/SQLite layer
- Status: ~~`legacy-compat-active`~~ **DELETED 2026-07-03**
- `get_incident_engine()` and `with_incident_session()` had zero callers. `base.py` (3 lines, just `declarative_base()`) was only imported by `repository.py`. Both deleted.

### cloud_server/sarapp_db/** — mirrored Mongo/router tree
- Status: ~~`legacy-compat-candidate`~~ **DELETED 2026-07-12**
- Was: `cloud_server/sarapp_db/**` (routers, mongo client, schemas) — a full mirrored copy of `data/db/sarapp_db/` from a pre-router cloud-server design where `cloud_server/` ran as a second, self-hosted MongoDB-backed backend. `cloud_server/` was later repurposed into a stateless reverse-tunnel router (see `Design Documents/Instructions/cloud_router_architecture.md`); this mirror had been dead weight since then — nothing under `cloud_server/router/`, `cloud_server/main.py`, or `cloud_server/server_manager.py` ever imported it, and `sarapp_server.py` explicitly excluded `cloud_server` from its local-import path because of it.
- Also removed the tooling that existed only to keep the mirror in sync: `scripts/validate-cloud-server-mirror.sh`, its pre-commit hook in `.claude/settings.json`, and the auto-mirror step in the `new-router`/`new-module` skills. `Design Documents/Instructions/api_router_rules.md` already said mirroring wasn't required; the deleted tooling had drifted out of sync with that and was still generating pointless mirror edits (see git history on `cloud_server/sarapp_db/api/routers/communications.py` immediately before this deletion for an example).

### CAP ORM router endpoints and collections — superseded by Safety Risk Manager
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-12**
- CAP ORM collection constants, indexes, summary endpoint, and SQLAlchemy model were removed. Compatibility `/safety/orm/form` and `/safety/orm/hazards` endpoints now synthesize/read/write CAPF-160-shaped data from canonical `hazards` documents.

### intel_clues collection and endpoints
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-12**
- Communications clue capture now writes canonical `intel_items` records with `item_type="Clue"`. Task-detail clue linking and form-context clue summaries were already using `IntelItemsRepository`.

### app/modules/planning/iap/models/repository.py — IAP CRUD in SQLite
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-03**
- SQLite removed. `IAPRepository` now calls `GET/PUT/DELETE /api/incidents/{id}/iap/packages`.
- Router: `data/db/sarapp_db/api/routers/iap.py` (`IAPPackagesRepository(BaseRepository)`); forms embedded in package doc.
- `IAPService._build_repository()` simplified — no longer resolves SQLite file paths.
- Tests rewritten to use FastAPI TestClient against the new router.
