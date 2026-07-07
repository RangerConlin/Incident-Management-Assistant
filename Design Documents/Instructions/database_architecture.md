# Database Architecture

## Persistence Architecture
- **MongoDB** is the active backend for cut-over modules. Three logical databases:
  - `sarapp_system` for server/app configuration
  - `sarapp_master` for agency-wide reference data such as personnel, vehicles, equipment, and templates
  - `sarapp_incident_<id>` for incident-scoped data, audit trail, and forms
- **SQLite** files in `data/` remain for modules not yet cut over, including `data/master.db` and `data/incidents/<id>.db`.
- Key MongoDB files in `data/db/sarapp_db/mongo/`:
  - `collection_names.py` for collection constants
  - `indexes.py` for idempotent index creation
  - `database_manager.py` for `get_system_db()`, `get_master_db()`, and `get_incident_db(id)`
- All UI code goes through `utils/api_client.py` (`httpx.Client` singleton). Do not add direct DB access from the UI layer.
- Active incident UI reads should prefer `utils.incident_cache.incident_cache` when the needed collection is available there. The cache is loaded from a bounded `/api/incidents/{incident_id}/snapshot` response and kept current by WebSocket events. Do not bypass API writes; write through routers/repositories and let broadcasts update the cache.
- Stable master/global lookup reads should use `utils.catalog_cache.catalog_cache` where practical, with explicit invalidation after catalog writes.
- Do not cache large binary/export content in RAM by default. Heavy/history collections should be recent-only, capped, or paged.

## Templates And Config
- Templates/forms live in `data/forms`, `data/templates`, and `profiles/`.
- Theme tokens live in `utils.theme_manager` and `styles/palette.py`.
- UI customization data lives in `modules/ui_customization` repositories/models.

## Active Incident Number
- Source of truth: `utils/state.py` via `AppState`.
- Read in UI/bridges with `AppState.get_active_incident()`.
- Prefer string IDs for persistence via `utils.incident_context.get_active_incident_id()`.
- DB path helper: `utils.incident_context.get_active_incident_db_path()` raises if there is no active incident.
- Set/update selection with `AppState.set_active_incident(<incident_number>)`. This also synchronizes `incident_context` and emits `app_signals.incidentChanged` (`str`).
- Listen to `utils.app_signals.app_signals.incidentChanged` to refresh bound views.
- FastAPI/services should accept `incident_id` explicitly where practical so routing stays obvious and testable.
- Tests can set `AppState.set_active_incident("TEST-123")` or `incident_context.set_active_incident("TEST-123")`; use `CHECKIN_DATA_DIR` for sandboxed paths.
