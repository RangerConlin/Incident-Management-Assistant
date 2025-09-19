# AGENTS

## Incident-Management-Assistant Overview
- Desktop-first incident management suite built with **PySide6**.  
- Python modules in `modules/` provide UI panels, FastAPI routers, and SQLite persistence.  
- `main.py` boots the Qt app and loads docks/widgets.  
- Domain data lives in `data/`.  
- Tests live in `tests/` and `modules/**/tests` using `pytest`.  
- Master design document: **Design Documents/designplan.md**.  

## Directory Orientation
- `bridge/`: QObject bridges. Slot-friendly, emit signals on state changes.  
- `models/`: SQLite helpers and domain queries. Update `tool.pyside6-project.files` when adding.  
- `modules/`: Functional areas (operations, logistics, forms, comms, etc.). Include `data/`, `panels/`, `api.py` or `bridge.py`. Use dataclasses + repositories.  
- `notifications/`, `panels/`, `ui/`, `ui_bootstrap/`: Widgets, dialogs, bootstrap scripts.  
- `styles/`, `utils/styles.py`: Shared palette and helpers.  
- `utils/`: App state, logging, filesystem, theme, incident context. Extend, don’t duplicate.  
- `tests/`: Pytest suites for models, repositories, bridges. Module-level tests under `modules/**/tests`.  
- `Design Documents/`, `demos/`, `profiles/`, `notifications/assets/`: Reference and profile content.  

## Toolchain & Environment
1. **Python**: Target 3.11.  
   ```bash
   python3.11 -m venv .venv && source .venv/bin/activate
   ```  
2. **Dependencies**:  
   ```bash
   pip install -r requirements.txt
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
- Docks/widgets register through `ui/docks.py`, `ui/widgets/`, and module factories.  

## Data & Configuration
- SQLite files in `data/`. Use scripts for seeding or inspection.  
- `utils.incident_context` selects active incident DB.  
- Templates/forms in `data/forms`, `data/templates`, and `profiles/`.  
- Theme tokens in `utils.theme_manager` and `styles/palette.py`.  

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
- **FastAPI routers**: Place in `modules/<module>/api.py`. Test with FastAPI app inclusion.  

## Definition of Done
- Code matches patterns.  
- Tests updated and passing.  
- New assets registered.  
- Docs updated if workflows change.  

## Updating This Guide
- Applies to the full repo.  
- Add nested `AGENTS.md` for unique subtree rules.  
- Keep current with toolchain and repo structure.  
