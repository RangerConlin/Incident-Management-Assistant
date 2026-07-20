# Planned Events Toolkit — Phase 0 Audit

Status: Phase 0 complete (documentation only). No toolkit feature code was written in this
phase. This document is the audit report, reuse matrix, domain-boundary decisions, shared
service contracts, and hardening backlog required before Phase 1 implementation begins.

**Update 2026-07-18**: the program-wide notification engine identified as missing in §1.2
finding 3 has been built as a first Phase 1 slice, ahead of the rest of this document's
Phase 1 recommendation — see `data/db/sarapp_db/services/notification_service.py`,
`data/db/sarapp_db/services/trigger_engine.py`, `data/db/sarapp_db/api/routers/notifications.py`
(collection `IncidentCollections.NOTIFICATIONS`), and `lan_server/notification_trigger_loop.py`.
It evaluates Planned Events' existing `ScheduleTrigger` definitions (one-shot triggers only;
recurring remains deferred pending a shared recurrence utility) and emits through the new
shared store, with mobile push (`send_to_person`) as the first-class delivery path per the
2026-07-18 scoping decision in §1.6. `plannedtoolkit.py`'s own `PLANNED_NOTIFICATIONS`
CRUD/UI is untouched and still separate — migrating it onto the new shared engine remains a
fast-follow, not done in this slice.

Scope note: per explicit instruction, this phase produced documentation only. Deliverables
6 (backend tests) and 7 (thin vertical prototype) from the original Phase 0 brief are
deferred pending a separate go-ahead, and are stubbed out at the end of this document as
"Phase 0.5" so Phase 1 planning isn't blocked on them.

---

## 1. Audit Report

### 1.1 Systems inspected

- `modules/plannedtoolkit/` (records, repository, services, windows, schedule widget)
- `data/db/sarapp_db/api/routers/plannedtoolkit.py`
- `modules/planning/meetings/` (Meeting Planner — model, repository, services, panel)
- `data/db/sarapp_db/api/routers/meetings.py`
- `notifications/` (desktop Notifier, scheduler, rules engine, toast/panel UI)
- `data/db/sarapp_db/api/routers/audit.py`, `data/db/sarapp_db/mongo/audit.py`, `data/db/sarapp_db/schemas/audit_schema.py`
- `data/db/sarapp_db/api/routers/task_narratives.py` (Narrative — task-embedded)
- `modules/operations/taskings/` (Operations Tasking), `data/db/sarapp_db/api/routers/operations.py`
- `modules/operations/teams/` (Teams)
- `data/db/sarapp_db/api/routers/personnel.py` (master Personnel catalog)
- `data/db/sarapp_db/api/routers/checkin.py` (Check-In / roster)
- `modules/gis/services/spatial_link_service.py` (entity-linking pattern)
- `data/db/sarapp_db/api/routers/attachments.py` (canonical GridFS attachments)
- `modules/operations/taskings/attachments.py`, `modules/intel/services/intel_attachments.py` (formerly duplicate filesystem attachment stores; migrated onto the canonical GridFS API 2026-07-18)
- `modules/forms_creator/` (forms family/template/version framework)
- `data/db/sarapp_db/api/routers/ic_overview.py`, `data/db/sarapp_db/api/routers/operational_periods.py` (incident lifecycle)
- `data/db/sarapp_db/mongo/collection_names.py`, `data/db/sarapp_db/services/push.py`
- Design docs: `mongo_cutover_status.md`, `mongodb_schema_decisions.md`, `realtime_architecture_roadmap.md`, `incident_collection_inventory.md`, `master_collection_inventory.md`

### 1.2 Key findings

1. **The Planned Events Toolkit already exists** (`modules/plannedtoolkit/`) with a
   surprisingly complete data model — `PlannedRecord`, `ScheduledItem`, `ScheduleTrigger`,
   `PlannedNotification` — including promotion-to-tasking, recurrence fields, and
   audience/notification-channel fields. But the module still writes directly with raw
   pymongo (not `BaseRepository`), and **no code anywhere evaluates a trigger against wall
   clock and fires a notification.** The trigger/notification collections are pure CRUD
   scaffolding with no execution engine behind them.
2. **Quick Assignment → Operations Tasking promotion is already implemented** and mostly
   correct (`promote_quick_assignment` in `plannedtoolkit.py`): idempotent, stamps
   `linked_tasking_id`/`promoted_read_only`/`lifecycle_state`. Gaps: doesn't carry forward
   team/personnel assignment, and uses `source_type`/`source_id` while `create_task` uses a
   separate `origin_module`/`origin_id` convention for the same concept.
