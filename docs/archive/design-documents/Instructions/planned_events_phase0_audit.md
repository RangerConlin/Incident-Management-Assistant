# Planned Events Toolkit — Phase 0 Audit

**Phase 2D (Operations Tasking Integration and Promotion Reliability) — completed 2026-11-22.**
Hardens the existing `promote_quick_assignment` endpoint rather than redesigning it. Three real
gaps closed, each previously flagged in this document:
- **Origin-link convention fixed** (§1.2 finding 2, §5 hardening backlog): the formal task's
  back-reference to its source Quick Assignment now uses `origin_module`/`origin_id` —
  `operations.create_task`'s existing convention (already used by `objectives.py` and the
  desktop Tasking repository) — instead of the one-off `source_type`/`source_id`/`source_label`
  trio the old promotion code invented, which nothing else in Operations Tasking ever read.
  `operations.create_task` now only writes these two fields (plus a derived `origin_ref`) when a
  caller actually supplies both; previously it always wrote `origin_module`/`origin_id` as
  explicit `null` on every ordinary task, which would have defeated a sparse unique index.
- **Promotion is now exactly-once at the database level, not just via a look-before-create
  check** (the brief's own words: "a simple check... is not sufficient for concurrency safety").
  A new sparse unique index on `tasks.origin_ref` (`f"{origin_module}:{origin_id}"`,
  `mongo/indexes.py`'s `ensure_task_origin_ref_index`) means two requests racing to promote the
  same Quick Assignment can't both successfully insert a task — the loser's insert raises
  `DuplicateKeyError`, caught and resolved by re-fetching the winner's task
  (`plannedtoolkit._find_or_create_promoted_task`). The same lookup-by-`origin_ref` path also
  recovers a formal task that was created but never linked back onto the Quick Assignment
  (a crash between the two writes), so a retry after any partial failure converges on one task
  instead of creating a second one. **Found in passing**: nothing in the incident-creation path
  (`ic_overview.create_incident_records`) actually runs index bootstrap — `create_incident_indexes`
  is only ever called from the seed loader, the incident importer, and the verify script — so
  this promotion path calls the narrow `ensure_task_origin_ref_index` helper itself rather than
  assuming the index exists; the broader gap (every other collection's indexes, e.g. the teams
  `int_id` uniqueness) is unaffected and is flagged here, not fixed, since fixing it repo-wide is
  outside this phase's scope.
- **Team assignment now forwards to the formal task** (§2 reuse matrix row "Quick Assignment →
  Tasking promotion", §5 hardening backlog): `assigned_team_id` is attached via the existing
  `add_task_team` service, not duplicated logic. A lone `assigned_person_id` or a free-text
  assignee has no equivalent destination field — Operations Tasking only tracks personnel
  through a team's roster, never as a standalone task field — so both are intentionally left in
  place, unconverted and undiscarded, on the (now read-only) source Quick Assignment rather than
  invented as new Task fields.
- Desktop (`modules/plannedtoolkit/windows.py`): the promote action is relabeled "Promote to
  Operations Task" with an explicit confirmation dialog and the button disabled for the duration
  of the request; a promoted row now shows a "✓ Promoted" indicator alongside "Open Operations
  Task (<id>)". The Assignment detail dialog's read-only lock-down and read-only notice already
  existed from Phase 2A and needed no changes.
- Tests: `test_plannedtoolkit_promotion_phase2d.py` (team/personnel-field-mapping, the
  origin-link convention, partial-failure recovery, incident isolation, recurring/schedule-
  triggered occurrence independence, the database-level uniqueness guarantee itself, and that
  ordinary task creation is unaffected by the new index) plus updated assertions in
  `test_plannedtoolkit_assignments.py`/`test_plannedtoolkit_repository.py` (tasks live in a
  per-incident database and never carried an `incident_id` field on the document itself — a
  pre-existing fact the old hand-built promotion code's test queries happened to paper over by
  stamping that field manually; the new tests query within the correct per-incident database
  instead). Full existing Planned Events Toolkit + Operations Tasking suites re-verified
  alongside these (293 passed; 5 unrelated pre-existing environment failures — GridFS requiring
  a real `pymongo.Database` that `mongomock` can't provide, and one FastAPI-version route-
  introspection mismatch — neither touches tasks, plannedtoolkit, or indexes).
- Out of scope per the brief (not implemented): any change to Operations Tasking's own data
  model or UI beyond reusing `create_task`/`add_task_team` as they already exist; a second
  formal task model; a new promotion/mapping collection; mobile app changes.

**Phase 2A (Assignment Cleanup and Management) and Phase 2B (Event Schedule and Assignment
Integration) — both complete.** Phase 2A removed the obsolete planned-event `tasks`
tool/collection, made `quick-assignments` the single user-facing "Assignments" system with a
compact create/edit modal (`widgets/assignment_detail_dialog.py`) and a resource-or-free-text
assignee picker (`widgets/assignee_picker_dialog.py`), and closed a promotion race that could
create duplicate formal Operations tasks. Phase 2B added an optional many-assignments-to-one
link from a Quick Assignment back to an Event Schedule item: a new `schedule_item_id` field on
`PlannedRecord` (API: `PlannedRecordCreate.schedule_item_id`, the `update_record` allowlist, and
an optional `schedule_item_id` filter on `GET /planned/{tool}`), a "Related Schedule Activity"
searchable picker in the assignment modal, and a "Linked Assignments" group plus "Add
Assignment" action in the Event Schedule's `ActivityDetailDialog`
(`widgets/operational_timeline_widget.py`). This is distinct from, and does not touch, the
existing single `ScheduledItem.quick_assignment_id` link (one auto-creatable companion
assignment per activity, from Phase 1D).

Status: Phase 0 (documentation) and Phase 0.5 (backend tests + thin vertical prototype, see
below) are both complete as of 2026-11-21, except for the two Phase 0.5 tests that depend on
the Registration system, which doesn't exist yet and is correctly out of scope here. This
document is the audit report, reuse matrix, domain-boundary decisions, shared service
contracts, and hardening backlog required before Phase 1 implementation begins.

**Phase 1E (Execution Controls and Schedule Reliability) — completed 2026-11-21, and with it
Phase 1 as a whole.** Hardens Phase 1A–1D for real operational use: a tighter lifecycle, an
explicit correction path, optimistic concurrency, and a genuine (not assumed) fix to a
trigger-delivery race. Four real pre-existing/newly-introduced bugs were found and fixed in
the course of this hardening pass — see below; each was caught by a test written for the
requirement it violated, not found by inspection first.
- **Lifecycle tightened to the brief's exact matrix**: `Delayed -> Completed` is no longer a
  direct transition (resume first); `Resume` now targets `In Progress` if the activity had
  actually started before the delay, or back to `Scheduled` if it never did ("as appropriate",
  not an unconditional `In Progress` as Phase 1A/1B shipped it). `Delay` accepts an optional
  `revised_start_at`, which just reschedules `starts_at` through the existing field and its
  existing trigger-resync — no new "revised time" model.
- **New `/correct` endpoint** is the one sanctioned way to reopen a terminal (Completed/
  Cancelled) status or fix a wrong actual timestamp, bypassing the routine transition table on
  purpose. No role/permission system exists anywhere in this router to check "authorized"
  against, so "authorized correction" here means: a separate, deliberate action that requires
  a mandatory `reason`, audited as `schedule_item.corrected` — the same shape delay/cancel's
  existing reason requirements already established, not a new access-control system.
- **Optimistic concurrency via a `revision` integer**, not `updated_at`. `updated_at` was the
  first thing tried, since every document already has one — and was rejected once proven
  empirically unreliable: `BaseRepository` stamps it at one-second resolution, so two writes
  to the same record inside the same second (realistic for two operators, let alone two
  automated calls back to back) produce an identical value and a "stale update" silently
  passes. `revision` starts at 0 and is incremented by exactly 1 on every write to a schedule
  item (`update_schedule`, every event-day action, `/correct`); an optional `expected_revision`
  on any of those requests is compared against it, and a mismatch returns 409 with the
  server's current record so the client can reload — entirely opt-in, so a caller that never
  sends it keeps the prior last-write-wins behavior.
- **Trigger-delivery race fixed for real**: `trigger_engine.py`'s old docstring claimed "only
  one `lan_server` process runs per incident... a stronger distributed lock isn't needed" —
  false for any cloud-connected incident, where `lan_server` *and* `cloud_server` each run
  their own `NotificationTriggerLoop` (confirmed in the Phase 0.5 update note above). The old
  code queried due triggers, then separately wrote `fired_at` after emitting — two evaluators
  racing on the same trigger could each pass the query before either wrote the flag, and both
  would emit. Fixed with `_claim_trigger`: a single atomic `find_one_and_update` that sets
  `fired_at` only if unset, so at most one evaluator ever proceeds to emit; the other sees
  `None` and moves on. Emission happens only after a successful claim, so a crash between claim
  and emission costs a missed notification, never a duplicate — the brief's explicit
  requirement. A failed emission after a successful claim is recorded on the trigger
  (`fire_error`, new field) rather than retried, for the same reason.
- **Four bugs found and fixed while hardening**, each via a test that exercised the exact
  requirement it violated:
  1. The `updated_at`-resolution problem above (concurrency design, not shipped code — caught
     before the first commit of this phase by the test for "stale update rejected").
  2. The genuine trigger-delivery race above (`trigger_engine.py`, pre-existing since Phase 0.5).
  3. `ScheduleController.refresh()` wiped `_items` to `[]` on *any* fetch failure, including a
     transient disconnect — directly violating this phase's own "temporary connection failures
     do not destroy the displayed schedule" requirement. Now preserves the last known-good list
     and only reports the error.
  4. Eight call sites across `ActivityDetailDialog`/`ScheduleListWidget` called `self.accept()`
     (closing the dialog) *unconditionally* after a mutation, even when the controller method
     returned `False` for failure — silently discarding the user's attempted action with no
     way to retry. Every action now only closes its dialog on success.
  5. `OperationalTimelineWidget`'s NOW-marker row only ever wrote column 0 before `continue`-ing
     the render loop; a filter change that reused that row index for a different item in a
     prior render left that item's text sitting in columns 1+ of the marker row — invisible
     (the column span hides it) but still returned by a direct `table.item(row, col)` read.
     Fixed by blanking the marker row's other columns on every render.
- Tests: `test_plannedtoolkit_phase1e.py` (14, backend lifecycle/correction/concurrency),
  `test_trigger_engine_reliability.py` (5, backend — simulated racing evaluators, restart-
  between-claim-and-delivery, failure distinguishability), `test_schedule_controller_phase1e.py`
  (4, desktop — refresh resilience, conflict resync), `test_timeline_phase1e.py` (4, desktop —
  the marker-row regression, the Correct dialog), all passing alongside a full re-run of every
  earlier Planned Events Toolkit test (116 total across backend + desktop).
- Out of scope per the brief (not implemented): recurring generation, advanced dependencies,
  automated readiness gates, automatic assignment generation, Registration, Vendor/Permit
  management, calendar integration, a second notification or synchronization system, a
  separate scheduling database.

**Phase 1D (Event Schedule Integration) — completed 2026-11-21.** Connects schedule activities
to Meeting Planner, Personnel, Teams, GIS, and Quick Assignments — "the Event Schedule
coordinates existing records, it does not replace the systems that own them." No new backend
capability was built where one already existed; two real pre-existing bugs were found and
fixed in passing because the integration work depended on the broken code paths being correct:
`PersonnelPicker._on_completion_selected` read `result.get("id")`, but `/api/master/personnel`
normalizes every record's id onto `person_record` (see `personnel.py`'s `_normalize`) — there
is no `id` key, so every existing caller (including `facilities_manager_panel.py`, which
persists `manager_personnel_id` from this) has always gotten an empty id. And
`schedule_time_utils.to_qdatetime` called `QDateTime(year, month, day, hour, minute)` — a
5-argument form this PySide6 version doesn't have — so opening the activity editor for any item
with a start time already set would have crashed; fixed to build via `QDate`/`QTime` instead.
A second Phase 1A/1B bug surfaced by the same testing pass: the editor's End field, when a
loaded item had a start but no stored end, kept showing "now + 30 min" from before `_load()`
ran instead of being derived from the item's actual start.
- Backend (`plannedtoolkit.py`, purely additive, no renamed/removed fields): `gis_feature_id`
  and `quick_assignment_id` join `meeting_id` as single-value link fields on `ScheduledItem`
  (one field per link kind structurally prevents duplicate associations — no extra validation
  needed). A new `severity` field on `ScheduleTrigger` is threaded through to
  `notification_service.emit_notification` via `trigger_engine._fire_trigger` (closes a real
  gap: the existing severity support had never been wired up for schedule triggers). Relative
  reminders ("15 min before start") resolve to an absolute `trigger_at` at write time inside
  `create_schedule_trigger`/`update_schedule_trigger` — the trigger engine itself is untouched
  and still only ever reads absolute timestamps, so no second scheduler was built. Rescheduling
  an activity recomputes every not-yet-fired relative trigger's `trigger_at`; cancelling or
  deleting an activity disables (never deletes, never touches an already-`fired_at` trigger)
  its pending triggers. A new `POST .../schedule/{id}/create-quick-assignment` endpoint creates
  a Quick Assignment prefilled from the activity and sets both sides' link fields atomically;
  a second call is rejected (409) rather than creating a duplicate. Every mutation here already
  flowed through the existing generic `_audit` call Phase 1A/1B added, so meeting/GIS link
  changes and responsibility changes were already producing audit records for free; trigger
  create/update/cancel gained their own `_audit` calls in this phase.
- Desktop: `PersonnelPicker` (from `modules.logistics.facilities.widgets`) is reused as-is
  (after the id-field fix above) for the Personnel link; a new `TeamPicker`
  (`widgets/team_picker.py`) mirrors its shape for Teams, since no reusable Team picker existed
  anywhere in the app (checked first). `record_resolvers.py` is the one place that reads
  Meeting/GIS/Personnel/Team data for display — every call is wrapped to return `None` on a
  404/unreachable record rather than raising, so a deleted linked record degrades to "(not
  found)" with a working Unlink button instead of crashing the dialog. Meeting navigation
  reuses the Meeting Planner's own detail window via a new tiny public function,
  `modules.planning.meetings.panel.open_meeting_detail` (previously only reachable from inside
  that module's own list panel). Reminders get a dedicated `ReminderDialog`
  (absolute / "before start" / "at start" modes, severity, audience) that edits the *same*
  `ScheduleTrigger` record in place rather than ever creating a second one.
- **Documented gap, not built around**: there is no existing desktop entry point that opens the
  GIS module centered on a specific feature (checked before writing anything) — linking,
  display, and unlink all work for a GIS location, but there is no "Open" action for it, unlike
  Meeting. Building one would mean either a new map-opening mechanism (explicitly out of scope)
  or modifying the GIS module itself (not part of this phase's brief). Likewise, "Open" for a
  linked Quick Assignment opens the whole Quick Assignments panel (reusing
  `windows.get_tasking_panel` as a plain top-level window) rather than deep-linking to the one
  record, since no such deep-link exists either; this also means it can display awkwardly
  under a modal `ActivityDetailDialog` — a real, documented UX limitation, not a crash risk.
- Tests: `test_plannedtoolkit_schedule_integration.py` (9, backend — link round-trip, relative-
  reminder resolution, reschedule/cancel cascades distinguishing fired-vs-pending triggers,
  Quick-Assignment-from-activity with duplicate-link rejection, incident isolation, backward
  compatibility) and `test_schedule_integration_widgets.py` (12, desktop — picker loading,
  both bugs above pinned as regressions, resolved/missing-record display, unlink scoping,
  reminder delivery-state display, edit-blocked-once-fired, `ReminderDialog` mode mapping).
  All run for real under `QApplication`, same EGL-stub approach as Phase 1C.

**Phase 1C (Operational Timeline) — completed 2026-11-21.** A dedicated timeline view inside
the existing Event Schedule panel, reusing Phase 1A/1B's backend and service layer with zero
server-side changes. Rather than let the new Timeline view and the existing Activity List view
each fetch/filter/mutate independently (which would have been a second scheduling system in
practice even without a second collection), both now read from one new
`modules.plannedtoolkit.schedule_controller.ScheduleController` — a `QObject` that owns the
current item list, every mutation (`create`/`update`/`delete`/`start`/`resume`/`complete`/
`delay`/`cancel`, each a thin call into the same `services.py` wrappers Phase 1A/1B built), and
the live-update subscription. `ScheduleWidget` is now a container with two tabs ("Timeline",
"Activity List") sharing one controller instance; the former top-level `ScheduleWidget` table
logic moved into `ScheduleListWidget` unchanged in behavior.
- Live refresh reuses the existing mechanism end to end: `BaseRepository` already broadcasts
  every write on `planned_event_schedules` over the incident WebSocket regardless of client;
  the desktop WS client already routes that into `utils.incident_cache.incident_cache`:
  `ScheduleController` just subscribes to its `changed` signal and calls `refresh()` when the
  collection matches. No new WebSocket, no polling. (Caught and fixed in the same pass: the
  controller must be constructed with its owning widget as Qt parent, or it never gets torn
  down and keeps refreshing after its panel closes — a real lifecycle bug a test for "live
  update only fires for the right collection" surfaced immediately.)
- "Needs Attention" (overdue) is purely computed (`schedule_time_utils.is_overdue`) from planned
  timestamps + current status on every render — nothing is written back, and status never
  changes on a timer, per the brief's explicit requirement.
- Planned-vs-actual deltas ("Started 8 min late", "Finished 12 min early", "On schedule") are
  computed the same way (`planned_vs_actual_text`), never stored.
- `ActivityDetailDialog` (opened by selecting/double-clicking a row) reuses the Phase 1A/1B
  `ScheduleItemDialog` for Edit and the controller's action methods for Start/Resume/Complete/
  Delay/Cancel — no separate status-changing logic.
- Tests: `test_schedule_controller.py` (8 — refresh/empty/sorted, error handling, that every
  mutation delegates to `services.py` and not local logic, live-update collection filtering),
  `test_schedule_time_utils.py` (9 — parse/format/diff/overdue pure functions),
  `test_operational_timeline_widget.py` (9 — chronological ordering, status/date filtering,
  overdue flagging without a status change, selection, refresh reflecting backend changes,
  cancelled-item visibility, backward compatibility with a minimal legacy item). All 26 pass
  under a real `QApplication` (`QT_QPA_PLATFORM=offscreen`) — this container's usual missing-
  `libEGL.so.1` gap was worked around this time with a throwaway stub `.so` built from the
  undefined EGL symbols `libQt6Gui`/`libQt6Multimedia` actually need (never called by anything
  these tests exercise; present only to satisfy the dynamic linker), rather than skipping real
  widget tests again — not part of the repo, environment-local only.
- Out of scope per the brief (not implemented): calendar sync, recurring generation, automatic
  Quick Assignment creation, advanced dependencies, readiness gates, Vendor/Registration/Permit
  management, new notification infrastructure, a separate event database. None needed.

**Phase 1A/1B (Event Schedule) — completed 2026-11-21.** Built on the existing
`ScheduledItem`/`ScheduleTrigger` backend (§2 reuse matrix row 1) rather than a new
subsystem. Summary (file-level detail in each commit):
- `ScheduledItem` extended with `actual_start_at`/`actual_end_at`/`time_zone`,
  `assigned_to`/`assigned_team_id`/`assigned_person_id`, `meeting_id` (the one straightforward
  link to Meeting Planner this phase implements — Personnel/Teams links are the assignment
  fields; GIS and Quick Assignment links are deferred, see §3.1/§3.4), and
  `delay_reason`/`cancellation_reason`. No fields renamed or removed; a pre-Phase-1A record
  with none of these fields, or a legacy free-text `status`, still reads back unchanged
  (tested — see below).
- `status` is now a validated 5-value enum (`Scheduled`/`In Progress`/`Completed`/
  `Delayed`/`Cancelled`) with a server-enforced transition table, both via generic `PATCH`
  and five new dedicated action endpoints (`/start`, `/resume`, `/complete`, `/delay`,
  `/cancel`) mirroring the brief's five event-day actions 1:1. Nothing changes status on a
  timer — every transition is an explicit user action, per the brief's "do not automatically
  change status" requirement.
- Every schedule-item mutation now calls `sarapp_db.mongo.audit.write_audit` — the first
  caller of that function from any router (§1.2 finding 6 had flagged it as defined but never
  called automatically). `source_module="plannedtoolkit"`, `entity_type="planned_schedule_item"`.
- Desktop: `ScheduleWidget` rebuilt as a real operational view (chronological table, status
  color-coding via a new `EVENT_SCHEDULE_STATUS` palette entry in both theme profiles, date/
  status/type/responsible filters, an editor dialog with `QDateTimeEdit` controls, and the five
  event-day action buttons) rather than the previous bare add-row form. Also fixed a pre-existing
  bug where `schedule_from_dict` read `name`/`notes` keys the API never actually sent (it sends
  `title`/`summary` — see `_map_doc`), so activity names and notes were silently always blank on
  the desktop client before this phase.
- The Event Schedule is promoted to its own top-level tab/menu entry (`Tools → Planned Event
  Toolkit → Event Schedule`, `planned.schedule`) instead of being nested two levels deep under
  the unrelated "External Messaging" (Campaigns) panel, where it was easy to miss.
- Tests: `test_plannedtoolkit_event_schedule.py` (12 tests — creation/defaults, time-range and
  status-enum validation, edit-and-persist, full lifecycle with planned-vs-actual preservation,
  cancellation/delay reason requirements, 404s, incident isolation, backward compatibility with
  a pre-Phase-1A doc, audit records, and that existing schedule triggers still fire unaffected).
  All logic-verified against `mongomock` (no `mongod` in this container; same environment gap
  as Phase 0.5, not a reason to skip verification).
- Out of scope per the brief (not implemented): recurring schedule generation, dependencies,
  readiness gates, automatic Quick Assignment generation, conflict resolution, Registration,
  Vendor/Permit management, calendar integration.

**Update 2026-11-21 (3)**: `plannedtoolkit.py`'s own pre-trigger-engine `PLANNED_NOTIFICATIONS`
CRUD (`PlannedNotificationsRepository`, the `/planned-meta/notifications` endpoints, the
`PlannedNotification` dataclass and `notification_from_dict` on the desktop side) is retired —
this is the other half of the §1.6 item 1 decision that update (2) above didn't cover. It had
zero live callers anywhere (no desktop UI window called the repository/service wrappers that
called it), so this was a straight deletion, not a migration: the shared
`notification_service`/`trigger_engine` was already the only thing anything calls for planned
toolkit notifications. The `PLANNED_NOTIFICATIONS` collection constant is left as a removed,
commented placeholder in `collection_names.py` rather than deleted outright, so a stale Mongo
collection of that name (if one exists in any deployed incident database from earlier testing)
is traceable back to this entry rather than looking like a typo.

**Any future planned-toolkit work that touches notifications must call
`sarapp_db.services.notification_service.emit_notification` — never add a toolkit-local
notification collection, model, or CRUD endpoint again.** This applies repo-wide, not just to
plannedtoolkit: per the §1.6 item 1 decision, delivered-notification storage is shared
infrastructure owned by `notification_service.py`, and any module (safety, logistics, comms,
etc.) that needs to notify someone is a caller of it, never an owner of its own notification
store.

**Update 2026-11-21 (2)**: the desktop toast delivery bridge flagged missing in §1.2 finding 3
and §1.4 is now wired up. `sarapp_db.services.notification_service.emit_notification` broadcasts
a `type: "notification"` WebSocket event — the same event shape `intel.py`'s urgent-intel alert
already defines and `notifications/services/incident_bridge.py` already consumes on the desktop
side — alongside its existing mobile-push delivery, rather than inventing a second desktop
delivery path. Resolved recipients (`person_record`s, already computed server-side for push/ack)
are passed as a new `target_person_records` field; `incident_bridge.handle_notification_event`
now checks that field first (exact match against the active user, no section lookup) and falls
back to the existing `target_sections` resolution only when it's absent, so `intel.py`'s
existing broadcast is unaffected. A notification with no resolved recipients still broadcasts to
every connected client, matching the existing no-`target_sections` behavior. `emit_notification`
is unchanged in every other respect; a broadcast failure still never blocks persistence.

**Update 2026-11-21**: Phase 1 item (1), `plannedtoolkit.py`'s raw-write pattern, is resolved
differently than originally scoped. The router already called `BaseRepository` methods
(`insert_one`/`update_one`/`soft_delete`/`find_many`/`find_by_id`) for every write — the
`_next_compound_id` helper's O(n) full-collection scan for the max existing ID suffix (§5)
was the only "Blocking Phase 1" item actually still open. That scan is replaced with an
indexed `seq` field (via the existing `next_record_id` helper, the same pattern `aircraft.py`/
`personnel.py`/etc. already use) with a unique index added in
`server/sarapp_db/sarapp_db/mongo/indexes.py` (`_create_plannedtoolkit_indexes`). The
Quick-Assignment-promotion path's own redundant compound-ID scan for the new task's `task_id`
is also removed — it now derives `task_id` directly from the `int_id` already minted via
`next_int_id`, with no second scan. No data-shape change beyond the new `seq` field; existing
`PlannedRecordCreate`/`ScheduleItemCreate`/etc. field set is unchanged.

**Update 2026-07-18**: the program-wide notification engine identified as missing in §1.2
finding 3 has been built as a first Phase 1 slice, ahead of the rest of this document's
Phase 1 recommendation — see `server/sarapp_db/sarapp_db/services/notification_service.py`,
`server/sarapp_db/sarapp_db/services/trigger_engine.py`, `server/sarapp_db/sarapp_db/api/routers/notifications.py`
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
- `server/sarapp_db/sarapp_db/api/routers/plannedtoolkit.py`
- `modules/planning/meetings/` (Meeting Planner — model, repository, services, panel)
- `server/sarapp_db/sarapp_db/api/routers/meetings.py`
- `notifications/` (desktop Notifier, scheduler, rules engine, toast/panel UI)
- `server/sarapp_db/sarapp_db/api/routers/audit.py`, `server/sarapp_db/sarapp_db/mongo/audit.py`, `server/sarapp_db/sarapp_db/schemas/audit_schema.py`
- `server/sarapp_db/sarapp_db/api/routers/task_narratives.py` (Narrative — task-embedded)
- `modules/operations/taskings/` (Operations Tasking), `server/sarapp_db/sarapp_db/api/routers/operations.py`
- `modules/operations/teams/` (Teams)
- `server/sarapp_db/sarapp_db/api/routers/personnel.py` (master Personnel catalog)
- `server/sarapp_db/sarapp_db/api/routers/checkin.py` (Check-In / roster)
- `modules/gis/services/spatial_link_service.py` (entity-linking pattern)
- `server/sarapp_db/sarapp_db/api/routers/attachments.py` (canonical GridFS attachments)
- `modules/operations/taskings/attachments.py`, `modules/intel/services/intel_attachments.py` (formerly duplicate filesystem attachment stores; migrated onto the canonical GridFS API 2026-07-18)
- `modules/forms_creator/` (forms family/template/version framework)
- `server/sarapp_db/sarapp_db/api/routers/ic_overview.py`, `server/sarapp_db/sarapp_db/api/routers/operational_periods.py` (incident lifecycle)
- `server/sarapp_db/sarapp_db/mongo/collection_names.py`, `server/sarapp_db/sarapp_db/services/push.py`
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
    `server/sarapp_db/sarapp_db/api/routers/attachments.py`). At the time of this audit, two independent
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
    `sync_incident_personnel_from_master` (`server/sarapp_db/sarapp_db/api/routers/operations.py`) and
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
   around. Rationale: `send_to_person()` (FCM wrapper, `server/sarapp_db/sarapp_db/services/push.py`)
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
| Push/mobile delivery | `server/sarapp_db/sarapp_db/services/push.py` | `send_to_person()` | Reusable, currently unwired | Zero callers anywhere | Call from the trigger evaluator once notifications fire, if in scope |
| Meeting agenda/attendees/notes/action items | `modules/planning/meetings` | `meetings.py` router, `MeetingsService` | Ready to reuse | None significant | Event Schedule links to Meeting records by id; do not model agenda data in Event Schedule |
| Recurrence rules / reminders | Nobody (no shared utility) | — | Missing | Two bespoke recurrence reps already exist | Build one shared recurrence utility before Phase 1 schedule work, or explicitly scope down to plannedtoolkit's existing string rep and document it as the interim standard |
| Quick Assignment creation | `modules/plannedtoolkit` (`quick-assignments` tool) | `plannedtoolkit.py` generic `/planned/{tool}` routes | Ready to reuse | Minor: still raw writes | Migrate to `BaseRepository` |
| Quick Assignment → Tasking promotion | `plannedtoolkit.py` `promote_quick_assignment` | `/planned/quick-assignments/{id}/promote` | Resolved (Phase 2D) | None remaining in scope; a lone personnel-only assignee still has no Task-side equivalent (documented limitation, not a gap) | Done — `origin_module`/`origin_id` convention, team forwarding via `add_task_team`, database-level exactly-once via a sparse unique index on `origin_ref` |
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
  (`server/sarapp_db/sarapp_db/api/routers/attachments.py`) with `owner_type="planned_event"` (or a
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
| ~~`plannedtoolkit.py` still uses raw pymongo writes and O(n) compound-ID scanning (`_next_compound_id`) instead of `BaseRepository`~~ — resolved 2026-11-21: writes already used `BaseRepository`; `_next_compound_id` now uses an indexed `seq` field instead of scanning | `server/sarapp_db/sarapp_db/api/routers/plannedtoolkit.py`, `server/sarapp_db/sarapp_db/mongo/indexes.py` | **Resolved** |
| No trigger evaluation/execution engine exists | (missing) | **Blocking Phase 1** for any "reminder actually fires" feature |
| No shared, persisted, multi-user notification store | `IncidentCollections.NOTIFICATIONS` (dead), `plannedtoolkit.py` | **Blocking Phase 1** for cross-workstation notification delivery |
| ~~Desktop `Notifier` has no bridge from server-persisted/broadcast data~~ — resolved 2026-11-21: `emit_notification` broadcasts the existing `type: "notification"` WS event with resolved recipients, consumed by `incident_bridge.py` | `server/sarapp_db/sarapp_db/services/notification_service.py`, `apps/desktop/sarapp_desktop/notifications/services/incident_bridge.py` | **Resolved** |
| ~~Inconsistent origin-link convention (`source_type/source_id` vs `origin_module/origin_id`)~~ — resolved 2026-11-22 (Phase 2D): `promote_quick_assignment`'s formal task now writes `origin_module`/`origin_id` like `objectives.py` and the desktop Tasking repository already did | `plannedtoolkit.py`, `operations.py` (`create_task`), `objectives.py` | **Resolved** |
| Check-in roster hardcodes `team_id: None` | `server/sarapp_db/sarapp_db/api/routers/checkin.py` (`fetch_roster`) | **Required during Phase 1** — blocks reliable Registration→Team joins |
| `ScheduleWidget` has no date pickers, recurrence UI, or trigger/notification UI | `modules/plannedtoolkit/widgets/schedule_widget.py` | **Important, non-blocking** for Phase 0→1 backend work; blocking for any user-facing schedule UI |
| No shared recurrence/date-time/reminder utility | (missing) | **Important, non-blocking** — can defer if Phase 1 scope stays server-side/backend |
| ~~Two duplicate filesystem+manifest attachment stores~~ — resolved 2026-07-18: both `modules/operations/taskings/attachments.py` and `modules/intel/services/intel_attachments.py` now call the canonical GridFS `attachments` API | `modules/operations/taskings/attachments.py`, `modules/intel/services/intel_attachments.py` | **Resolved** |
| `finance_attachments` is a separate collection from canonical `attachments` | `server/sarapp_db/sarapp_db/api/routers/finance.py` | **Deferred** — out of toolkit scope |
| No canonical entity-type registry/enum across the codebase | multiple | **Important, non-blocking** for Phase 1 if toolkit scopes its own linking narrowly; blocking if Phase 1 wants a truly reusable cross-module contract |
| `send_to_person` (push) has no callers anywhere | `server/sarapp_db/sarapp_db/services/push.py` | **Deferred** unless push is explicitly in Phase 1 scope |
| Incident-level `status` has no validation enum and no close/reopen cascade | `server/sarapp_db/sarapp_db/schemas/incident_schema.py`, `ic_overview.py` | **Deferred** — toolkit should not depend on cascade behavior that doesn't exist |
| `operational_periods.py` `period_summary()` cross-module counts are stubbed (returns zeros) | `modules/planning/operational_periods/repository.py` | **Deferred** — don't build toolkit rollups on top of this stub |
| `INCIDENT_PERSONNEL` collection declared but apparently unused (check-in actually uses `RESOURCE_STATUS`) | `server/sarapp_db/sarapp_db/mongo/collection_names.py` | **Deferred question** — confirm before Registration work assumes either is authoritative |
| Unreconciled experimental worktree redesign of plannedtoolkit | `.claude/worktrees/...` (not on active branch) | **Deferred question** — needs a decision before Phase 1, not engineering work in this phase |
| Toolkit's live menu/navigation reachability unconfirmed | `modules/plannedtoolkit/__init__.py` (no external callers found) | **Deferred question** — confirm before assuming Phase 1 builds on a live feature |
| Two audit record shapes coexist in practice (`audit_schema.py` vs. `audit.py` router's `AuditRequest`) | `server/sarapp_db/sarapp_db/schemas/audit_schema.py`, `server/sarapp_db/sarapp_db/api/routers/audit.py` | **Obsolete/candidate for retirement** — reconcile to one shape, not this toolkit's job to fix but worth flagging upstream |

---

## Phase 0.5 (completed 2026-11-21, except where a dependency doesn't exist yet)

The deliverables below were explicitly deferred pending a separate go-ahead; that go-ahead
was given and this section records what's now done and what remains genuinely blocked.

**Backend tests** — added:
- `server/sarapp_db/sarapp_db/services/tests/test_trigger_engine.py`: a due one-shot trigger
  emits through the shared notification system with the correct source link; a trigger fires
  at most once across repeated evaluations (the "survives reconnect/sync without duplication"
  requirement — re-running the poll loop never re-fires an already-fired trigger); a future
  trigger is not fired; a disabled trigger is not fired; a recurring trigger is skipped rather
  than silently fired (pins down the *current*, deliberately incomplete behavior so a future
  change has to touch this test on purpose).
- `server/sarapp_db/sarapp_db/services/tests/test_notification_service.py`: persistence +
  incident scope + source entity link; audience resolution to a person_record; acknowledge/
  dismiss recipient-state updates; acknowledge is rejected for a person outside the resolved
  audience; `list_notifications` filters by source_type/source_id (cross-module entity link
  resolution); a desktop-toast broadcast failure never blocks persistence.
- `server/sarapp_db/sarapp_db/api/routers/tests/test_plannedtoolkit_repository.py` gained
  `test_quick_assignment_promotion_is_idempotent`: promoting the same Quick Assignment three
  times (including with a different `promoted_by` on the third call) returns the same
  `linked_tasking_id` every time, never overwrites the original `promoted_by`, and never
  creates a second Operations Tasking record.

Still blocked, not a gap in this pass: **a registration can link to Personnel without
overwriting the Personnel record** and **existing Check-In data can produce
expected-vs-checked-in results** cannot be tested because Registration doesn't exist yet
(§1.4/§1.6 — greenfield, out of Phase 0 scope). These become real tests once Registration is
built, not before.

**Thin vertical prototype** — implemented as an automated integration test (per the brief's
own allowance: "a minimal development-facing control or test harness is acceptable"), not a
UI: `server/sarapp_db/sarapp_db/api/routers/tests/test_planned_events_thin_vertical_prototype.py`.
Walks the full chain through the real API layer: create schedule item → attach + persist
trigger via `/planned-meta/schedule-triggers` → fire via `trigger_engine.evaluate_due_triggers`
(the same function the `NotificationTriggerLoop` poll tick calls) → notification persists in
the shared store → resolved back to the trigger via `source_id` → resolved further back to the
schedule item via `schedule_item_id`, starting from nothing but the notification → re-running
the scheduler produces no duplicate.

All four files were logic-verified against `mongomock` before being committed, since this
development container has no `mongod` binary to run the real Mongo-backed pytest suite — an
environment gap, not a reason to skip writing or verifying the tests.

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
