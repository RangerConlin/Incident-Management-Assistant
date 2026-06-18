# Planned Events Toolkit Playbook

## Purpose
The Planned Events Toolkit supports event-day coordination for incidents where much of the work is known ahead of time, but success depends on fast execution, live status visibility, safety, scheduling, compliance, and partner management.

Pre-planning belongs here when it directly prepares the day-of operating picture. The toolkit should not become a general event-planning suite; its center of gravity is running the event.

## Current Repo Signals
- `modules/plannedtoolkit` is already more mature than the other toolkit families.
- Existing tool definitions include:
  - External Messaging
  - Vendors
  - Permits
  - Public Safety
  - Quick Assignments
  - Health & Sanitation
- The existing UI already suggests a home view plus tabbed tool panels.

## Primary Users
- event planning staff
- Incident Commander or event lead
- logistics staff
- safety staff
- liaison staff
- public information or messaging staff

## Operational Goals
- maintain a clear event-day operating picture
- track schedule-driven work, live issues, and operational prompts
- maintain visibility on vendors, permits, inspections, public safety, and sanitation issues that matter today
- coordinate safety, public-facing messaging, and partner follow-up during the event
- allow pre-planned work to flow smoothly into day-of execution

## Existing Conceptual Model
The current implementation already points toward a shared record shape with fields like:
- title
- summary
- status
- priority
- assigned_to
- location
- scheduled_at
- due_at
- metadata

That is a strong foundation for this toolkit family.

## Candidate Tool Set
- External Messaging
- Vendors
- Permits
- Public Safety
- Quick Assignments
- Health & Sanitation
- Schedule / milestones
- Site readiness checklist
- partner contact directory
- contingency planning worksheet

## Proposed Workflow
1. Define the event profile, timeline, key milestones, zones, and known day-of triggers.
2. Preload vendors, permits, inspections, message templates, and recurring Quick Assignments where useful.
3. Run the event from the dashboard: monitor schedule, open issues, active Quick Assignments, public safety, health/sanitation, and vendor blockers.
4. Create or auto-fire Quick Assignments as operational prompts.
5. Promote or open full Operations Tasking only when a Quick Assignment needs the full tasking workflow.
6. Export or review the event-day history after demobilization.

## Home View Ideas
The home view should act as a dashboard launcher rather than one universal dashboard. Different event roles need different attention surfaces.

Candidate dashboards:
- Event Command: operating picture, major blockers, schedule, cross-functional status
- Operations / Quick Assignments: active assignments, upcoming scheduled prompts, recurring assignment health, promoted taskings
- Public Safety: safety reports, dispatch queue, patrol or zone coverage, high-priority incidents
- Vendor & Permit: vendor check-in, missing documents, permit and compliance blockers, booth or location readiness
- Health & Sanitation: inspections, sanitation issues, critical violations, follow-ups
- Messaging: queued, sent, and scheduled messages plus urgent advisories

Each dashboard may include:
- Overview: the normal operating picture for that role
- Needs Attention: exceptions, blockers, overdue items, missed recurrence, or urgent follow-up

The planned event toolkit should not force one command-wall dashboard. It should provide role-focused dashboards backed by shared schedule, Quick Assignment, issue, vendor, safety, health, messaging, and team-link data.

## Core Records
- shared planned-event work item
- Quick Assignment
- Quick Assignment recurrence rule
- schedule item
- schedule trigger
- reminder / notification trigger
- dependency marker
- readiness checkpoint

## Teams
Planned events should use the normal Operations Teams module as the source of truth. The toolkit may provide filtered shortcuts or dashboard summaries for event teams, but it should not create a separate planned-event team model.

Teams should retain the same full-fidelity data and status behavior as the normal Teams module. The planned toolkit can make team status easier to see during the event, but full team details and durable team state belong in the existing Teams workflow.

## Locations And Zones
Do not create a planned-event zone model yet. Without GIS or a proven need for maintained zone records, the extra structure would slow down event-day entry.

Use lightweight free-text Location / Zone fields across Quick Assignments, schedule items, vendor records, safety reports, health/sanitation items, and notifications. These fields can later be normalized into real zone records if GIS or map workflows justify it.

Design rule: location and zone are lightweight text until mapping needs prove otherwise.

## Quick Assignments
Quick Assignments are frictionless operational prompts for event-day work. They replace the planned toolkit's lightweight "Tasking & Assignments" concept while keeping full Operations Tasking as the formal tasking workflow.