3. **There is no shared, persisted, multi-user notification system to reuse.** Three
   independent, non-integrated notification implementations exist: (a) an in-memory,
   per-workstation desktop `Notifier` that is lost on restart and has no API/persistence;
   (b) a dead `IncidentCollections.NOTIFICATIONS` collection that's declared and plumbed
   into the generic snapshot/WebSocket sync layer but has no schema, router, or writer;
   (c) the planned-toolkit's own bespoke `PLANNED_NOTIFICATIONS`/`PLANNED_SCHEDULE_TRIGGERS`
   collections, which duplicate what (b) was clearly meant to become. Push/mobile delivery
   (`send_to_person`) exists but has zero callers anywhere in the codebase.
4. **Meeting Planner is architecturally mature and should not be duplicated.** It uses
   `BaseRepository` correctly (unlike plannedtoolkit), has real service logic (template-driven
   meeting creation, bulk operational-period meeting sets, ICS-230 export, structured notes
   with narrative-log routing). It has no recurrence engine and is meeting-specific
   (agenda/attendees/checklist/notes) — a good complement to, not a replacement for, an
   Event Schedule.
5. **No shared scheduling/recurrence/date-time utility exists anywhere.** Plannedtoolkit uses
   free-text `recurrence_rule` strings; Meetings uses one-off "template set" bulk generation
   instead of recurrence. A third bespoke recurrence implementation must not be added.
6. **Audit logging exists and is solid but strictly manual** (`write_audit()` /
   `POST /api/audit`), never automatic via `BaseRepository`. Two slightly different audit
   record shapes already coexist in practice (`audit_schema.py`'s `AuditLogDocument` vs. the
   router's `AuditRequest`).
7. **Narrative is task-scoped only** — an embedded `narrative[]` array on `tasks` documents,
   not a standalone collection, with no incident- or operational-period-level narrative
   surface and no reusable "post to narrative" helper analogous to `write_audit()`.
8. **Operations Tasking, Teams, Personnel (master catalog with exact-fingerprint dedup), and
   Check-In (via `RESOURCE_STATUS`) are all mature and reusable.** There is, however, **no
   Registration system anywhere** — this is a genuine greenfield gap, not a hardening task.
   Team linkage on the check-in roster is string-based (`assigned_to`), not a real team FK
   (`fetch_roster` hardcodes `team_id: None`) — a hardening item if the toolkit needs to join
   registrations to teams reliably.
9. **Cross-module entity linking is fragmented into at least four incompatible patterns**
   (GIS spatial-link join table; `source_type`/`source_id`/`source_tool`; the competing
   `origin_module`/`origin_id`; typed embedded-array FKs on Safety hazards). No canonical
   entity-type registry or enum exists. The GIS spatial-link service and the Attachments
   `owner_type`/`owner_id` shape are the two most disciplined existing patterns and are the
   recommended templates — see §3.7.
10. **Attachments has one well-designed canonical service** (GridFS, `owner_type`/`owner_id`,
    `data/db/sarapp_db/api/routers/attachments.py`). At the time of this audit, two independent
    duplicate filesystem+JSON-manifest implementations also existed
    (`modules/operations/taskings/attachments.py`, `modules/intel/services/intel_attachments.py`);
    both were migrated onto the canonical GridFS service on 2026-07-18 and no longer touch the
    filesystem. The Planned Events Toolkit must use the canonical GridFS service, not create a
    duplicate.
11. **Forms framework (`modules/forms_creator/`) is directly reusable** for permits, waivers,
    and registration forms via a new form family/template — no new forms engine needed.
12. **Incident-level lifecycle status is weak**: a free string (`active|closed|archived`,
    loosely enforced, no validation, no close/reopen cascade). Operational period status
    (`Planned|Active|Complete|Canceled`, actually enum-validated with overlap checking) is
    the strongest existing lifecycle analog and the recommended model to imitate for a
    toolkit-level Planning/Execution/Wrap-Up phase.
13. **Confirmed: the toolkit's UI is live** in the running app today (stakeholder-confirmed
    2026-07-17) — Phase 1 builds on an active, navigable feature, not a dormant one.
14. **Resolved: the git-worktree `plannedtoolkit` code is stale, not a competing redesign.**
    `.claude/worktrees/agent-aee8e0eafc03d881d` and `agent-aff68ebd5edec480a` both check out
    an *earlier* version of `modules/plannedtoolkit` (`api.py`, `models/schemas.py`,
    `panels/*.py` as 10-line stubs, `scheduler.py`, `planned_models.py`) that `main` already
    replaced wholesale — confirmed via `git diff 4ffb4203 3421ea9c -- modules/plannedtoolkit`
    (~1,300 lines changed; `windows.py` grew from stub panels to 576 lines of real CRUD UI).
    No reconciliation needed. The two worktree directories separately contain a handful of
    unrelated uncommitted edits (forms/ICS-214 files) left over from prior sessions — harmless,
    clean up at your discretion with `git worktree remove` when convenient.
