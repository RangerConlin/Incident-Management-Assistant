# New Router

Create a new API router with automatic cloud_server mirroring.

## Usage

```
/new-router incidents
/new-router teams --methods=get,post,put
/new-router reports --no-mirror
```

## What It Creates

**Primary Router** — `data/db/sarapp_db/api/routers/myrouter.py`

```python
@router.get("/api/myrouter")
async def get_all():
    """List all items"""
    
@router.post("/api/myrouter")
async def create(data: MySchema):
    """Create new item"""
```

**Mirror Router** — `cloud_server/sarapp_db/api/routers/myrouter.py` (auto-created)

## Options

- `--methods=get,post,put` — Specific HTTP methods (default: all CRUD)
- `--no-mirror` — Skip cloud_server mirror (not recommended)
- `--with-repository` — Auto-wire repository pattern

## What It Includes

- ✅ FastAPI router with correct structure
- ✅ Type hints and docstrings
- ✅ Error handling patterns
- ✅ Automatic cloud_server/ mirror
- ✅ Test stubs in `tests/routers/`
- ✅ Registered in `app.py`

## Default Methods

When no `--methods` specified:
- `GET /api/myrouter` — List all
- `POST /api/myrouter` — Create
- `GET /api/myrouter/{id}` — Get one
- `PUT /api/myrouter/{id}` — Update
- `DELETE /api/myrouter/{id}` — Delete

## Next Steps

1. Implement endpoint logic (replace `pass` placeholders)
2. Add repository binding if using `--with-repository`
3. Run `/run-tests` to verify
4. Validate with `/check-architecture`

## Mirroring

Both routers are kept in sync:
- Logic changes go in `data/db/` (single source)
- `cloud_server/` gets auto-generated mirror
- Use `/new-router --no-mirror` only if router is data-layer-only
