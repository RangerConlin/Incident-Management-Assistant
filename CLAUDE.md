# Incident Management Assistant — Claude Instructions

## Project Overview
Desktop-first incident management suite (ICS Command Assistant / SARApp) built with **PySide6** and **FastAPI**. Windows-targeted, multi-module, ADS-docked layout. Target users: Incident Commanders, Section Chiefs, Logistics/Planning personnel, and field teams.

---

## Hard Rules (never break these)

- **No QML** — no new QML files, ever. Existing QML bridge/docstrings are legacy compatibility only.
- **No `backend/` directory** — files go under root, `lan_server/`, `cloud_server/`, or `data/`.
- **No `core/` for DB framework** — database framework belongs under `data/`.
- **Use "incident" not "mission"** — everywhere, all the time.
- **Never create demo/fake data** — only migrate or use data that already exists, however creating fake data is ok if instructed to.
- **Never wire MongoDB directly into the UI** — architecture is UI → API server → MongoDB.
- **`SARAPP_MONGO_URI` is never hardcoded** — read from environment variable only.
- **All text files must be UTF-8 (no BOM) with LF line endings** — audit with `python scripts/encoding_audit.py --summary`.

---

## Architecture

### Frontend
- **PySide6** widgets + Qt Advanced Docking System (PySide6-QtAds)
- Each module has: `models/` or `data/`, `panels/`/`widgets/`/`windows.py`, `services.py`, `repository.py`, optional `api.py`
- Open panels through module factories or `MainWindow._open_dock_widget()` so ADS behavior stays consistent
- Panels opened via menu float by default; users can dock them afterward
- ADS layouts persist to `settings/ads_perspectives.ini`. `FORCE_DEFAULT_LAYOUT` in `main.py` is a temporary debug toggle only

### Backend
- **FastAPI** server (`sarapp_server.py` / `SARAppServerManager`) with uvicorn; routers mounted under `/api`
- HTTP client: `httpx.Client` singleton at `utils/api_client.py` — all modules call `api_client`, no direct DB access from UI code
- **MongoDB** via PyMongo (not async Motor):
  - `sarapp_system` — server/app configuration
  - `sarapp_master` — agency-wide reference data (personnel, vehicles, equipment, templates, etc.)
  - `sarapp_incident_<id>` — one per incident; all incident data, audit trail, forms
- Key MongoDB package: `sarapp_db` at `data/db/sarapp_db/` (install: `pip install -e data/` from repo root)

### Planned Real-Time Architecture (post MongoDB cutover)
- **Client-side IncidentCache**: in-memory dict populated from server snapshot on incident load; kept current by WebSocket push events. All UI reads from cache. Writes go to server via HTTP POST; server broadcasts change event to all clients.
- **WebSocket hub**: FastAPI endpoint per incident at `/ws/incidents/{incident_id}`; server broadcasts typed change events (e.g. `team_status_changed`, `task_updated`). Client `IncidentCache.apply_event()` updates cache and emits Qt signals.
- **Offline resilience**: each client runs a local MongoDB node as a replica set member. On disconnection, client transparently reads/writes local node. On reconnect, MongoDB replica set replication auto-syncs.
- **Implementation order**: finish MongoDB cutover → IncidentCache + WebSocket broadcasts → configure local MongoDB replica → replace HTTP reads with cache reads → remove polling timers.

---

## Directory Structure

| Path | Purpose |
|------|---------|
| `main.py` | Qt app bootstrap, menu tree, ADS dock manager |
| `modules/` | All feature modules (command, planning, operations, logistics, etc.) |
| `data/` | SQLite files, MongoDB seed scripts, `sarapp_db` package |
| `data/db/sarapp_db/` | Installable DB package (PyMongo, Pydantic v2, collection constants, indexes, database manager) |
| `bridge/` | QObject bridges — `@Slot` methods, emit signals on state changes |
| `utils/` | App state, logging, filesystem, theme, incident context — extend, don't duplicate |
| `utils/state.py` | `AppState` — UI session source of truth for active incident, user, role, op period |
| `utils/incident_context.py` | `get_active_incident_id()`, `get_active_incident_db_path()` |
| `utils/api_client.py` | `httpx.Client` singleton |
| `lan_server/` | Self-contained standalone LAN server |
| `cloud_server/` | Headless cloud server stub |
| `server/server_manager.py` | Built-in offline server used by client |
| `settings/` | User settings and ADS perspectives |
| `styles/`, `utils/styles.py` | Shared palette and style helpers |
| `notifications/`, `panels/`, `ui/` | Widgets, dialogs, bootstrap scripts |
| `tests/` | Pytest suites; module-level tests under `modules/**/tests` |
| `Design Documents/` | Long-form design archive (designplan.md) |

