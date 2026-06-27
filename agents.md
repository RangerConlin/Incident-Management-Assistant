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
- All incident-database writes go through a `sarapp_db.mongo.repository.BaseRepository` subclass — routers must never call `insert_one`/`update_one`/`delete_one`/etc. directly on a raw collection. `BaseRepository` is the single place that stamps timestamps/ids and broadcasts the change to `IncidentCache` WebSocket clients; bypassing it silently drops both. Most routers (29 as of 2026-06-27) are already on `BaseRepository` — see "Axis 2 status" below for the current list and the 11 still on raw writes. New/touched routers must use it.

## Directory Orientation
- `bridge/`: QObject bridges. Slot-friendly, emit signals on state changes.
- `modules/`: Functional areas (command, planning, operations, logistics, communications, forms, ICS-214, intel/weather, GIS, safety/ORM, medical, liaison, public information, finance, admin catalogs, toolkits, UI customization, etc.). Include `data/`, `panels/`, `api.py`, `windows.py`, `services.py`, or `bridge.py` as established locally. Use dataclasses + repositories.
- `notifications/`, `panels/`, `ui/`, `ui_bootstrap/`: Widgets, dialogs, bootstrap scripts.
- `styles/`, `utils/styles.py`: Shared palette and helpers.
- `utils/`: App state, logging, filesystem, theme, incident context. Extend, don't duplicate.
- `tests/`: Pytest suites for models, repositories, bridges. Module-level tests under `modules/**/tests`.
- `Design Documents/`, `profiles/`, `notifications/assets/`: Reference and profile content.
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

### Two Separate Migration Axes — Don't Conflate Them
There are two independent cutover efforts in flight. A module can be fully done with one and not started on the other — check both separately, don't infer one from the other.

**Axis 1 — Client-side: SQLite file → HTTP API.** Did the UI module stop opening a local `.db` file and switch to an `Api*Repository` class that calls `utils/api_client.py`? This is a per-module, client-side concern.

**Axis 2 — Server-side: raw pymongo → `BaseRepository`.** Did the FastAPI router (`data/db/sarapp_db/api/routers/<name>.py`) stop calling `insert_one`/`update_one`/`delete_one` on a raw collection handle (typically via a local `_col(incident_id)` helper) and switch to a `BaseRepository` subclass? This determines whether writes get `created_at`/`updated_at`/`deleted` stamped and broadcast to `IncidentCache` WebSocket clients — independent of whether the UI talks to the API or not.

#### Axis 1 status (as of 2026-06-27)

| Module | Submodule | Status |
|---|---|---|
| `modules/admin` | `hazard_types` | Done |
| `modules/admin` | `resource_types` | Done |
| `modules/command` | `incident_organization` | Done |
| `modules/command` | (rest of module) | Done |
| `modules/common` | — | Done |
| `modules/communications` | `traffic_log` | Done |
| `modules/communications` | (rest of module) | Done |
| `modules/facilities` | — | Done |
| `modules/statusboards` | — | Done |
| `modules/personnel` | `units_organizations` | Done |
| `modules/personnel` | (rest of module) | Done |
| `modules/forms_creator` | — | Done |
| `modules/gis` | — | Done |
| `modules/logistics` | — | Done |
| `modules/operations` | — | Done |
| `modules/planning` | — | Done |
| `modules/finance` | — | Done |
| `modules/referencelibrary` | — | Done |

Every directory under `modules/` was swept (`sqlite|\.execute\(\s*["']` across all `.py` files, tests excluded) as of 2026-06-27. Modules not listed above (`approvals`, `devtools`, `disasterresponse`, `ics214`, `incidents`, `initialresponse`, `intel`, `liaison`, `medical`, `plannedtoolkit`, `projection_dashboard`, `public_information`, `safety`, `sartoolkit`) had zero hits and are presumed clean — they were never flagged as having sqlite-shaped code in the first place, not omitted oversights. No reliable "next in queue" ordering exists — multiple agents work this repo concurrently. Re-run the sweep before trusting this table; it decays the moment another agent touches a router or repository.

#### Axis 2 status (as of 2026-06-27)
Per-file status of `data/db/sarapp_db/api/routers/` (mirrored under `cloud_server/sarapp_db/api/routers/` — update both).

