# Migration Checklist

Guide for migrating SQLite code to MongoDB patterns.

## Usage

```
/migration-checklist
/migration-checklist --module=operations
/migration-checklist --status
```

## Migration Steps

### 1. Assess Current Code
- ✅ Identify SQLite queries in module
- ✅ List affected tables/files
- ✅ Check if tests exist

### 2. Design MongoDB Schema
- ✅ See `/schema-lookup` for existing collections
- ✅ Map SQLite tables to MongoDB documents
- ✅ Define ObjectId, indexes, validation
- ✅ Document in `Design Documents/Instructions/mongodb_schema_decisions.md`

### 3. Create Repository
```bash
/new-repository ModuleName --collection=name --with-indexes
```
- ✅ Implement all query methods
- ✅ Add indexes for performance
- ✅ Test with `/run-tests`

### 4. Create/Update API Router
```bash
/new-router module_name --with-repository
```
- ✅ Wire repository into endpoints
- ✅ Add error handling
- ✅ Test endpoints

### 5. Update UI Code
- ✅ Replace direct DB access with API calls (`utils/api_client.py`)
- ✅ Update data binding/signals
- ✅ Test with `/quick-start`

### 6. Data Migration
- ✅ Write migration script (SQLite → MongoDB)
- ✅ Test migration with sample data
- ✅ Verify data integrity
- ✅ Plan rollback if needed

### 7. Testing
- ✅ Update unit tests for new repository
- ✅ Add integration tests for API
- ✅ Run `/run-tests --coverage`
- ✅ Manual testing with `/quick-start`

### 8. Cleanup
- ✅ Remove old SQLite code
- ✅ Run `/validate-repo` to catch violations
- ✅ Run `/check-architecture` for patterns
- ✅ Update documentation

## Common Patterns

**Old SQLite way:**
```python
conn = sqlite3.connect('data.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM incidents WHERE status=?", ('active',))
```

**New MongoDB way:**
```python
repo = IncidentRepository(db)
incidents = repo.find({"status": "active"})
```

**Old UI accessing DB directly:**
```python
cursor.execute("SELECT * FROM teams")
# Direct DB access in UI code ❌
```

**New UI using API:**
```python
from utils.api_client import APIClient
client = APIClient()
teams = client.get("/api/teams")
# Clean separation ✅
```

## Checklist Template

```
Module: operations
Status: In Progress

[ ] Assess SQLite queries (25 queries found)
[ ] Design MongoDB schema
[ ] Create IncidentRepository
[ ] Create API routers (/api/incidents)
[ ] Update UI panels (operations_dashboard.py, team_status.py)
[ ] Write migration script
[ ] Test with sample data
[ ] Run full test suite
[ ] Manual testing (quick-start)
[ ] Remove old SQLite code
[ ] Validate with check-architecture
[ ] Document in schema_decisions.md
[ ] Ready for production
```

## Related

- `/new-repository` — Create MongoDB repository
- `/new-router` — Create API endpoints
- `/schema-lookup` — View existing schemas
- `/run-tests` — Verify migration works

## Documentation

- `Design Documents/Instructions/mongodb_schema_decisions.md`
- `Design Documents/Instructions/mongo_cutover_status.md`
- `Design Documents/Instructions/database_architecture.md`
