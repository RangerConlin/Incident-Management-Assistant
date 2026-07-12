# New Router

Create a new API router under the shared FastAPI app.

## Usage

```
/new-router incidents
/new-router teams --methods=get,post,put
```

## What It Creates

**Router** — `data/db/sarapp_db/api/routers/myrouter.py`

```python
@router.get("/api/myrouter")
async def get_all():
    """List all items"""
    
@router.post("/api/myrouter")
async def create(data: MySchema):
    """Create new item"""
```

This is the only copy that needs to exist. `cloud_server/` is a stateless
reverse-tunnel router (see `Design Documents/Instructions/cloud_router_architecture.md`)
and never runs `sarapp_db` routers, so there is nothing to mirror.

## Options

- `--methods=get,post,put` — Specific HTTP methods (default: all CRUD)
- `--with-repository` — Auto-wire repository pattern

## What It Includes

- ✅ FastAPI router with correct structure
- ✅ Type hints and docstrings
- ✅ Error handling patterns
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
