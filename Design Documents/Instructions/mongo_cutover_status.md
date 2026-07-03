# Mongo Cutover Status

Snapshot date: 2026-07-03 (updated 2026-07-03)

This file tracks the current migration snapshot. Treat it as reference material, not timeless policy. Re-run the checks before relying on it for new work.

## Two Separate Migration Axes
- **Axis 1**: client-side SQLite file -> HTTP API. This asks whether the UI module stopped opening a local `.db` file and switched to an `Api*Repository` that calls `utils/api_client.py`.
- **Axis 2**: server-side raw PyMongo -> `BaseRepository`. This asks whether the FastAPI router stopped writing through a raw collection and now uses a `BaseRepository` subclass for timestamping and change broadcast behavior.
- A module can be complete on one axis and incomplete on the other. Do not infer one from the other.

## Axis 1 Status

| Module | Submodule | Status |
|---|---|---|
| `modules/admin` | `hazard_types` | Done |
| `modules/admin` | `resource_types` | Done |
| `modules/command` | `incident_organization` | Done |
| `modules/command` | (rest of module) | Done |
| `modules/common` | - | Done |
| `modules/communications` | `traffic_log` | Done |
| `modules/communications` | (rest of module) | Done |
| `modules/facilities` | - | Done |
| `modules/statusboards` | - | Done |
| `modules/personnel` | `units_organizations` | Done |
| `modules/personnel` | (rest of module) | Done |
| `modules/forms_creator` | - | Done |
| `modules/gis` | - | Done |
| `modules/logistics` | - | Done |
| `modules/operations` | - | Done |
| `modules/planning` | - | Done |
| `modules/finance` | - | Done |
| `modules/referencelibrary` | - | Done |

Every directory under `modules/` was swept with `sqlite|\\.execute\\(\\s*[\"']` across `.py` files, tests excluded, as of 2026-06-27. Modules not listed in the table had zero hits and were presumed clean at that time. No reliable "next in queue" ordering exists because multiple agents may work the repo concurrently.

## Axis 2 Status
- New incident-scoped collection: `resource_status` — active as of 2026-07-03. This is the single source of truth for all resource types (personnel, vehicle, aircraft, equipment) assigned to an incident. Replaces `checkins`, `check_in_out`, and `logistics_resource_status_items`. Router: `data/db/sarapp_db/api/routers/resource_status.py`, uses `ResourceStatusRepository(BaseRepository)`.
- On `BaseRepository`: `hazard_types.py`, `incident_org.py`, `communications.py`, `objectives.py`, `operations.py`, `aircraft.py`, `approvals.py`, `canned_comm_entries.py`, `certifications.py`, `checkin.py`, `equipment.py`, `facilities.py`, `forms.py`, `finance.py`, `gis.py`, `hospitals.py`, `ic_overview.py`, `ics214.py`, `incident_resources.py`, `initialresponse.py`, `intel.py`, `liaison.py`, `logistics_resource_requests.py`, `logistics_resource_status.py`, `lookup_types.py`, `medical.py`, `meetings.py`, `organizations.py`, `resource_status.py`, `safety.py`, `safety_templates.py`, `weather.py`
- Still on raw writes: `objective_templates.py`, `operational_periods.py`, `personnel.py`, `resource_types.py`, `strategy_templates.py`, `vehicles.py`, `work_assignments.py`, `auth_sessions.py`, `plannedtoolkit.py`, `public_information.py`, `reference_library.py`
- Not applicable (no writes): `geocoding.py`, `incident_stream.py`

## Cross-Cutting SQLite Layer (not yet on API)

The `modules/` Axis 1 sweep was accurate at the module level, but the app still has a foundational SQLite layer in `utils/`, `models/`, and `bridge/` that has not been migrated. All entries below are tracked in `Design Documents/legacycode.md`.