---

## Active Incident

- Source of truth: `AppState` in `utils/state.py`
- Read: `AppState.get_active_incident()` → incident number (may be `None`)
- Prefer string ID: `utils.incident_context.get_active_incident_id()` → `str | None`
- DB path: `utils.incident_context.get_active_incident_db_path()` (raises if no active incident)
- Set/update: `AppState.set_active_incident(<incident_number>)` — also syncs `incident_context` and emits `app_signals.incidentChanged` (`str`)
- Reactivity: listen to `utils.app_signals.app_signals.incidentChanged` to refresh bound views
- FastAPI/services: accept `incident_id` explicitly in endpoints; repositories should keep incident routing obvious and testable

---

## MongoDB Migration Status (as of 2026-06-13)

**Completed cutover** (SQLite → MongoDB):
- `modules/admin` — hazard_types, resource_types + capabilities
- `modules/command` — objectives, IC overview, incident profile, ICS 203 (incident organization)
- `modules/common` — task_types, team_types lookup tables
- `modules/communications` — master channels, ICS 205 plan, traffic log

**Still on SQLite** (deliberate, pending their own cutover):
- `ResourceAssignmentRepository` (bridges master+incident data)
- `resource_type_io.py` (CSV import/export utility)
- `PersonnelPoolRepository` (personnel module not yet cut over)
- `modules/command/panels/incident_overview.py` `_get_incident_types` (lookup only)

**Next**: `modules/disasterresponse`, then alphabetically

Key MongoDB files:
- `data/db/sarapp_db/mongo/collection_names.py` — all collection name constants
- `data/db/sarapp_db/mongo/indexes.py` — idempotent index creation
- `data/db/sarapp_db/mongo/database_manager.py` — `get_system_db()`, `get_master_db()`, `get_incident_db(id)`
- `data/db/seed_master_from_sqlite.py` — seeds `sarapp_master` from `data/master.db`
- `data/db/seed_incidents_from_sqlite.py` — seeds all incident databases

Design decisions:
- `work_assignments` map to strategies (NOT tasks)
- Task narrative, debrief, assignment_ground/air all embedded inside task documents
- `resources` collection = `logistics_resource_status_items` (status snapshot, not raw inventory)
- String UUID4 `_id` fields, Pydantic v2, soft deletes

---

## Coding Standards

- **Python**: PEP 8 + typing. Use dataclasses, logging, repositories. Normalize before persistence.
- **Bridges**: Expose methods with `@Slot`. Emit change signals for binding refresh.
- **FastAPI routers**: Place in `modules/<module>/api.py`. Test with FastAPI app inclusion.
- **Lookups/catalogs**: Reuse admin resource type, hazard type, team type, and task type repositories — don't duplicate local constants.
- **CLI**: Extend quick actions in `ui/actions/quick_entry_actions.py`. Add pytest coverage.
- Update both `requirements.txt` and `pyproject.toml` when adding dependencies.
- Update `tool.pyside6-project.files` when adding new assets.

---

## Testing

```bash
pytest --import-mode=importlib
```

- Set `QT_QPA_PLATFORM=offscreen` in CI
- Run `QT_QPA_PLATFORM=xcb python main.py` for desktop (Windows: just `python main.py`)
- Stub `CHECKIN_DATA_DIR` for temp DBs in tests
- Set active incident in tests: `AppState.set_active_incident("TEST-123")`
- Add or update tests with each code change

---

## Encoding Hygiene

- All repo text files: UTF-8 (no BOM), LF line endings
- Avoid pasting from Word/PDF — paste as plain text, replace curly quotes/dashes
- Audit: `python scripts/encoding_audit.py --summary`
- CI gate: `python scripts/encoding_audit.py --fail-on-find`
- Pre-commit: `pipx install pre-commit && pre-commit install`; run with `pre-commit run --all-files`
- Windows console: `chcp 65001` before running tools

---

## Keeping These Docs in Sync
- **When you update this file, update `agents.md` to match.** Both files must stay in sync — they serve different consumers (Claude Code sessions vs. AI agents) but must reflect the same ground truth.
- The same applies in reverse: changes to `agents.md` should be reflected here.

## Definition of Done

- Code matches patterns above
- Tests updated and passing
- New assets registered in `tool.pyside6-project.files`
- Docs updated if workflows change
- No new `backend/` directories, QML files, or hardcoded Mongo URIs

---

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

---

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
