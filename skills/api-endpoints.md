# API Endpoints

List and reference all FastAPI endpoints in the project.

## Usage

```
/api-endpoints
/api-endpoints --method=GET
/api-endpoints --module=operations
/api-endpoints --search=incident
```

## All Endpoints

**Incidents**
```
GET     /api/incidents              List all incidents
POST    /api/incidents              Create incident
GET     /api/incidents/{id}         Get incident by ID
PUT     /api/incidents/{id}         Update incident
DELETE  /api/incidents/{id}         Delete incident
GET     /api/incidents/{id}/teams   Get teams in incident
```

**Teams**
```
GET     /api/teams                  List all teams
POST    /api/teams                  Create team
GET     /api/teams/{id}             Get team by ID
PUT     /api/teams/{id}             Update team status
DELETE  /api/teams/{id}             Remove team
GET     /api/teams/{id}/roster      Get team members
```

**Tasks**
```
GET     /api/tasks                  List tasks
POST    /api/tasks                  Create task
GET     /api/tasks/{id}             Get task by ID
PUT     /api/tasks/{id}             Update task
DELETE  /api/tasks/{id}             Mark complete/delete
GET     /api/incidents/{id}/tasks   Get tasks for incident
```

**Operations**
```
GET     /api/operations/dashboard   Summary dashboard
POST    /api/operations/demobilize  Demobilize all teams
```

**Forms**
```
GET     /api/forms                  List available forms
POST    /api/forms/{type}/submit    Submit form (ICS214, etc.)
GET     /api/incidents/{id}/forms   Get forms for incident
```

**Communications**
```
GET     /api/comms/log              Get comms log
POST    /api/comms/log              Add comms entry
GET     /api/comms/log?incident={id} Filter by incident
```

**Equipment**
```
GET     /api/equipment              List equipment
POST    /api/equipment/{id}/assign  Assign to team
POST    /api/equipment/{id}/return  Return equipment
```

## Query Parameters

Most endpoints support filtering:
```
/api/incidents?status=active
/api/teams?incident=2025-FAIR
/api/tasks?assigned_to=user123
/api/comms/log?limit=50&offset=0
```

## Common Response Formats

**Success (200):**
```json
{
  "success": true,
  "data": { ... } or [ ... ]
}
```

**Error (400/500):**
```json
{
  "success": false,
  "error": "Description of error",
  "code": "ERROR_CODE"
}
```

## Headers

```
Content-Type: application/json
Authorization: Bearer {token}  (if auth required)
```

## Testing Endpoints

From CLI:
```bash
curl http://localhost:8000/api/incidents
curl -X POST http://localhost:8000/api/incidents \
  -H "Content-Type: application/json" \
  -d '{"name":"Test"}'
```

From UI:
```python
from utils.api_client import APIClient
client = APIClient()
incidents = client.get("/api/incidents")
```

## Options

- `--method=GET` — Filter by HTTP method
- `--module=operations` — Show endpoints for module
- `--search=demob` — Search endpoint names/descriptions
- `--usage` — Show example calls

## Related

- `/new-router` — Create new endpoint
- `/api_router_rules.md` — Design patterns for APIs
- `utils/api_client.py` — Python client implementation

## Server Info

```
Local:  http://localhost:8000
API:    http://localhost:8000/api/
Docs:   http://localhost:8000/docs  (Swagger UI)
```

## Documentation

See `Design Documents/Instructions/api_router_rules.md` for:
- Endpoint design patterns
- Error handling
