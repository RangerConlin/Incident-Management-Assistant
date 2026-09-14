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

### Forms Creator legacy template registry and renderer
- Status: `legacy-compat-candidate`
- Location: `modules/forms_creator/templating.py`, `modules/forms_creator/render.py`, `data/templates/registry.json`, `data/templates/**`
- Purpose: preserves the old registry-plus-YAML rendering path used before the current `forms/sets/<set_id>/<form_id>/template.pdf` plus `mapping.json` pipeline.
- Legacy Source: pre-form-set template records in `data/templates/registry.json` and `data/templates/**` mapping files.
- Removal Condition: no runtime or developer tooling calls `modules.forms_creator.templating.resolve_template()` or `modules.forms_creator.render.render_form()`, and all old `data/templates` entries have either been migrated into `forms/sets/**` or intentionally discarded.
- Verification: `rg -n "modules\.forms_creator\.(templating|render)|resolve_template|render_form|data/templates" modules data tests` shows no production callers except this inventory or removed tests/docs.

### Devtools Template Debug panel
- Status: `legacy-compat-candidate`
- Location: `modules/devtools/panels/template_debug_panel.py`, `modules/devtools/services/template_registry.py`, `modules/devtools/services/renderer_bridge.py`
- Purpose: developer-only UI and services for inspecting the old `data/templates/registry.json` template system.
- Legacy Source: the deprecated `data/templates` registry/render path, separate from Developer -> Forms Creator.
- Removal Condition: the Developer menu no longer exposes Template Debug, or the panel is rewritten to inspect the canonical `forms/sets/**/mapping.json` registry instead.
- Verification: `rg -n "TemplateDebugPanel|template_debug_panel|Template Debug|template_registry|renderer_bridge" modules main.py` confirms no live menu registration or imports remain.

### Legacy data/forms catalog and map-generator assets
- Status: `legacy-compat-candidate`
- Location: `data/forms/**`, `modules/devtools/services/form_catalog.py`, `modules/devtools/services/fema_fetch.py`, `modules/devtools/services/pdf_mapgen.py`, `modules/devtools/services/form_identify.py`
- Purpose: older developer/import tooling and PDF/map assets for a `data/forms/catalog.json` layout.
- Legacy Source: pre-`forms/sets` form catalog and `.map.yaml` storage model.
- Removal Condition: any useful ingestion/scanning functionality has been ported to write `forms/catalog.json`, `forms/sets/<set_id>/<form_id>/template.pdf`, and `mapping.json`; otherwise the old catalog/assets are confirmed unused.
- Verification: `rg -n "data/forms|FormCatalog|fema_fetch|pdf_mapgen|form_identify" modules data tests` shows no production dependency.

### Profile-scoped form template pipeline
- Status: `legacy-compat-candidate`
- Location: `modules/forms_creator/form_registry.py`, `modules/forms_creator/session.py`, `modules/forms_creator/export.py`, `profiles/ics_base/templates/**`
- Purpose: deterministic profile template export pipeline using `profiles/<profile_id>/templates/**`, `FormRegistry`, `FormSession`, and per-profile binding definitions.
- Legacy Source: profile-era template model that is separate from the current `forms/sets/**/mapping.json` system used by `engine.generate()`.
- Removal Condition: all production exports use `modules.forms_creator.engine.generate()` directly or `modules.forms_creator.exporting.ExportService`, and no active profile/template selection workflow depends on `profiles/<id>/templates/**`.
- Verification: `rg -n "FormRegistry|FormSession|export_form\\(|profiles/.*/templates|profiles\\\\.*\\\\templates" modules profiles tests` shows no runtime callers, and profile manager UI no longer references template checksums from this pipeline.

### Unified form export bridge
- Status: `legacy-compat-active`
- Location: `modules/forms_creator/api.py`
- Purpose: compatibility export facade that tries the profile-scoped pipeline first, then falls back to the legacy `data/templates` renderer.
- Legacy Source: callers that still request form output through `export_form_unified()` instead of the canonical `engine.generate()` or `ExportService` path.
- Removal Condition: every production caller of `export_form_unified()` has been migrated to `modules.forms_creator.exporting.ExportService` or a direct `engine.generate()` call using `forms/sets/**/mapping.json`.
- Verification: `rg -n "export_form_unified" modules tests` shows no production callers.
- Known Callers: `modules/command/widgets/objective_detail_dialog.py`, `modules/command/panels/incident_objectives_panel.py`, `modules/safety/print_ics_206.py`, `modules/logistics/print_ics_213_rr.py`, `modules/operations/taskings/repository.py`.

### Forms Creator database template service
- Status: `legacy-compat-active`
- Location: `modules/forms_creator/services/templates.py`, `modules/forms_creator/services/template_importer.py`, `modules/forms_creator/ui/dialogs/NewTemplateWizard.py`, `modules/forms_creator/ui/dialogs/BindingDialog.py`, `modules/forms_creator/scripts/dev_seed.py`, `data/db/sarapp_db/api/routers/forms.py`
- Purpose: API-backed form template and instance workflow based on `FormService`, template configs, and instance export endpoints.
- Legacy Source: database-stored template/instance model that is separate from the current filesystem-backed `forms/sets/**/mapping.json` authoring and export pipeline.
- Removal Condition: user-visible forms workflows, especially Intel -> Forms, either migrate to the canonical form-set registry/export service or are intentionally retired.
- Verification: `rg -n "FormService|NewTemplateWizard|BindingDialog|template_importer|/api/forms|routers.forms" modules data tests` shows no runtime callers and `data/db/sarapp_db/api/app.py` no longer includes the forms router.
- Known Callers: `modules/intel/tabs/forms_tab.py`, `modules/forms_creator/__init__.py`, `modules/forms_creator/services/__init__.py`.

### Standalone PDF filler discovery UI
- Status: `legacy-compat-candidate`
- Location: `modules/forms_creator/pdf_filler/mapping_discovery.py`, `modules/forms_creator/pdf_filler/pdf_filler_widget.py`, `modules/forms_creator/mappings/**`
- Purpose: standalone PDF filler widget and mapping discovery helper for `*.mapping.json` files outside the canonical `forms/sets/**/mapping.json` location.
- Legacy Source: earlier PDF filler workflow that predates the Forms Creator Hub and MapperWindow form-set registry.
- Removal Condition: no standalone UI entry point uses `pdf_filler_widget.py`, and any useful discovery behavior is either removed or rewritten to use `FormSetRegistry`.
- Verification: `rg -n "pdf_filler_widget|mapping_discovery|modules/forms_creator/mappings|\\.mapping\\.json" modules tests` shows no production callers outside intentional import/scanning tools.

### Outdated forms guidance
- Status: `legacy-compat-candidate`
- Location: `data/library/README.md`, `modules/forms_creator/BINDING_PIPELINE.md`
- Purpose: documentation still references older form systems or labels them as current guidance in places.
- Legacy Source: accumulated guidance from the `data/templates`, profile template, and current `forms/sets` eras.
- Removal Condition: documentation clearly states that `forms/sets/**/mapping.json` is the canonical per-form binding source and that profile or `data/templates` flows are legacy only.
- Verification: review docs for `data/templates`, `FormRegistry`, `FormSession`, `profiles/<id>/templates`, and `modules/forms.FormRegistry` references after code cleanup.

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