15. **Resolved: `INCIDENT_PERSONNEL` and `RESOURCE_STATUS` are not duplicates/ambiguous** —
    they serve distinct purposes and both are live, actively-used collections.
    `incident_personnel` is a per-incident **identity roster**, a synced-down copy of select
    fields (name, rank, callsign, role, phone, email, org, `is_medic`) from the master
    `PERSONNEL` record, keyed by `person_record` and refreshed via
    `sync_incident_personnel_from_master` (`data/db/sarapp_db/api/routers/operations.py`) and
    consumed elsewhere (e.g. comms-log contact suggestions in `communications.py`).
    `resource_status` is the separate **live check-in/status ledger** (`ci_status`,
    `checked_in_time`, location) for the same `person_record`. Registration's linkage chain in
    §3.6 is unaffected: resolve/create against master Personnel → syncs to `incident_personnel`
    (roster) → actual arrival creates a `resource_status` row (check-in).

### 1.3 Duplicated or conflicting capabilities

| Capability | Duplicates |
|---|---|
| Notification/trigger modeling | Desktop `Notifier` (in-memory) vs. dead `NOTIFICATIONS` collection vs. `PLANNED_NOTIFICATIONS`/`PLANNED_SCHEDULE_TRIGGERS` |
| Source/origin back-reference | `source_type/source_id/source_label` (plannedtoolkit, liaison reporting) vs. `origin_module/origin_id` (tasks, objectives) vs. typed FK lists (safety hazards) vs. GIS join-table triple |
| Attachment storage | Canonical GridFS `attachments` service vs. filesystem+manifest in taskings vs. filesystem+manifest in intel vs. separate `finance_attachments` collection |
| Recurrence representation | plannedtoolkit free-text `recurrence_rule` vs. Meetings' one-off template-set bulk generation |
| Scheduled/timed execution | `notifications/services/scheduler.py` (ephemeral `threading.Timer`, client-side) vs. nothing server-side for plannedtoolkit triggers |

### 1.4 Missing capabilities

- Server-authoritative, durable trigger-evaluation/execution engine (does not exist in any form).
- Shared, persisted, multi-user notification store with ack/dismiss/read state and offline/reconnect sync (the intended `IncidentCollections.NOTIFICATIONS` was never built out).
- Bridge from server-side notification creation to desktop toast delivery (WS broadcast exists generically via `BaseRepository`/`incident_stream.py`, but nothing consumes it into `Notifier.notify()`).
- Volunteer/staff Registration system (entirely greenfield).
- Canonical entity-type registry / relationship contract.
- Shared recurrence/date-time utility.
- Incident-level lifecycle close/reopen workflow with cascading side effects.

### 1.5 Risks

- Building further plannedtoolkit features on raw pymongo writes deepens the architectural gap with the rest of the codebase (which has migrated to `BaseRepository`).
- If Phase 1 wires desktop toast delivery directly into `plannedtoolkit.py` instead of a shared notification service, it cements a permanent fourth notification implementation.
- The unreconciled worktree redesign risks wasted work or merge conflicts if not addressed before Phase 1 begins.
- `INCIDENT_PERSONNEL` vs `RESOURCE_STATUS` ambiguity (declared collection with an unclear authoritative status) could mislead new registration/check-in linkage work if not resolved first.

### 1.6 Deferred questions (need a stakeholder decision, not just engineering)

Items 1 and 2 from the original list were resolved during stakeholder review on 2026-07-17
(see §1.2 findings 13–15) and are recorded there. Remaining open items:

1. **Notification store shape — decided 2026-07-18**: resurrect `IncidentCollections.NOTIFICATIONS`
   as a real, `BaseRepository`-backed shared collection, with its own router/service living
   outside `modules/plannedtoolkit`/`plannedtoolkit.py` (per the agents.md rule that shared
   infrastructure belongs with the subsystem that owns it, not with whichever module
   consumes it first). `PlannedNotification`'s existing field shape is the starting template.
   `PLANNED_NOTIFICATIONS`/`plannedtoolkit.py`'s notification CRUD is retired and migrated to
   call the new shared service instead of maintaining its own copy. Rejected alternative:
   promoting `PLANNED_NOTIFICATIONS` in place — rejected because (a) the collection name and
   its location under `plannedtoolkit.py` are permanently misleading once other modules
   (safety, logistics, comms) need to emit notifications too, and (b) it defers rather than
   avoids the eventual rename/migration.
   **Poll loop location — decided 2026-07-18**: the trigger-evaluation background job runs
   inside `lan_server/`. This covers LAN, offline (a spun-up LAN server instance), and
   cloud-connected incidents (a LAN server always runs locally and dials out to
   `cloud_server/`, which per the hard rule in agents.md has no Mongo connection and runs no
   `sarapp_db` routers, so it cannot host this job).
