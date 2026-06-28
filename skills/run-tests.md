# Run Tests

Execute the pytest suite with correct environment setup.

## Usage

```
/run-tests
/run-tests --coverage        # Include coverage report
/run-tests --module=ui       # Run tests for specific module
/run-tests --watch           # Re-run on file changes
/run-tests --markers=slow    # Run only marked tests
```

## What It Does

1. **Environment Setup** — Sets `QT_QPA_PLATFORM=offscreen` for headless Qt
2. **Database Isolation** — Creates temp test database (doesn't touch dev DB)
3. **Runs Tests** — Executes pytest with proper config
4. **Reports Results** — Shows pass/fail, coverage, timing

## Output

- ✅ Test results summary
- 📊 Coverage report (if `--coverage`)
- 🔴 Failures with tracebacks (if any)
- ⏱️ Execution time per test

## Common Test Paths

```bash
/run-tests                    # All tests
/run-tests --module=modules/operations   # One module
pytest tests/test_auth.py     # Specific file
```

## Coverage Expectations

- Aim for 80%+ coverage on new code
- UI tests run headless (no display)
- Integration tests hit real test DB

## Troubleshooting

- **Qt errors** — `QT_QPA_PLATFORM=offscreen` should be auto-set
- **DB locked** — Kill leftover test processes: `pkill pytest`
- **Import errors** — Ensure repo root is in PYTHONPATH
