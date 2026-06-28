# Schema Lookup

Quick reference for MongoDB collection schemas and field definitions.

## Usage

```
/schema-lookup incidents
/schema-lookup teams --fields
/schema-lookup --all
/schema-lookup --search=status
```

## What It Shows

For each collection:
- Field names and types
- Required vs. optional
- Example documents
- Indexes defined
- Validation rules

## Example Output

```
Collection: incidents

Fields:
  _id (ObjectId)              [required, auto]
  incident_number (string)    [required, indexed]
  name (string)               [required]
  status (enum)               [required] values: active, demobilized, closed
  incident_type (string)      [optional]
  coordinates (GeoJSON)       [optional]
  created_at (datetime)       [auto, indexed]
  modified_at (datetime)      [auto]

Indexes:
  incident_number (unique)
  created_at (descending)
  status

Example:
{
  "incident_number": "2025-FAIR",
  "name": "Fair County Fair",
  "status": "active",
  "created_at": "2025-06-28T..."
}

Related Collections:
  - teams (field: incident_id)
  - tasks (field: incident_id)
```

## Options

- `--fields` — Show detailed field docs
- `--indexes` — Show index definitions only
- `--example` — Show sample document
- `--search=keyword` — Find collections/fields matching keyword
- `--all` — List all collections

## Collections

```
incidents       Team assignments, incident metadata
teams           Team info, roster, status
tasks           Work items, assignments
communications  Logs, messages, notifications
ics214          Form data, completed forms
equipment       Equipment inventory, assignments
```

## Common Queries

Find an incident's teams:
```python
db['teams'].find({"incident_id": incident_id})
```

Get active tasks:
```python
db['tasks'].find({"incident_id": incident_id, "status": "in_progress"})
```

Update incident status:
```python
db['incidents'].update_one(
    {"incident_number": number},
    {"$set": {"status": "demobilized"}}
)
```

## Schema Changes

When modifying schemas:
1. See `Design Documents/Instructions/mongodb_schema_decisions.md`
2. Document the change
3. Update migration if needed
4. Test with `/run-tests`

## Related

- `/new-repository` — Create data access for schema
- `/migration-checklist` — Guide for schema migrations