2. **Notification engine delivery-priority scope — decided 2026-07-18**: when the
   notification-engine rework is picked back up, build it **mobile-push-first**, with desktop
   toast/web delivery as a secondary consumer of the same emission point, not the other way
   around. Rationale: `send_to_person()` (FCM wrapper, `data/db/sarapp_db/services/push.py`)
   and the desktop `Notifier` both need a server-side emission point to exist at all — mobile
   is the one delivery channel that has no client-local fallback, so it's the forcing function
   for building the server engine in the first place. Concretely this means: the server engine
   should call `send_to_person()` as a first-class delivery path from day one (not bolted on
   later), while desktop-toast delivery (bridging WS-broadcast data into
   `notifications/services/notifier.py`) and any future web client can be wired in afterward
   against the same shared store/emission contract from §3.2/§4. This scoping decision does
   not un-defer item 1 above — the store shape still needs to be picked before implementation
   starts.

---

## 2. Reuse Matrix

| Planned-event requirement | Existing owner | Existing service/API | Reuse level | Gap | Recommended action |
|---|---|---|---|---|---|
| Event schedule items (milestones) | `modules/plannedtoolkit` (`ScheduledItem`) | `plannedtoolkit.py` `/planned/promotions/schedule` | Ready to reuse (model), needs hardening (router) | Raw pymongo writes, O(n) ID scan, minimal UI | Migrate router to `BaseRepository`; build out `ScheduleWidget` (date pickers, recurrence UI) |
| Schedule-linked trigger definitions | `modules/plannedtoolkit` (`ScheduleTrigger`) | `plannedtoolkit.py` `/planned-meta/schedule-triggers` | Reusable with major hardening | No execution engine evaluates triggers | Build server-authoritative trigger evaluator (new capability, not reuse) |
| Delivered notification storage/ack/dismiss | Nobody (canonical collection unimplemented) | `IncidentCollections.NOTIFICATIONS` (dead) vs. `PLANNED_NOTIFICATIONS` (toolkit-local) | Missing / duplicated | No shared notification store exists | Build the shared store (§3.2); toolkit becomes a producer via `source_type`/`source_id`, not its own store |
| Desktop toast delivery | `notifications/services/notifier.py` | In-memory `Notifier.notify()` | Reusable with hardening | Not connected to any server-persisted data | Add a WS-consumer bridge from shared notifications → `Notifier.notify()` |
| Push/mobile delivery | `data/db/sarapp_db/services/push.py` | `send_to_person()` | Reusable, currently unwired | Zero callers anywhere | Call from the trigger evaluator once notifications fire, if in scope |
| Meeting agenda/attendees/notes/action items | `modules/planning/meetings` | `meetings.py` router, `MeetingsService` | Ready to reuse | None significant | Event Schedule links to Meeting records by id; do not model agenda data in Event Schedule |
| Recurrence rules / reminders | Nobody (no shared utility) | — | Missing | Two bespoke recurrence reps already exist | Build one shared recurrence utility before Phase 1 schedule work, or explicitly scope down to plannedtoolkit's existing string rep and document it as the interim standard |
| Quick Assignment creation | `modules/plannedtoolkit` (`quick-assignments` tool) | `plannedtoolkit.py` generic `/planned/{tool}` routes | Ready to reuse | Minor: still raw writes | Migrate to `BaseRepository` |
| Quick Assignment → Tasking promotion | `plannedtoolkit.py` `promote_quick_assignment` | `/planned/quick-assignments/{id}/promote` | Ready to reuse, needs hardening | Doesn't carry team/personnel forward; inconsistent origin-field convention | Standardize on one origin-link convention (§3.7); carry forward assignment fields |
| Operations Tasking (post-promotion source of truth) | `modules/operations/taskings` | `operations.py` | Ready to reuse | None | No changes needed |
| Team lookup/assignment | `modules/operations/teams` | `operations.py` teams routes | Ready to reuse | None significant | No changes needed |
| Personnel lookup/dedup | Master catalog | `personnel.py`, `_duplicate_fingerprint` | Ready to reuse | Exact-match dedup only (no fuzzy match) | Acceptable for Phase 1; note as future enhancement |
| Check-in / expected-vs-arrived | `checkin.py` roster | `RESOURCE_STATUS` collection | Reusable with hardening | Roster's team link is string-based (`assigned_to`), `team_id` hardcoded `None`; no explicit "expected but not arrived" state distinct from a placeholder row | Add real `team_id` FK to roster rows; define registration's "pending" state explicitly (§3.6) |
| Volunteer/staff registration | Nobody | — | Missing (greenfield) | Entire capability | Build new, event-scoped, linking to Personnel/Check-In per §3.6 |
| Cross-module entity linking | Fragmented (4 patterns) | GIS `spatial_feature_link` closest to canonical | Reusable pattern, not a shared library | No entity-type registry | Adopt GIS-style link shape or attachments' `owner_type`/`owner_id` shape; do not invent a fifth (§3.7) |
| Attachments/documents | Canonical: `attachments.py` (GridFS) | `/incidents/{id}/attachments` | Ready to reuse | None for toolkit; do not touch filesystem duplicates | Use canonical service with `owner_type="planned_event"` |
| Forms (permits/waivers/registration forms) | `modules/forms_creator` | Family/template/version framework | Ready to reuse | None | Add a "Planned Events" or "Custom" family/templates |
| Audit history | `write_audit()` / `POST /api/audit` | `audit.py`, `mongo/audit.py` | Ready to reuse | Manual-only; two record shapes coexist | Toolkit routers call `write_audit()` explicitly on state changes |
| Narrative | Task-embedded only | `task_narratives.py` | Reusable pattern, not directly applicable | No incident/OP-level narrative surface exists | Toolkit needs its own decision: post significant events either to a linked task's narrative or skip Narrative integration in Phase 1 (see §3.9) |
| Incident lifecycle / phase | Weak (`status` string) | `ic_overview.py` | Not reusable as-is | No cascading close/reopen | Do not anchor toolkit phase to incident status; use OP-status pattern instead (§3.10) |
| Operational period linkage | `operational_periods.py` | Enum-validated `Planned/Active/Complete/Canceled` | Ready to reuse as a model to imitate | `period_summary()` cross-module counts are stubbed (returns zeros) | Toolkit schedule items may reference `operational_period_id`; don't rely on the stub for rollups |

