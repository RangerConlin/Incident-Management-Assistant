# AGENTS

## Incident-Management-Assistant Overview
- Desktop-first incident management suite built with **PySide6**.
- Python modules in `modules/` provide UI panels, FastAPI routers, and repository-based persistence.
- `main.py` boots the Qt app, builds the menu tree, and loads ADS docks/widgets.
- Domain data lives in `data/`. Active backend is **MongoDB** via the `sarapp_db` package (`data/db/sarapp_db/`). Legacy SQLite files remain for modules not yet cut over.
- Tests live in `tests/` and `modules/**/tests` using `pytest`.
- Master design document: **Design Documents/designplan.md**.
- Absolutely no new QML is to be used. Treat existing QML-facing bridges/docstrings as legacy compatibility unless a user explicitly asks to remove or migrate them.
- Use **"incident"** everywhere — never "mission".

## Hard Rules
- No new QML files.
- No `backend/` directory — files go under root, `lan_server/`, `cloud_server/`, or `data/`.
- Database framework belongs under `data/`, not `core/`.
- Never create demo/fake data — only migrate or use data that already exists.
- Never wire MongoDB directly into the UI — architecture is UI → API server → MongoDB.
- `SARAPP_MONGO_URI` is never hardcoded — read from environment variable only.

## Directory Orientation
- `bridge/`: QObject bridges. Slot-friendly, emit signals on state changes.
- `modules/`: Functional areas (command, planning, operations, logistics, communications, forms, ICS-214, intel/weather, GIS, safety/ORM, medical, liaison, public information, finance, admin catalogs, toolkits, UI customization, etc.). Include `data/`, `panels/`, `api.py`, `windows.py`, `services.py`, or `bridge.py` as established locally. Use dataclasses + repositories.
- `notifications/`, `panels/`, `ui/`, `ui_bootstrap/`: Widgets, dialogs, bootstrap scripts.
- `styles/`, `utils/styles.py`: Shared palette and helpers.
- `utils/`: App state, logging, filesystem, theme, incident context. Extend, don't duplicate.
- `tests/`: Pytest suites for models, repositories, bridges. Module-level tests under `modules/**/tests`.
- `Design Documents/`, `demos/`, `profiles/`, `notifications/assets/`: Reference and profile content.
- `data/db/sarapp_db/`: Installable MongoDB package (`pip install -e data/` from repo root). Contains collection name constants, indexes, database manager, and API routers.
- `lan_server/`: Self-contained standalone LAN server.
- `cloud_server/`: Headless cloud server stub.
- `server/server_manager.py`: Built-in offline server used by the client.

## Toolchain & Environment
1. **Python**: Target 3.11.
   ```bash
   python3.11 -m venv .venv && source .venv/bin/activate
   ```
