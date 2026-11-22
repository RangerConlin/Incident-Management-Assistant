# UI Desktop Patterns

## Runtime And Layout
- Run the desktop app with `QT_QPA_PLATFORM=xcb python apps/desktop/sarapp_desktop/main.py`.
- Use `QT_QPA_PLATFORM=offscreen` for CI or headless runs.
- Settings persist via `SettingsManager`.
- Docks/widgets register through `apps/desktop/sarapp_desktop/main.py`, `ui/widgets/`, module `windows.py` factories, and panel factory functions.
- ADS layout templates persist to `settings/ads_perspectives.ini`.
- Use `FORCE_DEFAULT_LAYOUT = True` in the desktop entry point only as a temporary troubleshooting toggle.

## UI Implementation Rules
- Prefer PySide6 widgets and repository/service boundaries.
- Open panels through module factories or `MainWindow._open_dock_widget()` so ADS behavior stays consistent.
- Reuse admin/catalog repositories for resource types, hazard types, team types, and task types when a module already integrates those lookups instead of duplicating local constants.
- Follow `docs/archive/design-documents/Instructions/tabledesign.md` when creating or modifying tables.

## Checklist widgets (Phase 4C)
- `apps/desktop/sarapp_desktop/modules/checklists/` is the reusable desktop frontend for the shared, program-wide Checklist backend (`server/sarapp_db/sarapp_db/api/routers/checklists.py` / `checklist_templates.py`, Phases 4A/4B). It is a sibling of `modules/plannedtoolkit/`, not nested inside it — the Planned Events Toolkit (`modules/plannedtoolkit/windows.py::get_checklists_panel`/`PlannedToolkitHome`'s "Checklists" tab) is only its first consumer. A future module embeds `widgets/checklist_execution_widget.py::ChecklistExecutionWidget` (and/or `widgets/checklists_tab.py::ChecklistsTab` for the full master/detail view) directly — construct with no args, then call `load_checklist(incident_id, checklist_id)`; it depends on nothing Planned-Events-specific.
- `api.py` is this module's `services.py`-equivalent service layer over `utils/api_client.py`, following `modules/plannedtoolkit/repository.py`'s layering. Every write passes `AppState.get_active_user_id()`/`get_active_api_session_id()` as `actor_id`/`session_id` body fields — there is no Authorization header anywhere in this desktop app, so this is how the server resolves "who did this" (same mechanism `approvals.py` already uses server-side).
- `async_call.py::BackgroundCall` is a minimal `QThread` wrapper used only by this module's widgets, for `api_client` calls that previously would have blocked the UI thread (every other desktop module calls `api_client` synchronously and accepts the blocking round trip — see that module's own docstring). Don't copy this pattern into other modules without reconsidering; it exists here because the Checklist execution widget saves a response on nearly every keystroke (debounced) and the product spec required the UI not to block on that.
- `styles_support.py::checklist_status_brush` wraps the new `utils.styles.checklist_status_colors()` accessor (profiles: `CHECKLIST_STATUS` in `styles/profiles/{light,dark}.py`, same `_build_status()` shape as `EVENT_SCHEDULE_STATUS`) — the status pill colors for Not Started/In Progress/Completed/Archived.
- Tests live under `modules/checklists/tests/`, following `modules/plannedtoolkit/widgets/tests/`'s convention (monkeypatch `modules.checklists.api` functions directly rather than mocking HTTP, `QApplication.instance() or QApplication([])` reused across tests). Two headless-testing gotchas worth remembering for this module: (1) `QMessageBox.warning/information/question` open a real modal event loop — monkeypatch them to no-ops (or a captured list) before any code path that might show one, or the test hangs forever with no one to click them; (2) a `QWidget` must never be constructed before a `QApplication` exists in the process — call `QApplication.instance() or QApplication([])` as the first line of every test, not after.