---

## 3. Domain Boundary Document

### 3.1 Event Schedule vs. Meeting Planner

- **Meeting Planner** (`modules/planning/meetings`) owns: agenda, attendees, facilitator,
  meeting notes, decisions, action items, meeting documents, recurrence-as-template-sets,
  attendance. Keep as-is.
- **Event Schedule** (to be built out from plannedtoolkit's existing `ScheduledItem` /
  `ScheduleTrigger`) owns: activities, milestones, openings/closures, shift changes,
  inspections, performances, announcements, demobilization activities, planned/actual
  start/end times, operational owner, location, status, dependencies, readiness
  requirements, schedule-linked triggers, Quick Assignment triggers, delay/cancellation
  reason, authorization requirements.
- **Relationship**: a schedule item MAY carry a `meeting_id` reference to a Meeting Planner
  record (e.g., `Staff Briefing — 07:45` schedule item → linked Meeting record with agenda
  and notes). The schedule item does not duplicate agenda/attendee data.
- **Shared infrastructure both should use** (currently absent, see §1.2 finding 5): a single
  recurrence/reminder utility, timezone handling, conflict detection. Until built, Meetings'
  "template set" approach and plannedtoolkit's `recurrence_rule` string remain the two
  interim, non-unified mechanisms — Phase 1 should not add a third.

### 3.2 Trigger definitions vs. delivered notifications

- **Ownership decision**: The Planned Events Toolkit owns schedule-linked **trigger
  definitions** (`ScheduleTrigger` — already modeled). It does **not** own delivered
  notification storage. Delivered notifications belong to a shared, main-application
  notification subsystem.
- **Recommendation**: Rather than building an entirely new `IncidentCollections.NOTIFICATIONS`
  collection from a blank slate, generalize the toolkit's existing `PlannedNotification`
  shape (it already has `severity`, `audience_role`/`audience_user_id`, `source_type`/
  `source_id`/`source_label`, `acknowledged_at`/`dismissed_at`) into the shared collection,
  and repoint the desktop `Notifier` to consume it. This avoids a second migration later.
  This is a **deferred question for a stakeholder** (§1.6.3), not decided unilaterally here,
  since it affects the desktop `Notifier`'s data contract too.
- **Flow**: trigger fires (via the new execution engine, §3.4) → emits through the shared
  notification service → delivered notification persists with `source_type`/`source_id`
  pointing back to the schedule item / Quick Assignment / other source record → desktop
  toast and/or push delivery consume the shared store, not toolkit-local data.