Design rules:
- no minimum fields; emergency workflow must never be blocked by required data entry
- same statuses as the full Operations Tasking module
- assignable to normal Operations teams or people when useful
- can be created manually, scheduled, recurring, milestone-triggered, or generated from vendor, safety, health/sanitation, inspection, or issue follow-up when completion tracking and assignment ownership are needed
- can be promoted to or opened in the full Operations Tasking window
- once promoted, store the linked full tasking ID so the formal task can become the source of truth

Scheduling behavior:
- A Quick Assignment may have a scheduled time.
- A `Recurring?` checkbox controls whether the assignment is one-time or recurring.
- When `Recurring?` is unchecked, the assignment is a single prompt that can become active or visible at the scheduled time.
- When `Recurring?` is checked, recurrence options are shown and the rule creates repeated Quick Assignment instances.
- Default missed-occurrence behavior should be "create only the latest overdue occurrence" unless the user chooses otherwise.

Lifecycle:
- Template / scheduled prompt: optional source record for future or recurring assignments
- Pending: exists but is not active yet because its scheduled time has not arrived
- Active: visible in day-of dashboards and ready to work
- Full tasking status: uses the same status vocabulary as Operations Tasking
- Overdue or missed: computed attention condition, not a separate status unless the full Tasking module adds one
- Promoted: linked to a full Operations Tasking record

Promotion behavior:
- Promote to Tasking creates a full Operations tasking from whatever Quick Assignment data exists.
- The Quick Assignment stores the linked tasking ID, promoted timestamp, and promoted user if available.
- After promotion, the Quick Assignment shows as promoted and stops accepting user edits.
- Its primary action becomes Open Full Tasking.
- Further detailed work happens in the Operations Tasking module.

Creation sources should store a source link where practical:
- source type
- source ID
- source label
- triggered timestamp

Auto-fired Quick Assignments are normal Quick Assignments after creation. The source link explains why they exist, but the assignment itself should behave like any other Quick Assignment.

## Quick Assignment Data Contract
The user-facing term is Quick Assignment. Existing code may temporarily keep the `tasks` tool key for compatibility, but new design language should not call these planned-event taskings.

Preferred future naming:
- UI label: Quick Assignments
- future API path: `/api/incidents/{incident_id}/planned/quick-assignments`
- future collection name: `planned_quick_assignments`
- legacy-compatible tool key during transition: `tasks`

Quick Assignment fields should remain optional unless a lower-level storage or API constraint absolutely requires a generated value. Emergency workflow must allow sparse records.

Base fields:
- id / record_id
- incident_id
- title
- summary or notes
- status
- priority
- assigned_to
- assigned_team_id
- assigned_person_id
- location
- zone
- scheduled_at
- due_at
- metadata
- created_at
- updated_at

Scheduling and lifecycle fields:
- recurring
- recurrence_rule
- recurrence_start_at
- recurrence_end_at
- missed_occurrence_behavior
- template_id
- generated_from_template_id
- lifecycle_state
- active_at
- triggered_at

Source link fields:
- source_type
- source_id
- source_label
- source_tool

Promotion fields:
- linked_tasking_id
- promoted_at
- promoted_by
- promoted_read_only

Status alignment:
- Quick Assignments use the full Operations Tasking status vocabulary.
- Current authoritative tasking lookup: Draft, Planned, In Progress, Completed, Cancelled.
- Existing repository translation also accepts Assigned for compatibility; do not rely on Assigned as a new Quick Assignment-only status unless Operations Tasking makes it canonical.
- Overdue, missed, pending, active, and promoted are lifecycle or computed attention states, not replacement statuses.

Promotion mapping into full Operations Tasking:
- title -> task title
- summary / notes -> assignment or description field, depending on the Operations Tasking target
- priority -> task priority
- status -> task status
- location / zone -> task location
- assigned team -> task team assignment when available
- assigned person -> personnel assignment when supported
- scheduled_at / due_at -> due time or schedule-related field
- source link -> task metadata or audit note
- Quick Assignment ID -> task source reference

Promotion rules:
- promote even when the Quick Assignment is sparse
- create exactly one linked full tasking per Quick Assignment
- after promotion, stop accepting user edits on the Quick Assignment
- display the linked tasking ID
- provide Open Full Tasking as the primary action
- do not create a second tasking if one is already linked

## Schedule, Reminders, And Assignment Triggers
Schedule items describe what is happening at the event. Quick Assignments describe work that someone or some team needs to complete because of it.

Schedule items may represent:
- milestone
- activity
- closure
- opening
- briefing
- shift change
- announcement
- inspection window
- performance
- demobilization item

Schedule triggers may create either reminders/notifications or Quick Assignments.

