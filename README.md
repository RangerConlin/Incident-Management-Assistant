# Incident Management Assistant

Incident Management Assistant ("SARApp") is a desktop-first toolkit for emergency operations centers. The application combines a PySide6/Qt Quick user interface with an offline-friendly SQLite data layer so that planning, logistics, communications and public information teams can coordinate even when connectivity is limited.

## Key capabilities

- **Dockable PySide6 workspace.** `main.py` boots a Qt `QMainWindow` with Qt Advanced Docking System (ADS) so panels from each section (Command, Planning, Operations, Logistics, Intel, etc.) can be opened, rearranged and saved as perspectives.
- **Offline-first data storage.** Utilities in `utils.db` and `utils.incident_context` manage a shared `data/master.db` file plus per-incident databases under `data/incidents/<id>.db`, with the `CHECKIN_DATA_DIR` environment variable allowing tests or deployments to override the storage root.
- **Logistics check-in workflows.** The logistics check-in module exposes repository and API helpers for copying master records into an active incident, running fuzzy searches and updating statuses so ICS-211 style intake can run offline.
- **Operations and team management.** Operations repositories normalize task and team data, derive status labels, and back the team dashboard and detail panels with reusable dataclasses and query helpers.
- **Forms & PDF generation.** `modules/forms` provides schema-backed templates, rendering helpers and export utilities for ICS forms (e.g., ICS-205) with validation and PDF output used throughout the planning toolchain.
- **Notifications and automation.** The notifier service persists mission notifications, emits toast/badge signals, and wires in a rules engine, scheduler and optional audible alerts for cross-module awareness.
- **Profile-driven customization.** Profiles combine manifests, templates and computed bindings so deployments can tailor branding, catalogs and workflows without touching core code; the profile manager handles discovery, inheritance and runtime switching.

## Repository layout

| Path | Purpose |
| --- | --- |
| `main.py` | Application entry point, menu wiring and dock manager bootstrap. |
| `main.qml` | Legacy Qt Quick prototype window kept for design reference. |
| `modules/` | Feature modules covering ICS sections (operations, logistics, communications, public info, safety, medical, etc.). |
| `notifications/` | Toast, banner and scheduled alert services plus QML panels. |
| `profiles/` | Deployable configuration profiles with manifests, templates and assets. |
| `data/` | SQLite master/incident databases, templates, catalog exports and sample content. |
| `settings/` | QML settings panels and persisted docking perspectives (`ads_perspectives.ini`). |
| `tests/` | Pytest suite for repositories, APIs, state helpers and accessibility checks. |
| `scripts/` | Utility scripts for inspecting/seedings databases and debugging audits. |

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

### Running a FastAPI module

Several modules (e.g., Public Information) expose REST APIs backed by the same data layer. Activate the virtual environment, ensure an incident database exists, then launch the module:

```bash
python -m modules.public_info.seed  # optional: loads sample content
uvicorn modules.public_info.api:app --reload
```

The API is mounted at `/api/public_info` and supports draft, approval and publishing flows for PIO teams.

## Working with data

- **Master vs incident scope.** `utils.context.master_db()` returns the persistent staff/equipment catalog, while `utils.context.require_incident_db()` opens the active incident database (set via `AppState.set_active_incident`).
- **Seeding objectives.** `scripts/seed_objectives.py` seeds example incident objectives if the table is empty, and `scripts/inspect_db.py` prints a summary of an incident database schema.
- **Forms and templates.** Legacy templates live under `data/templates`, while profile-scoped templates live under `profiles/<id>/templates`. Use `modules/forms.FormRegistry` and `FormSession` for profile-aware export pipelines.

## Developer workflow

1. Activate an incident for development with `AppState.set_active_incident("demo")` or via the UI. This ensures operations repositories, notifications and check-in services point at `data/incidents/demo.db`.
2. Seed or import sample data as needed (`data/examples`, module-specific seed scripts, or manual imports via SQLite tools).
3. Launch the Qt app (`python main.py`) to develop QDock-based panels, or run module entry points (for FastAPI services or CLI utilities).
4. Persisted ADS layouts live in `settings/ads_perspectives.ini`; delete this file or set `FORCE_DEFAULT_LAYOUT = True` in `main.py` for troubleshooting the dock layout.

## Testing

The repository uses `pytest` with lightweight fixtures that redirect database paths via `CHECKIN_DATA_DIR`. Run the full suite with:

```bash
pytest
```

Targeted tests include check-in workflows, catalog repositories, AppState signals and accessibility checks for UI components.

## Additional resources

- **Module READMEs.** Many feature areas include their own README (e.g., `modules/logistics/checkin/README.md`, `modules/public_info/README.md`) that describe domain-specific workflows and APIs.
- **Design documents.** The `Design Documents/` directory contains the original scoping decks, wireframes and data dictionaries that informed the module layout.
- **Notifications UI.** QML panels in `notifications/qml` surface toast history, rules management and scheduler controls powered by the notifier service.

Contributions are welcome—please open an issue describing proposed changes so the project maintainers can align implementation details with the broader incident management roadmap.