On `BaseRepository`: `hazard_types.py`, `incident_org.py`, `communications.py`, `objectives.py`, `operations.py`, `aircraft.py`, `approvals.py`, `canned_comm_entries.py`, `certifications.py`, `checkin.py`, `equipment.py`, `facilities.py`, `forms.py`, `finance.py`, `gis.py`, `hospitals.py`, `ic_overview.py`, `ics214.py`, `incident_resources.py`, `initialresponse.py`, `intel.py`, `liaison.py`, `logistics_resource_requests.py`, `logistics_resource_status.py`, `lookup_types.py`, `medical.py`, `meetings.py`, `organizations.py`, `safety.py`, `safety_templates.py`, `weather.py`.

Still on raw writes: `objective_templates.py`, `operational_periods.py`, `personnel.py`, `resource_types.py`, `strategy_templates.py`, `vehicles.py`, `work_assignments.py`, `auth_sessions.py`, `plannedtoolkit.py`, `public_information.py`, `reference_library.py`.

Not applicable (no writes): `geocoding.py`, `incident_stream.py`.

Re-run before trusting — one-time grep snapshot, not maintained automatically:
```bash
cd data/db/sarapp_db/api/routers
for f in *.py; do grep -q "(BaseRepository)" "$f" && echo "BaseRepository: $f" || grep -qE "insert_one|update_one|delete_one" "$f" && echo "raw write: $f"; done
```

### MongoDB Schema Design Decisions
- `work_assignments` map to strategies (NOT tasks).
- Task narrative, debrief, assignment_ground/air all embedded inside task documents.
- `resources` collection = `logistics_resource_status_items` (status snapshot, not raw inventory).
- String UUID4 `_id` fields, Pydantic v2, soft deletes.
- Finance (`data/db/sarapp_db/api/routers/finance.py`): all collections incident-scoped, no master-level finance data — the old sqlite `vendors` master table had zero readers/writers and was dropped, not migrated. `dashboard`/`fuel-report`/`pending-approvals` are Python-side aggregation in the router (no Mongo equivalent to the old SQL `JOIN`/CTE/`UNION` queries) rather than DB-side. `finance_approvals` is its own collection, not the generic `APPROVAL_INSTANCES`/`APPROVAL_RECORDS` system (`approvals.py`) — that system already has an extensible `_ENTITY_COLLECTIONS` registry and finance's submit/approve workflow could plausibly be rebuilt on it, but that's a real architecture decision deferred rather than made unilaterally during a faithful port. `modules/finance/approvals.py` and `modules/finance/rates.py` were deleted outright during migration — both had zero callers anywhere, and `rates.py` referenced `labor_rates`/`equipment_rates` tables that were never even created by the old schema. Finance overall is still heavily scaffolded (UI-incomplete) — the migration covers what the old sqlite schema and `services.py` actually implemented, not a feature-complete module.
- Reference Library (`data/db/sarapp_db/api/routers/reference_library.py`, raw pymongo, not yet on `BaseRepository` — see Axis 2): `modules/referencelibrary/api/public_api.py` was already API-backed before this pass; the only dead weight was unused SQLAlchemy ORM models (`Document`/`Collection`/`CollectionDocument`) and an FTS5 search helper (`services/search.py`) with zero callers anywhere — `public_api.search_references` already used the router's Mongo `$regex` search instead. Both removed; `models/reference_models.py` now only holds the still-used `Metadata` dataclass. Also fixed a real pre-existing bug found during verification: the router returned `int_id` but every caller (including `public_api.get_reference_by_id`) expects `id` — added a `_finalize()` helper to alias it, matching the convention in `forms.py`/`finance.py`. This module has zero live UI consumers yet (only re-exported at the package level) — heavily scaffolded, like finance.
- Forms (`data/db/sarapp_db/api/routers/forms.py`): family -> template -> version. **Family = issuing agency** (FEMA, CAP, SAR, ICS Canada, USCG, Custom), **template = one form within that agency's set** (e.g. FEMA's ICS 204), **version = a specific revision** of that form's layout/fields over time. Mirrors the `forms/sets/<agency>/<code>/` directory layout already in the repo. `modules/forms_creator/services/templates.py` (`FormService`) flattens this back into one dict per template for the rest of the module.

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
- **FastAPI routers**: Incident/master Mongo-data routers live under `data/db/sarapp_db/api/routers/` (mirrored byte-for-byte under `cloud_server/sarapp_db/api/routers/` — update both or they drift). A small number of modules keep a self-contained `modules/<module>/api.py` (e.g. `forms_creator`, `initialresponse`) for module-local, non-Mongo endpoints. Test with FastAPI app inclusion.
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
- **This is the single source of truth.** `CLAUDE.md` is a thin pointer that `@`-imports this file — do not duplicate content there. Edit only `agents.md`; any agent (Codex, Claude Code, etc.) working in this repo should update this file when wiring/architecture changes, not a per-tool copy.