2. **Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e data/
   ```
   Update both `requirements.txt` and `pyproject.toml`.
3. **Qt system libs** (Debian/Ubuntu):
   ```bash
   sudo apt-get update
   sudo apt-get install -y libgl1 libegl1 libxcb-xinerama0 libxkbcommon-x11-0
   ```
4. **Optional tools**: Maintain `tool.pyside6-project.files`.

## Running the Desktop App
- Activate venv, ensure Qt libs, run:
  ```bash
  QT_QPA_PLATFORM=xcb python main.py
  ```
- Use `QT_QPA_PLATFORM=offscreen` for CI.
- Settings persist via `SettingsManager`.
- Docks/widgets register through `main.py`, `ui/docks.py`, `ui/widgets/`, module `windows.py` factories, and panel factory functions.
- ADS layout templates persist to `settings/ads_perspectives.ini`. Use `FORCE_DEFAULT_LAYOUT = True` in `main.py` only as a temporary troubleshooting toggle.

## Data & Configuration

### Persistence Architecture
- **MongoDB** is the active backend for cut-over modules. Three logical databases:
  - `sarapp_system` — server/app configuration
  - `sarapp_master` — agency-wide reference data (personnel, vehicles, equipment, templates, etc.)
  - `sarapp_incident_<id>` — one per incident; all incident data, audit trail, forms
- **SQLite** files in `data/` remain for modules not yet cut over (`data/master.db`, `data/incidents/<id>.db`).
- **Key MongoDB files** in `data/db/sarapp_db/mongo/`:
  - `collection_names.py` — all collection name constants
  - `indexes.py` — idempotent index creation
  - `database_manager.py` — `get_system_db()`, `get_master_db()`, `get_incident_db(id)`
- All UI code goes through `utils/api_client.py` (`httpx.Client` singleton) — no direct DB access from UI.

### MongoDB Cutover Status (as of 2026-06-13)
Modules fully cut over to MongoDB:
- `modules/admin` — hazard_types, resource_types + capabilities
- `modules/command` — objectives, IC overview, incident profile, ICS 203 (incident organization)
- `modules/common` — task_types, team_types lookup tables
- `modules/communications` — master channels, ICS 205 plan, traffic log

Deliberately still on SQLite (pending their own cutover):
- `ResourceAssignmentRepository` (bridges master+incident data)
- `resource_type_io.py` (CSV import/export utility)
- `PersonnelPoolRepository` (personnel module not yet cut over)

Next in queue: `modules/disasterresponse`, then alphabetically.

### Templates & Config
- Templates/forms in `data/forms`, `data/templates`, and `profiles/`.
- Theme tokens in `utils.theme_manager` and `styles/palette.py`.
- UI customization data lives in `modules/ui_customization` repositories/models.

### Active Incident Number
- Source of truth: `utils/state.py` (`AppState`).
- Read in UI/bridges: `AppState.get_active_incident()` returns the current incident number (may be `None`).
- Prefer string ID for persistence: `utils.incident_context.get_active_incident_id()` (returns `str | None`).
- DB path helper: `utils.incident_context.get_active_incident_db_path()` (raises if no active incident).
- Set/update selection: `AppState.set_active_incident(<incident_number>)`. This also synchronizes `incident_context` and emits `app_signals.incidentChanged` (`str`).
- Reactivity: listen to `utils.app_signals.app_signals.incidentChanged` to refresh bound views.
- FastAPI/services: accept `incident_id` explicitly in endpoints/services where practical. UI-only panels may resolve from `AppState`/`incident_context` at the boundary, but repositories should keep incident routing obvious and testable.
- Tests: set with `AppState.set_active_incident("TEST-123")` or stub via `incident_context.set_active_incident("TEST-123")`; use `CHECKIN_DATA_DIR` to sandbox data paths.

## Planned Real-Time Architecture (post cutover)
- **IncidentCache**: client-side in-memory dict populated from server snapshot on incident load; kept current by WebSocket push events. All UI reads from cache. Writes go to server via HTTP POST; server broadcasts change event to all clients.
- **WebSocket hub**: FastAPI endpoint per incident at `/ws/incidents/{incident_id}`; server broadcasts typed change events (`team_status_changed`, `task_updated`, etc.). Client `IncidentCache.apply_event()` updates cache and emits Qt signals.
- **Offline resilience**: each client runs a local MongoDB node as a replica set member. On disconnection, client transparently reads/writes local node. On reconnect, MongoDB replica set replication auto-syncs — no manual conflict resolution needed.
- **Implementation order**: finish MongoDB cutover → IncidentCache + WebSocket broadcasts → configure local MongoDB replica → replace HTTP reads with cache reads → remove polling timers from status boards.

## Testing & QA
- Run with:
  ```bash
  pytest --import-mode=importlib
  ```
- Set `QT_QPA_PLATFORM=offscreen` in CI.
- Run targeted suites by path.
- Stub `CHECKIN_DATA_DIR` for temp DBs.
- Use smoke scripts in `scripts/` for audit tests.
- Add or update tests with each code change.

## Coding Standards & Patterns
- **Python**: PEP 8 + typing. Use dataclasses, logging, repositories. Normalize before persistence.
- **Bridges**: Expose methods with `@Slot`. Emit change signals for binding refresh.
- **CLI**: Extend quick actions in `ui/actions/quick_entry_actions.py`. Add pytest coverage.
- **FastAPI routers**: Place in `modules/<module>/api.py` or the established module API package. Test with FastAPI app inclusion.
- **UI panels**: Prefer PySide6 widgets and repository/service boundaries. Open panels through module factories or `MainWindow._open_dock_widget()` so ADS behavior stays consistent.
- **Lookups/catalogs**: Reuse admin resource type, hazard type, team type and task type repositories instead of duplicating local constants when the module already has catalog integration.
- **MongoDB pattern**: append an `Api*Repository` class to the existing repository file; keep the SQLite class in place until the module is fully cut over. UI/service code defaults to the API repo.

## Definition of Done
- Code matches patterns.
- Tests updated and passing.
- New assets registered.
- Docs updated if workflows change.
- No new `backend/` directories, QML files, or hardcoded Mongo URIs.

## Updating This Guide
- Applies to the full repo.
- Add nested `AGENTS.md` for unique subtree rules.
- Keep current with toolchain, repo structure, and MongoDB cutover progress.
- **When you update this file, update `CLAUDE.md` to match.** Both files must stay in sync — they serve different consumers (AI agents vs. Claude Code sessions) but must reflect the same ground truth.

## Text & Encoding Hygiene
- All repo text files must be UTF-8 (no BOM) with LF line endings.
- Avoid pasting from Word/PDF. Paste as plain text and replace curly quotes/dashes as needed.
- Symptoms to look for: mojibake sequences where apostrophes, dashes, or currency symbols render as multiple accented/garbled characters.
- Audit locally: `python scripts/encoding_audit.py --summary`.
- Gate in CI: `python scripts/encoding_audit.py --fail-on-find` (fails build on hits).
- Fix approach: reopen the file with UTF-8 encoding in your editor, retype the affected characters, or convert the file encoding to UTF-8.
- Console note (Windows): set UTF-8 code page before running tools to avoid display issues: `chcp 65001`.
- Pre-commit hooks: install once with `pipx install pre-commit` or `pip install pre-commit`, then run `pre-commit install`. CI runs the same checks.
- Local checks: `pre-commit run --all-files`.
- Encoding gate: current policy fails on decode errors only; once mojibake is cleaned, flip the hook to `--fail-kinds decode-error,mojibake,control,replacement`.
