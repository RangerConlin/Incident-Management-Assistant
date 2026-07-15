# MongoDB Schema Decisions

- `work_assignments` map to strategies, not tasks.
- Task narrative, debrief, `assignment_ground`, and `assignment_air` are embedded inside task documents.
- The `resources` collection maps to `logistics_resource_status_items`; it represents status snapshots rather than raw inventory.
- `resource_requests` is the canonical incident Logistics Resource Request / ICS-213RR collection. The duplicate `logistics_resource_requests` collection is retired; use `data/db/sarapp_db/migrations/migrate_logistics_resource_requests_to_resource_requests.py` for one-time data migration only.
- PIO message lifecycle approvals are embedded on each `pio_messages` document in `approvals`; the duplicate `pio_approvals` collection is retired.
- PIO misinformation timelines are embedded on each `pio_misinformation_items` document in `timeline`; the duplicate `pio_misinformation_timeline` collection is retired.
- `intel_env_snapshots`, `intel_form_entries`, and `intel_clues` are retired legacy Intel collections. Clues are canonical `intel_items` documents with `item_type="Clue"`.
- `ics_214_logs` is the canonical incident activity-log collection. A document is a stream, and entries are embedded in `entries`. The duplicate `unit_logs` collection is retired; SQLite `ics214_streams` imports seed `ics_214_logs`.
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
- Generated forms should not create durable in-app revision/export histories. If a generated PDF needs to be shared, upload it as an attachment and store the returned attachment id on the owning form, IAP package, task, or other domain document.

## Attachments
- File: `data/db/sarapp_db/api/routers/attachments.py`
- Incident-scoped document and media uploads use `IncidentCollections.ATTACHMENTS` for metadata and a per-incident Mongo GridFS bucket named `attachment_files` for bytes (`attachment_files.files` and `attachment_files.chunks`).
- Attachment metadata records include `attachment_id`, `owner_type`, `owner_id`, `category`, `filename`, `mime_type`, `size_bytes`, `checksum_sha256`, `gridfs_file_id`, `uploaded_by`, `uploaded_at`, optional `description`, and soft-delete fields.
- Domain documents should reference attachment ids rather than embedding file bytes or maintaining duplicate export/link collections.
- Deleting an attachment soft-deletes metadata by default; `purge_file=true` also removes the GridFS bytes.

## Push Notifications (FCM)
- File: `data/db/sarapp_db/api/routers/push_tokens.py`, collection `MasterCollections.PUSH_TOKENS` ("push_tokens") in `sarapp_master`.
- Master-scoped, not incident-scoped: a device's FCM token isn't tied to one incident, and field devices get shared across shifts (handoff tablets), so the collection tracks token -> current person, not token -> incident.
- Keyed and upserted by `token` (unique index), not by `person_record`. Re-registering an existing token — e.g. a different responder logging into a shared device — overwrites the existing document's `person_record`/`person_id`/`incident_id` in place rather than inserting a duplicate. This is the mechanism, not an incidental detail: it's what makes shared-device handoff work without manual cleanup.
- `person_record` is resolved server-side from `person_id`/`person_record` in the request the same way `auth_sessions._find_person` does, and is nullable — an unresolvable person (no matching `personnel` row) is tolerated, not rejected, matching how check-in already treats a missing `person_record` as non-fatal.
- Document shape: `{token, person_record, person_id, incident_id, platform, device_name, app_version, created_at, updated_at}`.
- `data/db/sarapp_db/services/push.py::send_to_person(person_record, title, body, data)` is the only sender — it looks up every token for a person and sends via `firebase_admin.messaging`, deleting any token that comes back `UnregisteredError`. It is infrastructure only; nothing calls it yet. Deciding which product events (task assignment, critical narrative, etc.) should trigger a push is a separate, later decision.
- `data/db/sarapp_db/services/firebase_client.py::get_firebase_app()` lazily initializes the Firebase Admin SDK from a service-account JSON path in `SARAPP_FIREBASE_CREDENTIALS_PATH` (never hardcoded, mirrors `mongo_client.py`'s env-var convention).

## Liaison — Reporting Board and origin back-links
- File: `data/db/sarapp_db/api/routers/liaison_reporting.py`, collection `IncidentCollections.LIAISON_REPORTING_DIGESTS` ("liaison_reporting_digests").
- The Liaison Officer (LOFR) role is controlling what information flows from incident staff to external customers, not raw CRUD on agencies. The Reporting Board is a one-way, LOFR-owned snapshot: `_pull_auto_summary()` reads the live `status`/`narrative` off an Objective (`IncidentCollections.INCIDENT_OBJECTIVES`) or the live `status`/latest embedded `narrative` entry off a Task (`IncidentCollections.TASKS`), seeds `lofr_summary` from it, and never writes back to the source. The LOFR edits `lofr_summary` and toggles `ready_to_report`; nothing else in the app reads or gates on this collection.
- Document shape: `{incident_id, int_id, source_type: "objective"|"task", source_id, source_title, auto_summary, lofr_summary, ready_to_report, last_synced_at, updated_by, updated_at}`. `int_id` is sequential per-incident like the rest of the Liaison collections (see `_next_int_id` in `liaison.py`).
- Objectives (`objectives.py`) and Tasks (`operations.py`'s task-create endpoint) both gained optional `origin_module`/`origin_id` fields so a customer request logged in Liaison can be converted directly into a real Objective or Task with a back-link to where it came from. This is the same directional-FK pattern Liaison Feedback already used (`objective_id`/`task_id`/`resource_request_id` on `FeedbackItem`), just reversed: the *new* Objective/Task points back at its Liaison origin instead of Liaison pointing at an existing Objective/Task.
- `liaison_agency_requests` gained `converted_to_type`/`converted_to_id` (set via `PATCH .../agency-requests/{id}/converted`) so the Customer Requests board can show a request has already been actioned and block converting it twice.
