# AGENTS

## Overview
- Incident-Management-Assistant is a desktop-first incident management suite built with **PySide6**.
- Python modules in `modules/` provide UI panels, FastAPI routers, and repository-based persistence.
- `main.py` boots the Qt app, builds the menu tree, and loads ADS docks/widgets.
- Domain data lives in `data/`. Active backend is **MongoDB** via the `sarapp_db` package in `data/db/sarapp_db/`.
- The shared FastAPI app lives in `data/db/sarapp_db/api/app.py` and is served by the LAN server, cloud server, and built-in offline server runtimes.
- Legacy SQLite files and repositories still exist for modules and utilities that have not fully cut over yet; if you encounter any of these, flag them for migration and deletion.
- Tests live in `tests/` and `modules/**/tests` using `pytest`.
- Master product roadmap: `Design Documents/designplan.md`.
- Use **"incident"** everywhere, never "mission".
- Do not create new git branches or forks without being instructed to.
- Do not start or restart the mobile emulator without specific instructions to

## Hard Rules
- No new QML files. Treat existing QML-facing bridges/docstrings as legacy compatibility unless explicitly asked to remove or migrate them.
- No `backend/` directory. Files belong under the existing root/module structure such as `modules/`, `lan_server/`, `cloud_server/`, `cloud_router/`, `server/`, or `data/` as appropriate.
- `cloud_server/` is the hosted VPS/container server. It runs the same shared `sarapp_db` FastAPI app as the LAN server, connects to its own MongoDB container, and exposes the app under the existing connect-code URL shape (`/r/<code>/...`) so clients do not distinguish LAN vs cloud. Keep incident/master router, schema, and database changes in `data/db/sarapp_db/`; `cloud_server/` only owns hosted packaging, connect-code path handling, and the per-server dashboard. `cloud_router/` is the separate reverse-tunnel proxy that `cloud_server/` and LAN servers each register with; it owns the public `/r/<code>/...` URL — do not merge its tunnel/proxy code with `cloud_server/`. Unlike `cloud_server/`, `cloud_router/` still has no incident/system data of its own, but (as of 2026-10) it does own an embedded, optional **central master-catalog database** (`sarapp_central_master`) under `cloud_router/master_db/`, reusing the same `data/db/sarapp_db/` master routers/schemas via `create_app(mode="master_only")` rather than duplicating them. This is the one authorized exception to "no database in cloud_router" — it holds only agency-wide catalog data (personnel/equipment/vehicles/templates/etc.), never incident or system data. See `Design Documents/Instructions/cloud_router_architecture.md`.
- Database framework belongs under `data/`, not `core/`.
- Never create demo/fake data unless instructed; only migrate or use data that already exists.
- Do not add backward-compatibility shims, alias fields, or legacy fallback reads/writes in production code. If a data shape change needs help, use a one-time conversion/migration script to rewrite existing data into the new canonical format, then keep the app code on the canonical shape only.
- Never wire MongoDB directly into the UI. Architecture is UI -> API server -> MongoDB.
- `SARAPP_MONGO_URI` is never hardcoded; read it from the environment only.
- All incident-database writes go through a `sarapp_db.mongo.repository.BaseRepository` subclass. Routers must never call `insert_one`/`update_one`/`delete_one` directly on a raw collection.
- All tables must support user-resizable columns and show a clear outer border around the selected row; follow `Design Documents/Instructions/tabledesign.md` when creating or modifying tables.
- User-facing timestamps must be human readable and must not display precision smaller than seconds; trim milliseconds, microseconds, and nanoseconds from UI text.
- Never hardcode colors (hex strings, `QColor(r, g, b[, a])`, etc.) in widget/panel code. Every color, including conditional/status row tints, badge chips, and legend swatches, must be defined in `styles/profiles/dark.py` and `styles/profiles/light.py` and consumed through an accessor in `styles/styles.py` (re-exported via `utils/styles.py`), following the existing `TEAM_STATUS`/`RESOURCE_STATUS`/`TASK_STATUS`/`INTEL_*` dict patterns. Widgets that recolor based on domain status must call `subscribe_theme` so they repaint on theme switch instead of only at construction time.

