# MongoDB Schema Decisions

- `work_assignments` map to strategies, not tasks.
- Task narrative, debrief, `assignment_ground`, and `assignment_air` are embedded inside task documents.
- The `resources` collection maps to `logistics_resource_status_items`; it represents status snapshots rather than raw inventory.
- Use string UUID4 `_id` fields, Pydantic v2, and soft deletes.

## Finance
- File: `data/db/sarapp_db/api/routers/finance.py`
- All collections are incident-scoped. There is no master-level finance data.
- The old SQLite `vendors` master table had zero readers/writers and was dropped rather than migrated.
- `dashboard`, `fuel-report`, and `pending-approvals` are Python-side aggregation in the router rather than Mongo-side equivalents of the old SQL queries.
- `finance_approvals` is its own collection, not the generic `APPROVAL_INSTANCES` / `APPROVAL_RECORDS` system in `approvals.py`.
- `modules/finance/approvals.py` and `modules/finance/rates.py` were deleted during migration because they had zero callers and referenced tables that did not exist.
- Finance remains scaffold-heavy and UI-incomplete; the migration reflects the old SQLite schema and `services.py`, not a feature-complete redesign.

## Reference Library
- File: `data/db/sarapp_db/api/routers/reference_library.py`
- This router was already API-backed before the pass.
- Unused SQLAlchemy ORM models and an unused FTS5 search helper were removed because callers already used the router's Mongo `$regex` search.
- `models/reference_models.py` now only holds the still-used `Metadata` dataclass.
- The router now aliases `int_id` to `id` via `_finalize()` because callers expect `id`.
- The module currently has zero live UI consumers and is still heavily scaffolded.

## Safety Risk Manager — canonical Hazard Register
- File: `data/db/sarapp_db/api/routers/safety.py` (`HazardsRepository`, `list_hazards`/`create_hazard`/`get_hazard`/`update_hazard`/`delete_hazard`), collection `IncidentCollections.HAZARDS`.
- Replaces the CAP-style severity/likelihood risk matrix with USCG SPE (Severity x Probability x Exposure) scoring: `score = severity(1-5) * probability(1-5) * exposure(1-4)`, banded 1-19 Slight / 20-39 Possible / 40-59 Substantial / 60-79 High / 80-100 Very High, each with a fixed recommended action. Score/band/action are computed server-side on write and never trusted from client input.
- A hazard has `spe_initial` and `spe_residual`, each optional (residual is typically unset until controls are determined).
- `links` embeds `work_assignment_ids`/`team_ids`/`task_ids` (plain int lists) rather than being a separate join collection — hazards are incident-wide, not per-operational-period singleton forms like the old CAP ORM model.
- GAR (Supervision/Planning/Team/Environment/Complexity) scoring is intentionally out of scope here — it will live on the task/assignment side, not on individual hazards.
- No `status`/lifecycle field and no approval-blocking gate in v1 — this was a deliberate simplification versus the old CAP ORM form (which blocked approval on H/EH residual risk); see `Design Documents/legacycode.md` for what CAP ORM data paths remain for form-export compatibility.

## Forms
- File: `data/db/sarapp_db/api/routers/forms.py`
- The model is `family -> template -> version`.
- **Family** means issuing agency such as FEMA, CAP, SAR, ICS Canada, USCG, or Custom.
- **Template** means one form within that agency's set, such as FEMA's ICS 204.
- **Version** means a specific revision of that form's layout/fields over time.
- This mirrors the existing `forms/sets/<agency>/<code>/` directory layout.
- `modules/forms_creator/services/templates.py` (`FormService`) flattens this back into one dict per template for the rest of the module.
