# New Module

Create a new functional module with correct directory structure and patterns.

## Usage

```
/new-module logistics
/new-module operations --with-ui --with-api
/new-module reports --with-tests
```

## What It Creates

```
modules/mymodule/
├── __init__.py
├── services.py              # Business logic
├── repository.py            # Data access (if --with-api)
├── panels/
│   ├── __init__.py
│   └── dashboard.py         # UI component (if --with-ui)
├── widgets/
│   ├── __init__.py
│   └── table.py             # Reusable widgets
├── tests/
│   ├── __init__.py
│   ├── test_services.py     # Service tests (if --with-tests)
│   └── test_repository.py   # Repo tests (if --with-tests)
└── __init__.py
```

## Options

- `--with-ui` — Add panels/ and widgets/ directories
- `--with-api` — Add repository.py and API router template
- `--with-tests` — Scaffold test files

## What It Includes

- ✅ Correct imports and structure
- ✅ Type hints and docstrings
- ✅ Follows `agents.md` patterns
- ✅ Integration with shared styles
- ✅ Logging setup
- ✅ Test stubs with fixtures

## Next Steps

After creation:
1. Implement `services.py` business logic
2. Add `repository.py` if data access needed
3. Create UI in `panels/` if needed
4. Run `/run-tests` to verify structure

## Example

```
/new-module logistics --with-ui --with-api
# Creates modules/logistics/ with panels, services, and repo pattern
```
