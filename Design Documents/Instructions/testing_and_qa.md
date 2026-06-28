# Testing And QA

## Environment
1. Target Python 3.11.
2. Typical setup:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e data/
```

3. Update both `requirements.txt` and `pyproject.toml` when dependencies change.
4. Maintain `tool.pyside6-project.files` when relevant.

## Qt System Libraries

```bash
sudo apt-get update
sudo apt-get install -y libgl1 libegl1 libxcb-xinerama0 libxkbcommon-x11-0
```

## Test Expectations
- Run tests with:

```bash
pytest --import-mode=importlib
```

- Run targeted suites by path when full coverage is unnecessary.
- Set `QT_QPA_PLATFORM=offscreen` in CI.
- Stub `CHECKIN_DATA_DIR` for temporary DB/data paths.
- Use smoke scripts in `scripts/` for audit-style checks when appropriate.
- Add or update tests with each code change.