Reminder / notification triggers:
- inform, prompt, or remind
- do not require assignment ownership
- do not need completion tracking
- may support acknowledge or dismiss
- should appear in notification feeds, schedule views, or role dashboards

Quick Assignment triggers:
- require a person or team to do work
- need completion tracking
- can be assigned or reassigned
- can be promoted to full Operations Tasking
- should appear in Operations / Quick Assignments dashboards

Decision rule: if it needs an assignee and completion tracking, create a Quick Assignment. If it only needs awareness or a prompt, create a reminder or notification.

Schedule-linked trigger examples:
- notification: road closure begins in 15 minutes
- notification: scheduled advisory is due to send
- notification: briefing starts in 10 minutes
- Quick Assignment: inspect barricades at Gate 2
- Quick Assignment: perform sanitation sweep in Zone C
- Quick Assignment: deploy team to vendor row

## Schedule Trigger Data Contract
Schedule triggers are child records or embedded records attached to schedule items. They define what should happen relative to a schedule item or absolute time.

Base trigger fields:
- id / trigger_id
- incident_id
- schedule_item_id
- trigger_type: notification or quick_assignment
- label
- offset_minutes
- trigger_at
- relative_to: start, end, or manual
- enabled
- created_at
- updated_at

Notification trigger fields:
- audience_role
- audience_user_id
- notification_channel
- requires_acknowledgement
- message_template
- link_to_schedule_item
- location / zone

Quick Assignment trigger fields:
- quick_assignment_template_id
- title
- summary / notes
- assigned_to
- assigned_team_id
- assigned_person_id
- location
- zone
- priority
- recurring
- recurrence_rule
- missed_occurrence_behavior

Trigger execution rules:
- notification triggers create reminders/notifications only
- Quick Assignment triggers create normal Quick Assignment records
- fired records should store the source trigger ID
- triggers should be idempotent for the same scheduled occurrence
- recurring triggers should follow the `Recurring?` behavior defined for Quick Assignments

## Reminders And Notifications
Reminders and notifications are awareness prompts. They are separate from Quick Assignments because they do not require assigned ownership or completion tracking.

Use reminders / notifications for:
- scheduled awareness prompts
- role-specific reminders
- schedule countdowns
- advisory prompts
- acknowledgement-only notices
- operational nudges that should not clutter the Quick Assignment board

Reminder / notification fields:
- id / notification_id
- incident_id
- title
- message
- severity
- audience_role
- audience_user_id
- notification_channel
- location / zone
- scheduled_at
- triggered_at
- acknowledged_at
- acknowledged_by
- dismissed_at
- source_type
- source_id
- source_label
- created_at
- updated_at

Behavior:
- notifications may be scheduled or fired immediately
- acknowledgement is optional and should be configured per trigger
- dismissed or acknowledged notifications should remain available in history
- notifications should link back to their schedule item, trigger, or source record when practical
- notifications should not have tasking statuses
- notifications should not be promoted to full Operations Tasking; create a Quick Assignment first if work tracking becomes necessary

Decision rule: reminders and notifications prompt awareness. Quick Assignments track work.

## Dashboard Action Boundaries
Dashboards should support inline actions for day-of motion, while deeper editing opens the owning module.

Allowed inline:
- change status
- assign or reassign
- acknowledge
- dispatch
- mark checked in, blocked, or resolved
- create a Quick Assignment
- promote or open a Quick Assignment as full Operations Tasking

Open the owning module or detail view for:
- full team record editing
- message content and approval workflow
- permit documents or templates
- vendor profile details
- full safety report detail
- full inspection or checklist detail
- full Operations Tasking workflow

Every dashboard card or row should have an open-detail path so users are not trapped in summarized views.

## Important Integrations
- command objectives
- contacts and personnel
- communications and messaging
- safety
- logistics
- activity log and documentation

## UX Priorities
- dashboard-first experience
- clean due-date management
- simple filtering by category, owner, and status
- dependency visibility
- clear handoff from pre-event setup to event-day execution
- fast Quick Assignment creation with no required-field friction
- easy transition from Quick Assignment to full Operations Tasking

## Open Design Questions
- Should all planned-event tools continue sharing one generic record model, or do some need their own specialized schemas?
- Should readiness be explicitly scored or simply inferred from open blockers?
- Which event-day tools belong here versus in other operational modules?
- Which Quick Assignment fields should map into full Operations Tasking during promotion?
- Which role-focused dashboards should ship first?

## Suggested Next Design Pass
- define dependency handling
- define the event-day transition workflow
- define Quick Assignment promotion mapping into full Operations Tasking
- define first-pass dashboard cards and inline actions