- **Delivery priority (decided 2026-07-18, §1.6 item 2)**: build mobile push
  (`send_to_person`) as the first-class delivery path, since it's the one channel with no
  client-local fallback and is therefore the forcing function for the server engine existing
  at all. Desktop toast (bridge into `notifications/services/notifier.py`) and any future web
  client are secondary consumers wired against the same emission point afterward.

### 3.3 Registration vs. Personnel vs. Check-In

See §3.6 below (combined with the registration workstream for coherence).

### 3.4 Quick Assignments vs. Operations Tasking

- **Quick Assignments** (already implemented) remain lightweight, fast-create, sparse,
  assignable, schedulable, recurring, source-linked, and promotable.
- **Operations Tasking remains the source of truth after promotion.** The promotion endpoint
  (`promote_quick_assignment`) already enforces one-task-per-quick-assignment idempotency
  and read-only lock-down on the source record — this satisfies the "exactly one full task"
  and "idempotent" requirements from the original brief already. Remaining work is hardening
  (§4), not new design.

### 3.5 Audit history vs. Narrative

- **Audit-only** (via `write_audit()`): record created, status changed, assignment changed,
  trigger fired, notification acknowledged, schedule changed, registration matched, Quick
  Assignment promoted.
- **Narrative candidates** (require an explicit "Post to Narrative" action, not automatic):
  significant delay, safety issue, command decision, closure activated, activity started,
  contingency activated, major staffing problem. Because Narrative today is task-scoped only
  (embedded array on `tasks`), toolkit-originated narrative posts in Phase 1 should target a
  **linked task's** narrative where one exists (e.g., a promoted Quick Assignment's task) and
  should not attempt to invent an incident-level narrative surface — that is out of this
  toolkit's scope and would itself duplicate a system the rest of the app doesn't have yet.

### 3.6 Registration vs. Personnel vs. Check-In

- **Relationship**: `Registration -> Personnel -> Check-In -> Team Assignment`, exactly as
  specified in the original brief. This is a green-field build (§1.2 finding 8).
- Registration is event-specific, may exist without an immediate Personnel link, and owns:
  registration source, external registration ID, requested role, assigned event role, shift
  availability, expected arrival, confirmation status, waitlist status, event-specific notes,
  meal requirements, shirt size, waiver status, import batch, match status.
- Personnel (master catalog) remains the source of truth for the person — reuse
  `_duplicate_fingerprint()`/`_find_exact_duplicate()` for match/merge; do not overwrite
  verified Personnel fields from registration import data — write registration-only fields to
  the registration record, and only push a *new* Personnel record if no match is found.
- Check-In (`RESOURCE_STATUS`) remains the source of truth for actual arrival/departure. A
  registration in "expected, not yet arrived" state is a **distinct concept from a
  resource_status row** — do not pre-create a resource_status placeholder for every
  registrant; only create one on actual check-in. Expected-vs-arrived queries should join
  Registration (expected) against `RESOURCE_STATUS` (arrived) by resolved `person_record`,
  not rely on resource_status rows existing in advance.
- Teams remain the source of truth for operational assignment. Hardening required first: the
  check-in roster's `team_id` is currently hardcoded `None` (§4) — this must be fixed before
  registration→team-assignment queries can be reliable.

### 3.7 Toolkit phase vs. incident lifecycle

- Incident lifecycle (`active|closed|archived`) remains authoritative for the incident as a
  whole and is NOT to be replaced or shadowed.
- The toolkit's Planning/Execution/Wrap-Up presentation phase should be **modeled after the
  Operational Period status pattern** (`Planned|Active|Complete|Canceled` — an enum-validated
  string field, no cascading automation) rather than incident status. Recommend the toolkit
  phase be **manual** (user-set, like OP status), optionally cross-checked against the active
  operational period's dates, not computed from incident status. When an incident is closed
  or reopened, no automatic toolkit-phase transition should be assumed, since no such
  cascading mechanism exists anywhere else in the codebase to imitate — building one bespoke
  cascade solely for this toolkit is out of scope for Phase 1.

### 3.8 Attachments vs. feature-specific records

- All planned-event attachments (permits, vendor docs, insurance certs, briefing packets,
  registration spreadsheets, generated exports) go through the canonical GridFS service
  (`data/db/sarapp_db/api/routers/attachments.py`) with `owner_type="planned_event"` (or a
  more specific value per record type, e.g. `"planned_permit"`) and `owner_id` set to the
  owning record's compound id. Do not replicate the filesystem+manifest pattern used by
  taskings/intel — that pattern is documented tech debt, not a template (§4).

---

## 4. Shared Service Contract Document

These are the service interfaces Phase 1 needs from shared subsystems. Contracts marked
**(new)** don't exist yet and are Phase 1 build items, not integration points.