| File | Domain | What it covers | Migration blocker |
|---|---|---|---|
| `models/database.py` | Master catalog | ~~Raw SELECT * for 18 tables~~ **DELETED 2026-07-03** — zero callers | — |
| `models/master_catalog.py` | Master catalog | ~~Generic SQLite CRUD~~ **DELETED 2026-07-03** — only caller was catalog_bridge (also deleted) | — |
| `bridge/catalog_bridge.py` | Certifications | ~~SQLite catalog bridge~~ **DELETED 2026-07-03** — never instantiated; dead import removed from main.py | — |
| `bridge/incident_bridge.py` | Task narrative | **Done 2026-07-03** — calls `GET/POST/PATCH/DELETE /api/incidents/{id}/narratives`; new `NarrativeRepository(BaseRepository)` in `task_narratives.py` | — |
| `utils/audit.py` | Audit log | ~~SQLite~~ **Done 2026-07-03** — calls `POST /api/audit`; new router at `data/db/sarapp_db/api/routers/audit.py` | — |
| `utils/session.py` | Sessions | ~~SQLite redundant write~~ **Done 2026-07-03** — SQLite removed; main.py gates on `get_active_api_session_id()` | — |
| `utils/incident_meta.py` | Incident data | ~~SQLite~~ **Done 2026-07-03** — calls profile GET/PATCH; profile endpoint extended with direct `latitude`/`longitude` | — |
| `models/sqlite_table_model.py` | UI | ~~QML table model~~ **DELETED 2026-07-03** — never instantiated; dead import removed from main.py | — |
| `ui/widgets/data_providers.py` | Dashboard | `equipment_getSnapshot()` and `vehicles_getStatus()` fall back to direct `incident.db` reads | Needs equipment/vehicle snapshot API endpoints |
| `modules/_infra/repository.py` + `base.py` | Objectives | ~~SQLAlchemy layer~~ **DELETED 2026-07-03** — zero callers for all SQLite functions | — |
| `app/modules/planning/iap/models/repository.py` | IAP | **Done 2026-07-03** — `IAPRepository` now calls `GET/PUT/DELETE /api/incidents/{id}/iap/packages`; new `IAPPackagesRepository(BaseRepository)` in `iap.py`; forms embedded in package doc | — |
| `utils/incident_db.py` | File mgmt | **Cleaned 2026-07-03** — duplicate `_active_incident_id` state removed; `_ensure_schema_compatibility()` and dead MongoDB-era table entries in `_REQUIRED_INCIDENT_TABLES` removed. Now lifecycle-only: copy template, validate `narrative_entries` present, bootstrap spatial DB. Canonical incident ID state lives in `incident_context.py`. | — |
| `modules/gis/services/schema_bootstrap.py` | GIS | `spatial_features` / `spatial_feature_links` tables in per-incident `spatial.db` | GIS/spatial DB migration is a separate architectural decision |

### Axis 1 note on `utils/db.py` and `utils/context.py`
`utils/context.py` was deleted 2026-07-03 (zero callers after session/audit cutover). `utils/db.py` has one remaining active caller: `ui/widgets/data_providers.py` (equipment/vehicles snapshot fallback). It will become dead code when that module is fixed.

**Surprise find 2026-07-03:** `modules/command/incident_organization/personnel_repo.py` had a dead `from utils.db import get_master_conn` import that was never used by the class — removed. The module itself (`ApiPersonnelPoolRepository`) was already fully on the API.

**Narrative + IAP cutover 2026-07-03:** `bridge/incident_bridge.py` SQLite removed — narrative CRUD now via `POST/PATCH/DELETE /api/incidents/{id}/narratives` backed by `NarrativeRepository(BaseRepository)` in `task_narratives.py`. `app/modules/planning/iap/models/repository.py` SQLite removed — IAP package/form CRUD now via `GET/PUT/DELETE /api/incidents/{id}/iap/packages/{op}/forms/{id}` backed by `IAPPackagesRepository(BaseRepository)` in `iap.py`; forms embedded in package document. `IAPService._build_repository()` simplified (no file paths). IAP tests rewritten to TestClient pattern. `_REQUIRED_INCIDENT_TABLES` now empty — all data in MongoDB. `narrative_entries` table in `incident.db` is now inert legacy data.

**incident_db.py cleanup 2026-07-03:** Removed duplicate active-incident-id state (`_active_incident_id`, `set_active_incident_id()`, `get_active_incident_id()`) from `utils/incident_db.py`; all callers now use `incident_context.get_active_incident_id()` / `incident_context.set_active_incident()`. Removed `_ensure_schema_compatibility()` and its helpers (`_ensure_notifications_schema()`, `_ensure_column()`) — all migrations targeted MongoDB-era tables. Stripped MongoDB-migrated tables from `_REQUIRED_INCIDENT_TABLES` (only `narrative_entries` remains). `state.py` no longer syncs `incident_db`; `resource_requests/__init__.py` and `data/seed_demo.py` updated to use `incident_context`.

Re-run before trusting. Example snapshot command:

```bash
cd data/db/sarapp_db/api/routers
for f in *.py; do grep -q "(BaseRepository)" "$f" && echo "BaseRepository: $f" || grep -qE "insert_one|update_one|delete_one" "$f" && echo "raw write: $f"; done
```
