# AGENTS

## Overview
- Incident-Management-Assistant is a desktop-first incident management suite built with **PySide6**.
- Python modules in `modules/` provide UI panels, FastAPI routers, and repository-based persistence.
- `main.py` boots the Qt app, builds the menu tree, and loads ADS docks/widgets.
- Domain data lives in `data/`. Active backend is **MongoDB** via the `sarapp_db` package in `data/db/sarapp_db/`.
- The shared FastAPI app lives in `data/db/sarapp_db/api/app.py` and is served by the LAN server, cloud server, and built-in offline server runtimes.
- Legacy SQLite files and repositories still exist for modules and utilities that have not fully cut over yet; do not assume every remaining SQLite reference is dead code.
- Tests live in `tests/` and `modules/**/tests` using `pytest`.
- Master product roadmap: `Design Documents/designplan.md`.
- Use **"incident"** everywhere, never "mission".

## Hard Rules
- No new QML files. Treat existing QML-facing bridges/docstrings as legacy compatibility unless explicitly asked to remove or migrate them.
- No `backend/` directory. Files belong under the existing root/module structure such as `modules/`, `lan_server/`, `cloud_server/`, `server/`, or `data/` as appropriate.
- Database framework belongs under `data/`, not `core/`.
- Never create demo/fake data; only migrate or use data that already exists.
- Never wire MongoDB directly into the UI. Architecture is UI -> API server -> MongoDB.
- `SARAPP_MONGO_URI` is never hardcoded; read it from the environment only.
- All incident-database writes go through a `sarapp_db.mongo.repository.BaseRepository` subclass. Routers must never call `insert_one`/`update_one`/`delete_one` directly on a raw collection.
- All tables must support user-resizable columns and show a clear outer border around the selected row; follow `Design Documents/Instructions/tabledesign.md` when creating or modifying tables.

## Directory Orientation
- `bridge/`: QObject bridges. Keep slots/signals friendly for widget bindings.
- `modules/`: Functional areas. Follow the local structure already established in each module.
- `notifications/`, `panels/`, `ui/`, `ui_bootstrap/`: Shared widgets, dialogs, and bootstrap code.
- `styles/`, `utils/styles.py`: Shared palette and styling helpers.
- `utils/`: App state, logging, filesystem, theme, and incident context. Extend instead of duplicating.
- `data/db/sarapp_db/`: Installable MongoDB package with collection constants, indexes, database manager, and API routers.
- `server/`: Built-in offline server runtime used by the desktop client.
- `lan_server/`: Standalone LAN server runtime and console tooling.
- `cloud_server/`: Headless cloud/server deployment runtime with its mirrored `sarapp_db` package tree.

## Coding Defaults
- Target Python 3.11.
- Use PEP 8, type hints, dataclasses where they fit, logging, and repository/service boundaries.
- Prefer PySide6 widgets for UI work and open panels through established factories so ADS behavior stays consistent.
- UI code uses `utils/api_client.py`; do not add direct DB access to widgets or bridges.
- The shared FastAPI surface is `data/db/sarapp_db/api/app.py`; keep architecture notes and new server-facing work aligned with that entry point.
- When touching incident/master routers under `data/db/sarapp_db/api/routers/`, mirror equivalent changes under `cloud_server/sarapp_db/api/routers/`.

## Testing Expectations
- Run or update relevant `pytest` coverage with each code change.
- Use `QT_QPA_PLATFORM=offscreen` for CI/headless Qt runs.
- Stub `CHECKIN_DATA_DIR` when tests need isolated data paths.

## Instruction Index
- Backlog / queued follow-up work: `plan of action.md`
- Table UI standards: `Design Documents/Instructions/tabledesign.md`
- Database architecture and incident context: `Design Documents/Instructions/database_architecture.md`
- API/router rules and mirroring requirements: `Design Documents/Instructions/api_router_rules.md`
- Mongo cutover status snapshots: `Design Documents/Instructions/mongo_cutover_status.md`
- Mongo schema decisions: `Design Documents/Instructions/mongodb_schema_decisions.md`
- Desktop/UI patterns and runtime notes: `Design Documents/Instructions/ui_desktop_patterns.md`
- Python coding standards: `Design Documents/Instructions/python_coding_standards.md`
- Testing and environment setup: `Design Documents/Instructions/testing_and_qa.md`
- Text encoding hygiene: `Design Documents/Instructions/text_encoding_hygiene.md`
- Product structure, module inventory, and roadmap: `Design Documents/Instructions/product_structure.md`
- Planned real-time architecture: `Design Documents/Instructions/realtime_architecture_roadmap.md`

## Updating Instructions
- `AGENTS.md` is the repo-wide entry point. Keep it short, stable, and limited to universal rules plus pointers to focused instruction docs.
- `plan of action.md` is the repo backlog/reference list for pending work. Consult it when orienting on open follow-ups, and update it when durable backlog items are added, completed, or materially re-scoped.  If you complete an item, remove it from the list, do not just make a comment.
- When architecture, workflow, migration status, coding standards, or UI conventions change, update the relevant file under `Design Documents/Instructions/` in the same work when practical.
- If you add a new durable rule that future agents must follow, either add it to `AGENTS.md` if it is truly repo-wide and mandatory, or add it to the appropriate instruction doc and reference it here.
- Add nested `AGENTS.md` files only when a specific subtree needs extra local rules.
- `CLAUDE.md` is a thin pointer that imports this file; do not duplicate instruction content there.

## Definition Of Done
- Code matches repo patterns and relevant instruction docs.
- Tests are updated and passing, or any unrun coverage is called out.
- New assets are registered if required.
- Docs/instruction files are updated when workflows or architecture change.
- No new `backend/` directories, QML files, hardcoded Mongo URIs, or direct UI-to-Mongo wiring.
