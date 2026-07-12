# SARApp MongoDB Transition Guide

This document is the authoritative reference for coding agents performing the SQLite → MongoDB module cutover. Read it in full before touching any module.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [MongoDB Databases and Collections](#2-mongodb-databases-and-collections)
3. [Key Files and Where Things Live](#3-key-files-and-where-things-live)
4. [Hard Rules — Do Not Violate](#4-hard-rules--do-not-violate)
5. [The Cutover Process — Step by Step](#5-the-cutover-process--step-by-step)
6. [API Client Usage (Desktop Side)](#6-api-client-usage--desktop-side)
7. [FastAPI Router Patterns (Server Side)](#7-fastapi-router-patterns--server-side)
8. [MongoDB Document Patterns](#8-mongodb-document-patterns)
9. [Common Field Mapping Gotchas](#9-common-field-mapping-gotchas)
10. [Module Status](#10-module-status)
11. [Worked Examples](#11-worked-examples)

---

## 1. Architecture Overview

```
Desktop UI (PySide6)
    ↓
utils/api_client.py  (stdlib urllib, singleton)
    ↓  HTTP
SARApp Server (FastAPI / uvicorn)  ← one of three: lan_server/, cloud_server/, server/
    ↓
data/db/sarapp_db/   (shared Python package, PyMongo)
    ↓
MongoDB
```

All three server types (`lan_server/`, `cloud_server/`, built-in offline `server/`) import and serve the **same** FastAPI app from `data/db/sarapp_db/api/app.py`. Module routers are registered there.

The desktop UI never talks to MongoDB directly. Every DB read/write goes through the server via HTTP.

---

## 2. MongoDB Databases and Collections

Three logical databases:

| Database | Purpose |
|---|---|
| `sarapp_system` | Server/app config, active incident state |
| `sarapp_master` | Agency-wide reference data (personnel, equipment, radio channels, lookup tables) |
| `sarapp_incident_<id>` | One database per incident (e.g., `sarapp_incident_2025-FAIR`) |

Collection name constants live in `data/db/sarapp_db/mongo/collection_names.py`. **Always import from there — never write collection name strings inline.**

```python
from sarapp_db.mongo.collection_names import MasterCollections, IncidentCollections
col = get_master_db()[MasterCollections.TASK_TYPES]
col = get_incident_db("2025-FAIR")[IncidentCollections.TEAMS]
```

If you need a collection that doesn't have a constant yet, add one to the appropriate class in `collection_names.py`.

### Accessing databases

```python
from sarapp_db.mongo.database_manager import get_master_db, get_incident_db, get_system_db

master_db = get_master_db()
incident_db = get_incident_db("2025-FAIR")   # incident_id is the string identifier
system_db = get_system_db()
```

---

## 3. Key Files and Where Things Live

| File | Role |
|---|---|
| `data/db/sarapp_db/api/app.py` | FastAPI app factory — register new routers here |
| `data/db/sarapp_db/api/routers/` | One `.py` per domain (hazard_types, objectives, communications, …) |
| `data/db/sarapp_db/mongo/collection_names.py` | All collection name constants |
| `data/db/sarapp_db/mongo/database_manager.py` | `get_master_db()`, `get_incident_db(id)`, `get_system_db()` |
| `data/db/seed_master_from_sqlite.py` | Seeds `sarapp_master` from `data/master.db` |
| `data/db/seed_incidents_from_sqlite.py` | Seeds each `sarapp_incident_<id>` from SQLite incident DBs |
| `utils/api_client.py` | Desktop-side HTTP singleton (`api_client`) |
| `utils/state.py` | `AppState.get_active_incident()`, `AppState.get_active_user_id()` |
| `modules/<name>/` | Each UI module — repository files get Api* variants appended |

---

## 4. Hard Rules — Do Not Violate

- **No files under `backend/`** — that directory doesn't exist in this project.
- **No QML** — UI is PySide6 widgets, not QML.
- **Never use the word "Mission"** — use "incident" everywhere.
- **Never create demo or fake data** — only migrate what already exists in SQLite.
- **Never hardcode `SARAPP_MONGO_URI`** — it is always read from the environment variable. The `database_manager.py` handles this; don't duplicate it.
- **Don't delete SQLite databases** — they remain until every module is cut over. Old SQLite repositories stay in place; you append the new `Api*` class below them.
- **Database framework belongs under `data/`** — not `core/`, not `backend/`, nowhere else.
- **Don't add error handling for impossible cases** — trust internal API and framework guarantees. Only validate at system boundaries.
- **No comments explaining what the code does** — only add a comment when the WHY is non-obvious.

---

## 5. The Cutover Process — Step by Step

### Step 1 — Read the existing module

Before writing anything, read:
- The SQLite repository file(s) in `modules/<name>/` — understand every method's inputs, outputs, and SQL queries.
- The seeder functions in `data/db/seed_master_from_sqlite.py` or `data/db/seed_incidents_from_sqlite.py` to understand **what field names were stored in MongoDB**. These often differ from SQLite column names (see §9).
- `data/db/sarapp_db/mongo/collection_names.py` to know which collections already have constants.

### Step 2 — Add any missing collection constants

Open `data/db/sarapp_db/mongo/collection_names.py` and add constants to the appropriate class for any collections you'll use that aren't already there.

### Step 3 — Create the FastAPI router

Create `data/db/sarapp_db/api/routers/<module_name>.py`. Use PyMongo (not async Motor). Follow the patterns in §7.

**Critical route ordering:** FastAPI matches routes in registration order. Declare static-path routes BEFORE parameterized ones:

```python
# CORRECT — /validate is matched before /{row_id}
@router.get("/incidents/{incident_id}/things/validate")
def validate(...): ...

@router.get("/incidents/{incident_id}/things/{row_id}")
def get_one(...): ...
```

### Step 4 — Register the router in app.py

In `data/db/sarapp_db/api/app.py`, inside `create_app()`:

```python
from sarapp_db.api.routers import my_module
app.include_router(my_module.router, prefix="/api/my-module", tags=["my-module"])
```

If your router has routes under multiple prefixes (e.g., `/api/comms/master-channels` AND `/api/incidents/{id}/comms-log`), define two separate `APIRouter()` objects in the file and register each with its own prefix.

### Step 5 — Append Api* repository class

In the existing module repository file (e.g., `modules/command/models/objectives.py`), **append** the new `Api*` class below the existing SQLite class. Do not delete or rename the SQLite class — other modules or the seeder may still reference it.

```python
# --- existing SQLite class stays here ---
class ObjectiveRepository:
    ...

# --- new class appended below ---
class ApiObjectiveRepository:
    def __init__(self, incident_id: str):
        self._base = f"/api/incidents/{incident_id}/objectives"
    
    def list_objectives(self) -> list:
        from utils.api_client import api_client
        return api_client.get(self._base)
    ...
```

### Step 6 — Update the controller / service

In the controller or service that creates the repository, swap `FooRepository(...)` for `ApiFooRepository(...)`. Import from the same file as before — you just added the new class to it.

### Step 7 — Verify no SQLite calls remain

Grep the module files for `sqlite3`, `get_incident_conn`, `get_master_conn`, `incident_storage`, `db.get_*` — anything that touches SQLite directly. Any remaining references should be intentional (e.g., a deliberate deferral noted in §10) or need to be cut over.

---

## 6. API Client Usage — Desktop Side

The desktop-side singleton is `api_client` from `utils/api_client.py`.

**Always use deferred imports** — import inside the method body, not at module level:

```python
def list_things(self) -> list:
    from utils.api_client import api_client          # ← deferred, not at top of file
    return api_client.get("/api/things")
```

This avoids circular import issues and keeps modules loadable before the server is connected.

### Method signatures

```python
api_client.get(path, *, params=None)           # params: dict or None
api_client.post(path, *, json=None)
api_client.put(path, *, json=None)
api_client.patch(path, *, json=None, params=None)
api_client.delete(path, *, params=None)
```

All methods return the parsed JSON response (a `dict`, `list`, or `None`). They raise `APIError` (from `utils.api_client`) on any HTTP error or if the server is unreachable.

### Typical patterns

```python
# List with optional query params
results = api_client.get("/api/incidents/2025-FAIR/teams", params={"op_no": 3})

# Create (201)
created = api_client.post("/api/incidents/2025-FAIR/teams", json={"name": "Alpha"})

# Partial update
updated = api_client.patch(f"/api/incidents/2025-FAIR/teams/7", json={"status": "active"})

# Replace
api_client.put(f"/api/incidents/2025-FAIR/teams/7/requirements", json=[...])

# Delete (204 returns None)
api_client.delete(f"/api/incidents/2025-FAIR/teams/7")
```

### Getting the active incident

```python
from utils.state import AppState
incident_id = AppState.get_active_incident()   # returns str or None
user_id = AppState.get_active_user_id()        # returns str or None
```

---

## 7. FastAPI Router Patterns — Server Side

### Standard imports

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db

router = APIRouter()
```

### Timestamp helper

```python
def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
```

### Generating new `_id` values

All MongoDB documents use string UUID4 `_id` fields:

```python
import uuid
doc["_id"] = str(uuid.uuid4())
```

### Returning documents

Always project out `_id` when returning to the client:

```python
col.find(query, {"_id": 0})
col.find_one(filter, {"_id": 0})
```

Exception: if a router intentionally exposes MongoDB's UUID string as the
public record identifier, map it to the UI-facing `id` field. Existing
objectives still expose `_id` directly in places; treat that as transitional
compatibility, not the preferred pattern for new routers.

### Soft deletes

Most incident-scoped collections use a `deleted` boolean flag. Filter it out on reads:

```python
col.find({"incident_id": incident_id, "deleted": {"$ne": True}}, {"_id": 0})
```

On delete:
```python
col.update_one({"thing_id": thing_id}, {"$set": {"deleted": True, "updated_at": _utcnow()}})
```

### Request body — use Pydantic models or Body(...)

For structured creates/updates, define a Pydantic model:

```python
class CreateThingRequest(BaseModel):
    name: str
    description: Optional[str] = None
    priority: str = "Normal"

@router.post("/incidents/{incident_id}/things", status_code=201)
def create_thing(incident_id: str, body: CreateThingRequest):
    ...
```

For generic patch dicts (where any subset of fields may be sent):

```python
@router.patch("/incidents/{incident_id}/things/{thing_id}")
def update_thing(incident_id: str, thing_id: int, patch: Dict[str, Any] = Body(...)):
    ...
```

### 404 pattern

```python
doc = col.find_one({"thing_id": thing_id}, {"_id": 0})
if not doc:
    raise HTTPException(status_code=404, detail="Thing not found")
```

---

## 8. MongoDB Document Patterns

### Integer IDs

SQLite uses auto-increment integer PKs. MongoDB uses UUID4 `_id`. To preserve integer IDs for backward compat, two patterns are used:

**Pattern A — Compound string ID (incident-scoped collections)**

The seeder stores `thing_id = f"{incident_id}-THING-{sqlite_int}"` as a separate field. The integer is recoverable by parsing:

```python
def _thing_int_id(thing_id: str, incident_id: str) -> Optional[int]:
    marker = f"{incident_id}-THING-"
    if isinstance(thing_id, str) and thing_id.startswith(marker):
        try:
            return int(thing_id[len(marker):])
        except ValueError:
            pass
    return None
```

To generate the next ID for new documents:

```python
def _next_thing_id(col, incident_id: str) -> str:
    all_ids = [d.get("thing_id", "") for d in col.find({"incident_id": incident_id}, {"thing_id": 1})]
    max_n = 0
    marker = f"{incident_id}-THING-"
    for tid in all_ids:
        if isinstance(tid, str) and tid.startswith(marker):
            try:
                n = int(tid[len(marker):])
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"{marker}{max_n + 1}"
```

**Pattern B — `int_id` field (master collections)**

For master data (task_types, team_types, etc.), an `int_id` integer field sits alongside the UUID4 `_id`. Seeded docs may lack this field — use lazy migration:

```python
def _ensure_int_ids(col) -> None:
    """Lazily assign sequential int_ids to seeded docs that lack them."""
    missing = list(col.find({"int_id": {"$exists": False}}, {"_id": 1}))
    if not missing:
        return
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    next_id = (top["int_id"] + 1) if top else 1
    for doc in missing:
        col.update_one({"_id": doc["_id"]}, {"$set": {"int_id": next_id}})
        next_id += 1
```

Call `_ensure_int_ids(col)` at the start of list endpoints for these collections.

To get the next `int_id` for a new document:

```python
def _next_int_id(col) -> int:
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (top["int_id"] + 1) if top else 1
```

### Soft deletes vs hard deletes

- **Incident collections**: almost all use `"deleted": True/False`. Always filter `{"deleted": {"$ne": True}}` on reads.
- **Master lookup tables** (task_types, team_types, hazard_types, etc.): use `"is_active": False` for soft delete, no `deleted` flag.
- **Hard deletes**: only for user-owned transient data like filter presets.

### Embedded vs separate collections

- Task narrative, debrief, assignment info → **embedded** in the task document
- Meeting attendees and checklist → **embedded** in the meeting document  
- ICS 214 unit log entries → **embedded** in the unit_log document
- Org positions, assignments, history → **separate flat collections** (not embedded)

---

## 9. Common Field Mapping Gotchas

**The seeder field names are often different from SQLite column names.** Always check the seeder before writing router mapping code. The source of truth is:

- `data/db/seed_master_from_sqlite.py` — for `sarapp_master` collections
- `data/db/seed_incidents_from_sqlite.py` — for `sarapp_incident_<id>` collections

### Known mappings

| Collection | SQLite field | MongoDB field | Notes |
|---|---|---|---|
| `radio_channels` | `id` (int PK) | `channel_id` (string) | `str(sqlite_id)` |
| `radio_channels` | `alpha_tag` | `channel_name` | |
| `radio_channels` | `freq_rx` | `freq_rx` | same |
| `radio_channels` | `freq_tx` | `freq_tx` | same |
| `radio_channels` | `line_a` (int) | `line_a` (bool) | |
| `incident_channels` | `id` (int PK) | `channel_id` | compound: `{inc}-CH-{n}` |
| `incident_channels` | `master_id` (int) | `master_id` (string) | `str(int)` |
| `incident_channels` | `repeater` (int) | `repeater` (bool) | |
| `incident_channels` | `include_on_205` (int) | `include_on_205` (bool) | |
| `communications_log` | `id` (int PK) | `comms_id` | compound: `{inc}-COMMS-{n}` |
| `communications_log` | `team_id` (int) | `team_id` | compound: `{inc}-TEAM-{n}` |
| `communications_log` | `task_id` (int) | `task_id` | compound: `{inc}-TASK-{n}` |
| `communications_log` | `follow_up_required` (int) | `follow_up_required` (bool) | |
| `teams` | `id` (int PK) | `team_id` | compound: `{inc}-TEAM-{n}` |
| `tasks` | `id` (int PK) | `task_id` | compound: `{inc}-TASK-{n}` |
| `incident_profile` | `incident_number` | `incident_number` | same, but API renames `number` for UI |
| `incident_profile` | `incident_type` | `incident_type` | same, but API renames `type` for UI |
| `incident_profile` | `icp_address` | `icp_address` | same, but API renames `icp_location` for UI |

**When writing router mapping functions**, check what the UI/controller currently expects (the SQLite dict keys), then map from MongoDB field names to those keys. Do not expose MongoDB field names directly to the UI unless they already match.

### Boolean vs integer for flags

SQLite stores booleans as integers (0/1). MongoDB stores them as actual booleans. When the UI code does `int(row.get("repeater") or 0)`, returning a Python `bool` is fine (bools are ints). But be explicit in your mapping functions about what you return.

---

## 10. Module Status

### Completed ✅

**`modules/admin`**
- `ApiHazardTypeRepository` in `modules/admin/hazard_types/data/hazard_type_repository.py`
- `ApiResourceTypeRepository` in `modules/admin/resource_types/data/resource_type_repository.py`
- Routers: `hazard_types.py`, `resource_types.py`
- `ResourceAssignmentRepository` **deliberately left on SQLite** — bridges master+incident data; cut over with operations/logistics module.
- `resource_type_io.py` **deliberately left on SQLite** — CSV import/export utility, low priority.

**`modules/command`**
- IC overview router: `ic_overview.py` — `/api/incidents/{id}/`: profile (GET/PATCH), header (GET), op-periods (GET), teams (GET), tasks/summary (GET), channels (GET), logistics/counts (GET), alerts (GET)
- Objectives router: `objectives.py` — `/api/objectives` — basic objective CRUD/list/reorder/delete is migrated. Objective strategies, task links, and history are still pending and currently stubbed in `ApiObjectiveRepository`.
- Incident org router: `incident_org.py` — `/api/incidents/{id}/org/` — positions (CRUD), units, templates (list/by-name/apply/save), assignments (add/end/list), history, snapshots
- `modules/command/data_access.py` — fully rewritten to use API client
- `modules/command/data_access.py` still contains demo fallback payloads when API calls fail. These are development fallbacks and should be removed or replaced with explicit empty/error states before the command cutover is considered production-complete.
- `modules/command/panels/incident_overview.py` — uses API for load/save; `_get_incident_types()` still reads from SQLite (dropdown lookup, deliberate deferral)
- `ApiIncidentOrganizationRepository` in `modules/command/incident_organization/repository.py`
- `PersonnelPoolRepository` **deliberately left on SQLite** — cut over with personnel module.

**`modules/common`**
- Lookup types router: `lookup_types.py` — `/api/lookup/task-types` and `/api/lookup/team-types`
- `ApiTaskTypesRepository` and `ApiTeamTypesRepository` in `modules/common/models/lookup_models.py`
- `task_types_editor.py` and `team_types_editor.py` use API repos.

**`modules/communications`**
- Communications router: `communications.py` — two routers:
  - `master_router` at `/api/comms`: `/master-channels` (list, get)
  - `incident_router` at `/api`: `/incidents/{id}/channels-plan` (full CRUD + validate + preview), `/incidents/{id}/comms-log` (full CRUD + audit + contacts)
- `ApiMasterRepository` in `modules/communications/models/master_repo.py`
- `ApiIncidentRepository` in `modules/communications/models/incident_repo.py`
- `ApiCommsLogRepository` in `modules/communications/traffic_log/repository.py`
- `ICS205Controller` uses API repos; `CommsLogService` uses API repos.
- Guard this status with the API startup smoke test in `tests/test_api_app_startup.py`; communications imports depend on the module-level DB helpers in `sarapp_db.mongo.database_manager`.

**`modules/safety`**
- Safety router: `safety.py` — `/api/safety/reports`, `/api/safety/zones`, `/api/medical/incidents`, `/api/medical/triage`, `/api/safety/caporm`, `/api/safety/ics206/build`.
- CAP ORM router paths are also Mongo-backed under `/api/safety/orm`: form get/update, hazards list/create/update/delete, and approve with high-risk blocking.
- Collection constants live in `IncidentCollections`: `SAFETY_REPORTS`, `MEDICAL_INCIDENTS`, `TRIAGE_ENTRIES`, `HAZARD_ZONES`, `CAP_ORM_SUMMARIES`, `CAP_ORM_FORMS`, `CAP_ORM_HAZARDS`, `CAP_ORM_AUDIT`, and `ICS_206_BUILDS`.
- Legacy `modules/safety/services.py` and `modules/safety/orm/repository.py` remain in place for older direct imports and existing tests. Prefer the shared SARApp API router for new desktop/server workflows.

### Pending (alphabetical order)

- `modules/disasterresponse`
- `modules/finance`
- `modules/forms` / `forms_creator`
- `modules/ics214`
- `modules/initialresponse`
- `modules/intel`
- `modules/liaison`
- `modules/logistics`
- `modules/medical`
- `modules/operations`
- `modules/personnel`
- `modules/plannedtoolkit`
- `modules/planning`
- `modules/projection_dashboard`
- `modules/public_info` / `public_information`
- `modules/referencelibrary`
- `modules/sartoolkit`
- `modules/toolkits`
- `modules/ui_customization`
- `modules/devtools`
- `modules/gis`
- `modules/incidents`

### Deliberate SQLite deferrals (revisit when parent module is cut over)

| Repository | Location | Reason |
|---|---|---|
| `ResourceAssignmentRepository` | `modules/admin/resource_types/` | Bridges master + incident data; do with logistics/operations |
| `resource_type_io.py` | `modules/admin/resource_types/` | CSV import/export utility, low priority |
| `PersonnelPoolRepository` | `modules/command/incident_organization/` | Do with personnel module |
| `_get_incident_types()` | `modules/command/panels/incident_overview.py` | Dropdown lookup from master.db; low priority |
| Objective strategies/task links/history | `modules/command/models/objectives.py` | Basic objective CRUD is migrated; richer objective detail workflows still need Mongo endpoints |
| Command demo fallbacks | `modules/command/data_access.py` | Development fallback data; replace with explicit empty/error states before final cutover |

### Verification checks

- Run `pytest --import-mode=importlib tests/test_api_app_startup.py` after registering or editing routers.
- This smoke test should not require a running MongoDB server; it catches broken imports, missing collection constants, and router registration mistakes.

---

## 11. Worked Examples

### Example A — Simple master lookup (read-only)

**Router side:**

```python
@router.get("/task-types")
def list_task_types(include_inactive: bool = False):
    col = get_master_db()[MasterCollections.TASK_TYPES]
    _ensure_int_ids(col)
    query = {} if include_inactive else {"is_active": {"$ne": False}}
    docs = list(col.find(query, {"_id": 0}).sort("name", 1))
    return [_doc_to_row(d) for d in docs]

def _doc_to_row(doc):
    return {
        "id": doc.get("int_id"),
        "name": doc.get("name", ""),
        "is_active": 1 if doc.get("is_active", True) else 0,
        "updated_at": doc.get("updated_at", ""),
    }
```

**Client side (appended to existing repo file):**

```python
class ApiTaskTypesRepository:
    _endpoint = "/api/lookup/task-types"

    def list(self, include_inactive: bool = False) -> list:
        from utils.api_client import api_client
        params = {"include_inactive": "true"} if include_inactive else None
        return api_client.get(self._endpoint, params=params)
```

---

### Example B — Incident-scoped CRUD with compound ID

**Router side:**

```python
def _next_thing_id(col, incident_id: str) -> str:
    all_ids = [d.get("thing_id", "") for d in col.find({"incident_id": incident_id}, {"thing_id": 1})]
    max_n = max(
        (int(cid.split("-THING-")[-1]) for cid in all_ids
         if isinstance(cid, str) and f"{incident_id}-THING-" in cid),
        default=0
    )
    return f"{incident_id}-THING-{max_n + 1}"

def _map_thing(doc: dict) -> dict:
    thing_id = doc.get("thing_id", "")
    try:
        int_id = int(thing_id.split("-THING-")[-1])
    except (ValueError, IndexError):
        int_id = None
    return {
        "id": int_id,
        "thing_id": thing_id,
        "name": doc.get("name", ""),
        "status": doc.get("status", ""),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }

@router.get("/incidents/{incident_id}/things")
def list_things(incident_id: str):
    col = get_incident_db(incident_id)[IncidentCollections.THINGS]
    docs = list(col.find({"incident_id": incident_id, "deleted": {"$ne": True}}, {"_id": 0}))
    return [_map_thing(d) for d in docs]

@router.post("/incidents/{incident_id}/things", status_code=201)
def create_thing(incident_id: str, body: CreateThingRequest):
    col = get_incident_db(incident_id)[IncidentCollections.THINGS]
    now = _utcnow()
    thing_id = _next_thing_id(col, incident_id)
    doc = {
        "_id": str(uuid.uuid4()),
        "thing_id": thing_id,
        "incident_id": incident_id,
        "name": body.name,
        "status": body.status,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
    col.insert_one(doc)
    return _map_thing(col.find_one({"thing_id": thing_id}, {"_id": 0}))

@router.delete("/incidents/{incident_id}/things/{thing_id}", status_code=204)
def delete_thing(incident_id: str, thing_id: int):
    col = get_incident_db(incident_id)[IncidentCollections.THINGS]
    compound_id = f"{incident_id}-THING-{thing_id}"
    result = col.update_one({"thing_id": compound_id}, {"$set": {"deleted": True, "updated_at": _utcnow()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Thing not found")
```

**Client side:**

```python
class ApiThingRepository:
    def __init__(self, incident_id: str):
        self._base = f"/api/incidents/{incident_id}/things"

    def list_things(self) -> list:
        from utils.api_client import api_client
        return api_client.get(self._base)

    def create_thing(self, name: str, status: str = "active") -> dict:
        from utils.api_client import api_client
        return api_client.post(self._base, json={"name": name, "status": status})

    def delete_thing(self, thing_id: int) -> None:
        from utils.api_client import api_client
        api_client.delete(f"{self._base}/{thing_id}")
```

---

### Example C — Registering a router with two prefix groups

When a single module needs routes under both `/api/my-domain/` (master-level) and `/api/incidents/{id}/` (incident-level), define two `APIRouter()` objects and register both:

```python
# In the router file:
master_router = APIRouter()
incident_router = APIRouter()

@master_router.get("/channels")
def list_channels(): ...

@incident_router.get("/incidents/{incident_id}/channel-plan")
def list_plan(incident_id: str): ...
```

```python
# In app.py:
from sarapp_db.api.routers import my_module
app.include_router(my_module.master_router, prefix="/api/my-domain", tags=["my-domain"])
app.include_router(my_module.incident_router, prefix="/api", tags=["my-domain"])
```
