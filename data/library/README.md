# Incident Management Assistant

Incident Management Assistant ("SARApp") is a desktop-first toolkit for emergency operations centers. The application combines a PySide6 widget-based interface with an offline-friendly SQLite data layer so that planning, logistics, communications and public information teams can coordinate even when connectivity is limited.

## Key capabilities

- **Dockable PySide6 workspace.** `main.py` boots a Qt `QMainWindow` with Qt Advanced Docking System (ADS) so panels from each section (Command, Planning, Operations, Logistics, Communications, Intel, Medical/Safety, Public Information, Finance/Admin and Toolkits) can be opened, rearranged and saved as perspectives.
- **Offline-first data storage.** Utilities in `utils.db` and `utils.incident_context` manage a shared `data/master.db` file plus per-incident databases under `data/incidents/<id>.db`, with the `CHECKIN_DATA_DIR` environment variable allowing tests or deployments to override the storage root.
- **Incident operations workflows.** Command, Planning, Operations, Logistics, Communications, Safety, Medical, Liaison, Public Information and Finance/Admin modules now provide widget panels, repositories, and FastAPI routers for common ICS workflows.
- **Logistics resource lifecycle.** Logistics includes ICS-211 check-in/check-out, resource status boards, ICS-213RR requests, vehicle and aircraft inventory, fulfillment tracking and printable/exportable request artifacts.
- **Operations, tasking and team management.** Operations repositories normalize task and team data, derive status labels, link teams/resources to tasks, write audit activity, and back the dashboard/detail panels with reusable dataclasses and query helpers.
- **Forms, PDF generation and forms creator tools.** `modules/forms` provides schema-backed templates, binding providers, rendering helpers and export utilities for ICS forms with validation, PDF output and profile-aware form sets. `modules/forms_creator` supports template mapping and form set authoring.
- **Notifications and automation.** The notifier service persists mission notifications, emits toast/badge signals, and wires in a rules engine, scheduler and optional audible alerts for cross-module awareness.
- **Profile-driven customization and UI layout tools.** Profiles combine manifests, templates and computed bindings so deployments can tailor branding, catalogs and workflows without touching core code. UI customization modules manage layout templates, dashboard widgets, theme profiles and import/export bundles.
- **Specialized toolkits.** SAR, disaster response, planned event, initial response, projection dashboard, GIS/spatial services, weather and CAP ORM modules provide incident-type-specific tools that can be launched from the main menu.

## Repository layout

| Path | Purpose |
| --- | --- |
| `main.py` | Application entry point, menu wiring and dock manager bootstrap. |
| `modules/` | Feature modules covering ICS sections (operations, logistics, communications, public info, safety, medical, etc.). |
| `notifications/` | Toast, banner and scheduled alert services. |
| `profiles/` | Deployable configuration profiles with manifests, templates and assets. |
| `data/` | SQLite master/incident databases, templates, catalog exports and sample content. |
| `settings/` | Persisted settings and docking perspectives (`ads_perspectives.ini`). |
| `tests/` | Pytest suite for repositories, APIs, state helpers and accessibility checks. |
| `scripts/` | Utility scripts for inspecting/seedings databases and debugging audits. |
| `bridge/`, `models/`, `ui/`, `ui_bootstrap/`, `panels/` | Shared Qt bridges, table/query models, widget registries, settings pages and legacy/shared panels. |

## Getting started

### Prerequisites

- Python 3.11+ (PySide6 wheels are available for the supported interpreter versions).
- A virtual environment manager such as `venv` or `conda`.

### Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running the desktop app

```bash
python main.py
```

The first run creates `data/master.db` plus any incident databases referenced by utilities. Set `CHECKIN_DATA_DIR=/custom/path` before launching to store data outside the repository (useful for tests or production deployments).

Use `QT_QPA_PLATFORM=offscreen` when running Qt smoke tests in CI. On Linux desktops, use `QT_QPA_PLATFORM=xcb` if Qt needs an explicit platform plugin.

### Running FastAPI modules

Several modules expose FastAPI routers backed by the same data layer. Routers are intended to be included by an app or test harness, including `modules.forms.api`, `modules.finance.api`, `modules.logistics.api`, `modules.operations.taskings.api`, `modules.planning.api`, `modules.plannedtoolkit.api`, `modules.initialresponse.api`, `modules.ics214.api`, `modules.safety.api`, `modules.safety.orm.api`, and shared catalog routers under `data/db/sarapp_db/api`.

## Working with data

- **Master vs incident scope.** `utils.context.master_db()` returns the persistent staff/equipment catalog, while `utils.context.require_incident_db()` opens the active incident database (set via `AppState.set_active_incident`).
- **Active incident state.** `utils.state.AppState` is the UI/session source of truth. `AppState.set_active_incident()` synchronizes `utils.incident_context` and emits `app_signals.incidentChanged` for panels that need to refresh.
- **Seeding objective templates.** `data/db/seed_objective_templates.py` seeds canonical SAR incident objective templates into `sarapp_master`, and `scripts/inspect_db.py` prints a summary of an incident database schema.
- **Forms and templates.** Legacy templates live under `data/templates`, while profile-scoped templates live under `profiles/<id>/templates`. Use `modules/forms.FormRegistry` and `FormSession` for profile-aware export pipelines.
- **Encoding hygiene.** Text files should remain UTF-8 without BOM and LF line endings. Run `python scripts/encoding_audit.py --summary` when touching imported docs, templates or generated text.

## Developer workflow

1. Activate an incident for development with `AppState.set_active_incident("demo")` or via the UI. This ensures operations repositories, notifications and check-in services point at `data/incidents/demo.db`.
2. Seed or import sample data as needed (`data/examples`, module-specific seed scripts, or manual imports via SQLite tools).
3. Launch the Qt app (`python main.py`) to develop ADS dock panels, or run module entry points for FastAPI services and CLI utilities.
4. Persisted ADS layouts live in `settings/ads_perspectives.ini`; delete this file or temporarily set `FORCE_DEFAULT_LAYOUT = True` in `main.py` only when troubleshooting dock layout state.
5. Keep new UI work in PySide6 widgets. Legacy QML compatibility code still exists in a few bridge/model docstrings, but new QML should not be added.

## Testing

The repository uses `pytest` with lightweight fixtures that redirect database paths via `CHECKIN_DATA_DIR`. Run the full suite with:

```bash
pytest --import-mode=importlib
```

Targeted tests include check-in workflows, resource requests, catalog repositories, AppState signals, ICS-214, safety ORM, liaison, UI customization and module-level repository/API suites.

## Additional resources

- **Module READMEs.** Many feature areas include their own README (e.g., `modules/logistics/checkin/README.md`) that describe domain-specific workflows and APIs.
- **Design documents.** The `Design Documents/` directory contains the original scoping decks, wireframes and data dictionaries that informed the module layout.
- **Notifications UI.** Notification services expose toast history, rules management and scheduler controls for the widget-based desktop app.

Contributions are welcome—please open an issue describing proposed changes so the project maintainers can align implementation details with the broader incident management roadmap.