1. **Notification emission (new)** — `emit_notification(incident_id, title, message, severity, source_type, source_id, source_label, audience_role=None, audience_user_id=None, ...) -> notification_id`. Backing store TBD per §3.2 stakeholder decision; must ride the existing generic `incident_stream.py` snapshot/WS sync automatically once backed by an `IncidentCollections` entry.
2. **Notification acknowledgement (exists, toolkit-local today)** — `POST /planned-meta/notifications/{id}/acknowledge`, `/dismiss`. Contract should generalize unchanged if §3.2 promotes the toolkit shape to the shared store.
3. **Schedule trigger execution (new)** — a server-authoritative evaluator that reads `ScheduleTrigger` records, computes due occurrences (respecting `offset_minutes`/`relative_to`/`recurring`/`missed_occurrence_behavior`), and calls (1) above exactly once per occurrence, with a deterministic idempotency key (e.g. `f"{trigger_id}:{occurrence_start_iso}"`).
4. **Personnel lookup (exists)** — `GET /personnel/search`, `GET /personnel/{person_record}`; dedup via `_duplicate_fingerprint`/`_find_exact_duplicate` (exact-match only).
5. **Check-in status lookup (exists, needs hardening)** — `GET /roster` (filters: `q`, `ci_status`, `personnel_status`, `role`, `team`, `include_no_show`). Fix `team_id: None` hardcoding before Registration relies on it for team joins.
6. **Team lookup (exists)** — `GET /operations/teams`, `/operations/teams/search`.
7. **Quick Assignment promotion (exists)** — `POST /planned/quick-assignments/{id}/promote` → `linked_tasking_id`. Idempotent already. Needs: forwarding of team/personnel assignment fields; convention alignment (`source_type`/`source_id` vs `origin_module`/`origin_id`, recommend standardizing on `source_type`/`source_id` since it already carries a human-readable `source_label`).
8. **Entity linking (recommend adopting GIS pattern)** — a small join shape: `{module, record_type, record_id, relationship_type}`, modeled on `modules/gis/models/spatial_feature_link.py`. No canonical shared library exists to call into yet — Phase 1 either reuses the GIS module/service directly for non-GIS links (needs confirming it's not GIS-specific in practice) or replicates the shape as a toolkit-local join collection following the same field names, to keep future consolidation cheap.
9. **Attachment handling (exists)** — `POST/GET /incidents/{id}/attachments`, `.../download`, `DELETE .../{id}?purge_file=`. Use `owner_type`/`owner_id`.
10. **Audit logging (exists)** — `write_audit(incident_db, incident_id=, entity_type=, entity_id=, action=, changed_by=, field_changes=, source_module=)`. Call explicitly from every toolkit router mutation.
11. **Narrative posting (exists, task-scoped only)** — `POST /incidents/{id}/narratives` with `task_id`. Only usable where the toolkit record has a linked task (e.g. post-promotion).

---

## 5. Technical Debt and Hardening Backlog

| Finding | File(s) | Category |
|---|---|---|
| `plannedtoolkit.py` still uses raw pymongo writes and O(n) compound-ID scanning (`_next_compound_id`) instead of `BaseRepository` | `data/db/sarapp_db/api/routers/plannedtoolkit.py` | **Blocking Phase 1** — new toolkit writes should not extend a raw-write pattern the rest of the codebase has moved off of |
| No trigger evaluation/execution engine exists | (missing) | **Blocking Phase 1** for any "reminder actually fires" feature |
| No shared, persisted, multi-user notification store | `IncidentCollections.NOTIFICATIONS` (dead), `plannedtoolkit.py` | **Blocking Phase 1** for cross-workstation notification delivery |
| Desktop `Notifier` has no bridge from server-persisted/broadcast data | `notifications/services/notifier.py` | **Required during Phase 1** if toolkit notifications must produce toasts |
| Inconsistent origin-link convention (`source_type/source_id` vs `origin_module/origin_id`) | `plannedtoolkit.py`, `operations.py` (`create_task`), `objectives.py` | **Required during Phase 1** — pick one before Registration/Quick Assignment linking expands |
| Check-in roster hardcodes `team_id: None` | `data/db/sarapp_db/api/routers/checkin.py` (`fetch_roster`) | **Required during Phase 1** — blocks reliable Registration→Team joins |
| `ScheduleWidget` has no date pickers, recurrence UI, or trigger/notification UI | `modules/plannedtoolkit/widgets/schedule_widget.py` | **Important, non-blocking** for Phase 0→1 backend work; blocking for any user-facing schedule UI |
| No shared recurrence/date-time/reminder utility | (missing) | **Important, non-blocking** — can defer if Phase 1 scope stays server-side/backend |
| ~~Two duplicate filesystem+manifest attachment stores~~ — resolved 2026-07-18: both `modules/operations/taskings/attachments.py` and `modules/intel/services/intel_attachments.py` now call the canonical GridFS `attachments` API | `modules/operations/taskings/attachments.py`, `modules/intel/services/intel_attachments.py` | **Resolved** |
| `finance_attachments` is a separate collection from canonical `attachments` | `data/db/sarapp_db/api/routers/finance.py` | **Deferred** — out of toolkit scope |
| No canonical entity-type registry/enum across the codebase | multiple | **Important, non-blocking** for Phase 1 if toolkit scopes its own linking narrowly; blocking if Phase 1 wants a truly reusable cross-module contract |
| `send_to_person` (push) has no callers anywhere | `data/db/sarapp_db/services/push.py` | **Deferred** unless push is explicitly in Phase 1 scope |
| Incident-level `status` has no validation enum and no close/reopen cascade | `data/db/sarapp_db/schemas/incident_schema.py`, `ic_overview.py` | **Deferred** — toolkit should not depend on cascade behavior that doesn't exist |
| `operational_periods.py` `period_summary()` cross-module counts are stubbed (returns zeros) | `modules/planning/operational_periods/repository.py` | **Deferred** — don't build toolkit rollups on top of this stub |
| `INCIDENT_PERSONNEL` collection declared but apparently unused (check-in actually uses `RESOURCE_STATUS`) | `data/db/sarapp_db/mongo/collection_names.py` | **Deferred question** — confirm before Registration work assumes either is authoritative |
| Unreconciled experimental worktree redesign of plannedtoolkit | `.claude/worktrees/...` (not on active branch) | **Deferred question** — needs a decision before Phase 1, not engineering work in this phase |
| Toolkit's live menu/navigation reachability unconfirmed | `modules/plannedtoolkit/__init__.py` (no external callers found) | **Deferred question** — confirm before assuming Phase 1 builds on a live feature |
| Two audit record shapes coexist in practice (`audit_schema.py` vs. `audit.py` router's `AuditRequest`) | `data/db/sarapp_db/schemas/audit_schema.py`, `data/db/sarapp_db/api/routers/audit.py` | **Obsolete/candidate for retirement** — reconcile to one shape, not this toolkit's job to fix but worth flagging upstream |

---

## Phase 0.5 (deferred, not started)

The following deliverables from the original Phase 0 brief require writing code and were
explicitly deferred pending a separate go-ahead:

- **Backend tests** proving: a planned schedule trigger emits through the main notification
  system; one trigger occurrence creates no more than one delivered notification; a Quick
  Assignment promotes to exactly one Operations Tasking record (partially exists already —
  needs a test written against current `promote_quick_assignment` behavior); a registration
  can link to Personnel without overwriting the Personnel record; existing Check-In data can
  produce expected-vs-checked-in results; cross-module entity links resolve correctly; missed
  recurring occurrences follow configured behavior; trigger execution survives
  reconnect/sync without duplication.
- **Thin vertical prototype**: create schedule item → attach trigger → persist → execute via
  authoritative scheduler → emit through shared notification subsystem → persist delivered
  notification → link back to source → resolve from notification → sync without duplicates.

Both require the §3.2 stakeholder decision (shared notification store shape) and the trigger
execution engine (§4 item 3) to exist first, since they are prerequisites, not test targets.

---

## Summary for Phase 1 planning

**Confirmed reusable as-is**: Operations Tasking, Teams, Personnel (master catalog + dedup),
Check-In roster (with one fix needed), Meeting Planner, Forms framework, canonical
Attachments service (GridFS), Audit logging, Quick Assignment promotion (needs minor
hardening).

**Requires hardening before/during Phase 1**: `plannedtoolkit.py`'s raw-write pattern,
check-in roster team FK, origin-link convention consistency, ScheduleWidget UI.

**Missing and must be built in Phase 1**: trigger execution engine, shared notification
store (pending stakeholder decision on shape), Registration system, (optionally) a shared
recurrence utility and entity-type registry.

**Blockers to Phase 1** (need a decision, not just code): the four items in §1.6.

**Recommended Phase 1 scope**: (1) migrate `plannedtoolkit.py` to `BaseRepository`; (2)
resolve the shared-notification-store question and build the trigger execution engine against
it; (3) harden Quick Assignment promotion and check-in roster team FK; (4) build Registration
as a new toolkit-owned record type linking to existing Personnel/Check-In/Teams; (5) defer
recurrence-utility consolidation and cross-module entity-type registry unless Phase 1's
concrete features require them.