## Text & Encoding Hygiene
- All repo text files must be UTF-8 (no BOM) with LF line endings.
- Avoid pasting from Word/PDF. Paste as plain text and replace curly quotes/dashes as needed.
- Symptoms to look for: mojibake sequences where apostrophes, dashes, or currency symbols render as multiple accented/garbled characters.
- Audit locally: `python tools/encoding_audit.py --summary`.
- Gate in CI: `python tools/encoding_audit.py --fail-on-find` (fails build on hits).
- Fix approach: reopen the file with UTF-8 encoding in your editor, retype the affected characters, or convert the file encoding to UTF-8.
- Console note (Windows): set UTF-8 code page before running tools to avoid display issues: `chcp 65001`.
- Pre-commit hooks: install once with `pipx install pre-commit` or `pip install pre-commit`, then run `pre-commit install`. CI runs the same checks.
- Local checks: `pre-commit run --all-files`.
- Encoding gate: current policy fails on decode errors only; once mojibake is cleaned, flip the hook to `--fail-kinds decode-error,mojibake,control,replacement`.

## Module Inventory
The app is organized around ICS sections. Each module has its own panels, services, repository, and optional API router.

| # | Module | Description |
|---|--------|-------------|
| 1 | Command | Incident setup, objectives, status flags, operational periods, IAP builder |
| 2 | Planning | Strategic objectives, task tracking, IAP inputs, planning logs |
| 2-1 | Strategic Objectives | Objective lifecycle, approval workflow, audit trail, task linkage |
| 3 | Operations | Field execution, team assignments, real-time task status, ICS 214 logging |
| 3-1 | Taskings | Task creation/assignment, narrative log, debrief forms, ICS 204/CAPF 109 |
| 4 | Logistics | Resource requests, inventory, check-in/out, assignment workflow |
| 4-1 | Resource Request | ICS 213-RR workflow, approval chain, fulfillment tracking |
| 5 | Communications | Chat, ICS 213 messages, ICS 205 channel plan, comms log |
| 6 | Medical & Safety | Medical plans, safety messages, ICS 206, CAP ORM |
| 6-1 | CAP ORM | Operational Risk Management for CAP missions |
| 6-2 | Weather | NOAA/NWS weather panels, advisory/lightning tools |
| 7 | Intel | Data, clue management, intelligence dashboard |
| 8 | Liaison | Agency contacts, support requests, notifications |
| 9 | Personnel & Role Mgmt | Roster, org structure, assignments, qualifications, accountability |
| 9-1 | Personnel Certifications | Certification tracking per personnel record |
| 10 | Reference Library | ICS forms, agency docs, SOPs, guides |
| 11 | ICS Forms & Documentation | Fillable forms, auto-fill from live data, form versioning |
| 12 | Finance/Admin | Time tracking, expense reporting, procurement, reimbursement |
| 13 | Status Boards | Global and module-specific boards (teams, personnel, equipment, tasks, etc.) |
| 14 | Public Information | Press releases, briefing log, public info contacts |
| 15 | Mobile App Integration | Future: sync with field/mobile app |
| 16 | Training/Sandbox Mode | Simulated incidents, practice environment |
| 17 | SAR Toolkit | SAR-specific calculators, clue management, workflows |
| 18 | Disaster Response Toolkit | Floods, wildfires, hurricanes, etc. |
| 19 | Planned Event Toolkit | Event planning, vendor/permitting, public safety, promotions |
| 20 | Initial Response Toolkit | Hasty search, rapid tasking, initial response workflows |
| 21 | UI Customization | Template selector, custom theme editor, dashboard builder |
| XX | AI Integration | Future: assistant, automation, smart forms |
| XX | Advanced GIS | Future: external mapping platforms, AVL, drone feeds |

## Design Phases (Roadmap)
1. Core System & User Foundation
2. Team Operations, Personnel, and Status Boards
3. Communications & Public Information
4. Forms, Documentation, & Reference Library
5. Logistics, Medical, & Safety
6. Intel & Mapping
7. Advanced Operations & Toolkits
8. UI Customization & Multi-Window UX
9. Status Boards, Automation, & Reporting
10. Finance/Admin & Incident Closeout
11. Mobile Integration & Future Systems
12. Special/Planned (AI & Advanced GIS)

Full phase and module detail: [Design Documents/designplan.md](Design%20Documents/designplan.md)
