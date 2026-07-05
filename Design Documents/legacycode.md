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
- Status: `legacy-compat-active`
- Location: `data/db/sarapp_db/api/routers/checkin.py`, `data/db/sarapp_db/api/routers/incident_resources.py`, `data/db/sarapp_db/mongo/collection_names.py`, `data/db/seed_incidents_from_sqlite.py`
- Purpose: `checkins` and `check_in_out` were the pre-redesign tables for personnel and non-personnel resource tracking respectively. `checkin_history` stored status change events per-person. All three are superseded by the `resource_status` collection, which is the new single source of truth for all resource types and embeds status history in `status_log`.
- Legacy Source: pre-`resource_status` era resource tracking design where personnel and non-personnel used separate collections
- Removal Condition: all roster reads and check-in writes are confirmed to use `resource_status`; no active code reads `checkins`, `check_in_out`, or `checkin_history` outside of data migration scripts
- Verification: grep for `checkins`, `check_in_out`, `checkin_history` in routers and services; confirm no runtime callers remain

### logistics_resource_status_items collection
- Status: `legacy-compat-active`
- Location: `data/db/sarapp_db/mongo/collection_names.py`, `data/db/sarapp_db/api/routers/` (logistics_resource_status router)
- Purpose: was the board's own copy of status rows, populated once by the sync service and never updated live. Replaced by `resource_status`, which is written by the checkin service and ResourceStatusDesk and broadcast via WebSocket.
- Legacy Source: pre-`resource_status` design where the board maintained its own denormalized copy separate from checkins/check_in_out
- Removal Condition: the old logistics resource-status router and collection constant are confirmed unused
- Verification: grep for `logistics_resource_status_items` and the old `/logistics/resource-status` route prefix

### CIStatus enum
- Status: `legacy-compat-active`
- Location: `modules/logistics/checkin/models.py`
- Purpose: status enum for roster payloads using "CheckedIn" vocabulary (vs. "Checked In" in resource_status). Retained for import compatibility at roster-reading call sites not yet migrated.
- Legacy Source: pre-`resource_status` checkin vocabulary mismatch
- Removal Condition: all callers are confirmed to use `RESOURCE_STATUSES` from `resource_status/models.py`; no code imports `CIStatus` for new status handling
- Verification: grep for `CIStatus` imports; confirm only compatibility bridging code uses it

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
- Router: `data/db/sarapp_db/api/routers/task_narratives.py` (`NarrativeRepository(BaseRepository)`).
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

### app/modules/planning/iap/models/repository.py — IAP CRUD in SQLite
- Status: ~~`legacy-compat-active`~~ **REMOVED 2026-07-03**
- SQLite removed. `IAPRepository` now calls `GET/PUT/DELETE /api/incidents/{id}/iap/packages`.
- Router: `data/db/sarapp_db/api/routers/iap.py` (`IAPPackagesRepository(BaseRepository)`); forms embedded in package doc.
- `IAPService._build_repository()` simplified — no longer resolves SQLite file paths.
- Tests rewritten to use FastAPI TestClient against the new router.
