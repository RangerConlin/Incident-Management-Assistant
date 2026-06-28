# Setup Dev Environment

Initialize a local development environment for the Incident Management Assistant.

## Usage

```
/setup-dev
/setup-dev --skip-mongodb   # Skip MongoDB setup (already running)
/setup-dev --skip-python    # Skip Python deps (already installed)
```

## What It Does

1. **Python Dependencies** — Install/upgrade packages from requirements
2. **MongoDB** — Check/start local MongoDB instance (or show connection string)
3. **Environment Variables** — Set `SARAPP_MONGO_URI`, `QT_QPA_PLATFORM`, etc.
4. **Database Initialization** — Create collections and indexes
5. **Verify Setup** — Run basic connectivity checks

## Output

- ✅ Environment ready for `python main.py`
- 📋 Summary of configured paths and ports
- ⚠️ Any missing dependencies or config issues

## Next Steps

After setup:
```bash
python main.py                    # Start desktop app
pytest tests/ --cov              # Run test suite
bash scripts/validate-all.sh      # Validate code quality
```

## Troubleshooting

- **MongoDB won't start** — Check if port 27017 is in use
- **Module import errors** — Ensure virtualenv is activated
- **Qt warnings** — Set `QT_QPA_PLATFORM=offscreen` for headless