## Directory Orientation
- `bridge/`: QObject bridges. Keep slots/signals friendly for widget bindings.
- `modules/`: Functional areas. Follow the local structure already established in each module.
- `notifications/`, `panels/`, `ui/`, `ui_bootstrap/`: Shared widgets, dialogs, and bootstrap code.
- `styles/`, `utils/styles.py`: Shared palette and styling helpers.
- `utils/`: App state, logging, filesystem, theme, and incident context. Extend instead of duplicating.
- `data/db/sarapp_db/`: Installable MongoDB package with collection constants, indexes, database manager, and API routers.
- `data/db/sarapp_db/export_import/`: Universal incident export/import package format (zip of collections + GridFS attachments) used by the `incident_transfer` router to move a whole incident between servers as a file.
- `server/`: Built-in offline server runtime used by the desktop client.
- `lan_server/`: Standalone LAN server runtime and console tooling.
- `cloud_server/`: Hosted Docker/Traefik cloud server wrapper, per-server dashboard, and Mongo backup import/export tooling. Dials out to and registers with `cloud_router/`, the same way a LAN server does.
- `cloud_router/`: Reverse-tunnel proxy. Owns the public `/r/<CONNECT_CODE>/...` URL and forwards traffic to whichever LAN/cloud server has registered that connect code. No incident data, no shared files/imports with `cloud_server/`. Also optionally owns an embedded central master-catalog database (`cloud_router/master_db/`, see above) — the one exception to "no database."
- `web_client/`: React/Vite SPA, a full-CRUD browser clone of the desktop app built module by module (see `Design Documents/Instructions/product_structure.md` "Client Surfaces"). The one place in this repo with Node/JS tooling — has its own `AGENTS.md`, which also documents the pattern each new module follows. Talks to the same shared FastAPI app as every other client; no separate backend. Its build (`web_client/dist`) is served by `create_app()` at `/app` when present.

## Coding Defaults
- Target Python 3.11.
- Use PEP 8, type hints, dataclasses where they fit, logging, and repository/service boundaries.
- Prefer PySide6 widgets for UI work and open panels through established factories so ADS behavior stays consistent.
- UI code uses `utils/api_client.py`; do not add direct DB access to widgets or bridges.
- The shared FastAPI surface is `data/db/sarapp_db/api/app.py`; keep architecture notes and new server-facing work aligned with that entry point.
- When touching incident/master routers under `data/db/sarapp_db/api/routers/`, do not duplicate them under `cloud_server/`; the cloud server imports the shared app from `data/db/sarapp_db/api/app.py`.

## Testing Expectations
- Run or update relevant `pytest` coverage with each code change.
- Use `QT_QPA_PLATFORM=offscreen` for CI/headless Qt runs.
- Stub `CHECKIN_DATA_DIR` when tests need isolated data paths.
- If tests repeatedly fail with the same error that is related to the environment and not the code, stop running the tests and flag it.

## Instruction Index
- Backlog / queued follow-up work: `backlog.md`
- Legacy compatibility inventory: `Design Documents/legacycode.md`
- Table UI standards: `Design Documents/Instructions/tabledesign.md`
- Database architecture and incident context: `Design Documents/Instructions/database_architecture.md`
- API/router rules and mirroring requirements: `Design Documents/Instructions/api_router_rules.md`
- Mongo cutover status snapshots: `Design Documents/Instructions/mongo_cutover_status.md`
- IncidentCache/CatalogCache cutover status: `Design Documents/Instructions/cache_cutover_status.md`
- Mongo schema decisions: `Design Documents/Instructions/mongodb_schema_decisions.md`
- Desktop/UI patterns and runtime notes: `Design Documents/Instructions/ui_desktop_patterns.md`
- Python coding standards: `Design Documents/Instructions/python_coding_standards.md`
- Testing and environment setup: `Design Documents/Instructions/testing_and_qa.md`
- Text encoding hygiene: `Design Documents/Instructions/text_encoding_hygiene.md`
- Product structure, module inventory, and roadmap: `Design Documents/Instructions/product_structure.md`
- Planned real-time architecture: `Design Documents/Instructions/realtime_architecture_roadmap.md`
- Cloud server hosting architecture: `Design Documents/Instructions/cloud_router_architecture.md`
- VPS deployment packaging and Traefik (per-service Docker packaging, how this VPS's Traefik actually discovers containers, routing conventions): `Design Documents/Instructions/vps_deployment.md`
- Planned Events Toolkit Phase 0 audit (reuse matrix, domain boundaries, hardening backlog): `Design Documents/Instructions/planned_events_phase0_audit.md`

## Updating Instructions
- `AGENTS.md` is the repo-wide entry point. Keep it short, stable, and limited to universal rules plus pointers to focused instruction docs.
- `backlog.md` is the repo backlog/reference list for pending work. Consult it when orienting on open follow-ups, and update it when durable backlog items are added, completed, or materially re-scoped.  If you complete an item, remove it from the list, do not just make a comment.
- `Design Documents/legacycode.md` is the authoritative inventory for code kept only for legacy compatibility with outdated persisted data or migration gaps. Update it when such code is added, re-scoped, verified, or removed.
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
