# UI Desktop Patterns

## Runtime And Layout
- Run the desktop app with `QT_QPA_PLATFORM=xcb python main.py`.
- Use `QT_QPA_PLATFORM=offscreen` for CI or headless runs.
- Settings persist via `SettingsManager`.
- Docks/widgets register through `main.py`, `ui/docks.py`, `ui/widgets/`, module `windows.py` factories, and panel factory functions.
- ADS layout templates persist to `settings/ads_perspectives.ini`.
- Use `FORCE_DEFAULT_LAYOUT = True` in `main.py` only as a temporary troubleshooting toggle.

## UI Implementation Rules
- Prefer PySide6 widgets and repository/service boundaries.
- Open panels through module factories or `MainWindow._open_dock_widget()` so ADS behavior stays consistent.
- Reuse admin/catalog repositories for resource types, hazard types, team types, and task types when a module already integrates those lookups instead of duplicating local constants.
- Follow `Design Documents/Instructions/tabledesign.md` when creating or modifying tables.
