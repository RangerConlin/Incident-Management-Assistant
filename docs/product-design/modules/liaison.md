# Liaison

## Purpose and users

Support Liaison Officers and command staff coordinating with external agencies. Keep agency
identity and contacts, incoming requests/offers, operational work links, and curated reporting
notes together within the selected incident.

## Web workflows

- `/liaison`: overview of agency count, open requests/offers, requests needing attention and
  reporting entries ready to share. Failed queries show unavailable metrics rather than zeros.
- Agency directory: create/edit agency identity, code, status, priority, assigned liaison,
  next-contact time and notes. Agency codes are required for request numbering. Agency detail
  reads contacts, interactions, recorded feedback/follow-ups, agreements/restrictions, and
  earlier request/offer records from the existing detail endpoint. Add contacts from the detail.
- Requests/offers: create, update and delete current `liaison_requests` records; link existing
  objectives, tasks and resource requests; create linked objectives/tasks; add narrative updates
  and feedback. Server-generated request codes use the agency code. If work creation succeeds
  but linking fails, the editor exposes the created work and retries linking without recreating it.
- Reporting board: create standalone or objective/task-sourced internal notes, curate a separate
  external summary, and mark it ready to report. Source notes remain read-only after creation.
  Readiness does not send a message or update the source objective/task.
- Interaction log: record agency contact and follow-up context. The existing API updates the
  agency's last-contact time when an interaction is created.

Boards use the shared resizable table with selected-row outlines. Search, agency/status/priority
filters and sorting live in the URL. Shared Liaison status tokens follow light/dark themes.
Queries poll every 20 seconds and use collection-aligned keys for incident WebSocket invalidation.
Edits PATCH only changed editable fields, preserving server timestamps and embedded narratives.

## Desktop and API boundaries

Desktop provides Agency Directory, Agency Requests and Reporting Board workflows, alongside
several older or scaffold panels. Web uses the same shared API and current request model.
Contacts and interactions have create/read endpoints only; agreements/restrictions and separate
follow-up records remain read-only. A unified Liaison activity log has no backing model.
Earlier request/offer/feedback records are shown separately on agency detail; they are not a
fallback data source for the current request board. Remaining CRUD, runtime ID migration and
parallel-model cleanup are recorded in `backlog.md` and the legacy inventory.

## Validation

Focused Node tests cover request attention/deadlines, reporting readiness, canonical work-link
IDs, safe PATCH payloads, combined URL filters, timestamp conversion, shared API paths, and
safe rendering of form text. Live-server browser acceptance remains a separate check.
