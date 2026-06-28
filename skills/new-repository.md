# New Repository

Scaffold a new BaseRepository subclass for MongoDB data access.

## Usage

```
/new-repository Incident
/new-repository Team --collection=teams
/new-repository Task --with-indexes
```

## What It Creates

`data/db/sarapp_db/mongo/repositories/incident_repository.py`

```python
class IncidentRepository(BaseRepository):
    """Repository for incident data"""
    
    def __init__(self, db):
        super().__init__(db, collection_name="incidents")
    
    def find_active(self):
        """Find all active incidents"""
        return self.find({"status": "active"})
    
    def get_by_number(self, incident_number: str):
        """Get incident by number"""
        return self.find_one({"incident_number": incident_number})
```

## Options

- `--collection=name` — Custom collection name (default: lowercase plural)
- `--with-indexes` — Add common index patterns
- `--methods=find,create,update` — Specific methods only

## What It Includes

- ✅ Extends `BaseRepository` (enforces repository pattern)
- ✅ Type hints and docstrings
- ✅ CRUD methods (find, find_one, insert_one, etc.)
- ✅ Custom query methods for common patterns
- ✅ Index definitions (if `--with-indexes`)
- ✅ Test stubs with fixtures
- ✅ Logging for data access

## Common Methods Included

- `find(filter)` — Query documents
- `find_one(filter)` — Get single document
- `insert_one(doc)` — Create new
- `update_one(id, update)` — Update existing
- `delete_one(id)` — Delete
- `count(filter)` — Count matching

## Next Steps

1. Add domain-specific query methods
2. Define indexes for performance
3. Run `/run-tests` to verify
4. Wire into service layer

## Integration

Use in services via dependency injection:

```python
repo = IncidentRepository(db)
incident = repo.get_by_number("2025-001")
```

Never call MongoDB directly from UI — go through repository.
