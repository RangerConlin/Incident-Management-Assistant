# Quick Start

Launch the app locally for manual testing and verification.

## Usage

```
/quick-start
/quick-start --no-db         # Skip DB connection (offline mode)
/quick-start --profile=test  # Use test incident data
/quick-start --debug         # Show Qt debug output
```

## What It Does

1. **Environment Check** — Verifies Python, MongoDB, Qt are ready
2. **Database Connect** — Connects to MongoDB (or uses offline mode)
3. **Load Test Data** — Populates with sample incidents if `--profile=test`
4. **Launch App** — Starts `python main.py` with desktop window
5. **Monitor** — Watches for errors, exits gracefully

## Output

- ✅ App window opens
- 📋 Console logs for debugging
- 🔴 Errors printed immediately
- 🛑 Graceful shutdown on Ctrl+C

## Common Startup Issues

| Error | Solution |
|-------|----------|
| "No MongoDB connection" | Run `/setup-dev` or use `--no-db` |
| "Qt display error" | Not a problem in CI; OK to ignore locally |
| "Module not found" | Check Python path, run `/setup-dev` |
| "Port 5000 in use" | Change via `--port=5001` |

## Features to Test

After launch, manually verify:
- ✅ Login page works
- ✅ Dashboard loads
- ✅ Create new incident
- ✅ Edit team status
- ✅ Export ICS214
- ✅ Real-time updates (if applicable)

## Options

- `--no-db` — Offline mode (no MongoDB)
- `--profile=test` — Load sample data
- `--debug` — Verbose Qt logging
- `--port=5001` — Custom API port

## Next Steps

- Test the feature you just built
- Check console for warnings/errors
- Use `/run-tests` after manual verification
- Validate code with `/check-architecture`

## Shutdown

Press `Ctrl+C` in terminal or close the window.
