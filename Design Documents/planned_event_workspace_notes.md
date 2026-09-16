# Planned Event Workspace Notes

Working notes for planned event functionality, especially one-day public safety events such
as Tunnel to Towers. This document is intentionally exploratory: use it to capture access
patterns, proposed modules, classes, data fields, and open questions before implementation.

## Product Direction

The main program remains first and foremost an incident-management application for SAR,
ICS/NIMS, disaster management, and complex incidents. Planned event functionality is an
add-on workspace profile, not a separate app and not a watered-down incident.

For planned events, the app should make the quick operational path obvious while keeping the
full incident modules available under an **Advanced Tools** submenu. Users should not
accidentally open heavyweight tasking, objectives, resource requests, or planning-cycle
modules when they need event-day operations.

## Main Program Access Pattern

When the active incident type/profile is a planned event, the existing menu-first PySide/ADS
application should keep its normal structure but reorder and group menu entries around event
operations.

Primary planned-event tools should appear directly in the relevant menus. Full incident
modules should move under an **Advanced Tools** submenu for planned-event workspaces.

Example Operations menu for planned events:

```text
Operations
  Event Operations Board
  Event Units
  Calls / Issues
  Event Map
  Event Log
  ----------------
  Advanced Tools >
      Operations Dashboard
      Operations Unit Log ICS-214
      Tactics and Resources Planner
      Operations Section Organization
      Team Status Board
      Task Board
      Team Location Map
      Incident Map
```

The modules are not disabled. The intended behavior is progressive disclosure: accessible,
but one deliberate click deeper.

## Existing Planned Toolkit State

Current planned toolkit implementation exists under `modules/plannedtoolkit/` with a
Mongo-backed FastAPI router in `data/db/sarapp_db/api/routers/plannedtoolkit.py`.

Currently built:

- External Messaging / Promotions
- Event Schedule
- Vendors
- Permits
- Quick Assignments
- Quick Assignment promotion to full Operations Tasking
- Health & Sanitation
- Schedule trigger records
- Planned notification records

Shared notification/trigger infrastructure also exists:

- `data/db/sarapp_db/services/notification_service.py`
- `data/db/sarapp_db/services/trigger_engine.py`
- `lan_server/notification_trigger_loop.py`

Current gap: the existing toolkit is mostly CRUD/table-based and does not yet provide a
lightweight CAD-style event operations board.

## Modules Needing Lightweight Planned-Event Replacements

Highest priority:

- Full Operations Task Board / Taskings -> Event Operations Board or Calls / Issues Board
- Resource Requests ICS-213RR -> Event Needs / Supply Requests
- Tactics and Resources Planner -> Event Staffing / Coverage Plan
- Incident Objectives -> Event Priorities, likely embedded on overview rather than a full
  objective-management module

Medium priority:

- Operational Period Manager -> Event Timeline / Event Phases
- Operations Dashboard -> Event Dashboard
- Resource Status / Check-In -> Event Roster / Check-In
- Incident Organization / Operations Section Organization -> Event Contacts / Roles

Reusable as-is or with light planned-event presentation:

- Teams / Team Status: reuse the original implementation for planned events. Do not create
  a replacement, duplicate, parallel `EventUnit` model, or second team workflow unless a
  future hard requirement forces that decision.
- Communications Log / Quick Entry
- Communications Plan, possibly via a simpler Event Comms Plan surface
- Incident Map / Team Location Map, with event route/post/aid-station presets
- Medical Plan, possibly via a lighter Aid Stations / EMS Plan view
- Safety Message / Hazard Register, surfaced as Event Safety Notes
- Situation Report, probably under Advanced Tools unless a lighter event summary/export is
  built

## Candidate Data Classes

These are planning sketches, not final schemas.

## Event Task Board Replacement

The planned-event replacement for the full Operations Task Board should operate similarly
to the current task board/detail-window pattern, but with a much smaller task record and a
lighter detail window.

Current full Task Detail has ten main tabs:

- Narrative
- Teams
- Assignment Details
- Safety
- Communications
- Debriefing
- Attachments/Forms
- Intel
- Log
- Planning

Planned-event task detail should be limited to four main tabs:

- **Narrative**
- **Team**
- **Attachments**
- **Log**

Fields currently spread across heavier tabs should only be promoted into the planned-event
task detail if they are needed for fast event operations. For example, Communications should
not be a tab in this mode; the task header only needs a `primary_channel` dropdown. Assignment
details can be captured in the Narrative fields rather than in a separate Assignment Details
tab. Attachments are useful operational context and should be included, but only as a
lightweight file list; this is not the full Attachments/Forms workflow from the incident
task detail window.

Suggested always-visible header fields:

- `event_task_id`
- `incident_id`
- `task_number`
- `task_type`
- `priority`
- `status`
- `location`
- `zone`
- `post_id`
- `assigned_team_id`
- `primary_channel`
- `received_at`
- `updated_at`

Proposed detail-window layout:

```text
Top row:
  Category / Type / Priority / Status / Task ID

Full-width row:
  Location

Two-column row:
  Left:
    Assignment
    Requestor
  Right:
    Assigned Teams list

Full-width row:
  Narrative quick-entry box

Tabs:
  Narrative
  Team
  Attachments
  Log
```

Implementation direction: begin by copying the current full Operations Task Detail window
and paring it down. Keep the existing behavior for Narrative, Team, and Log as much as
possible, since Team and Log are intended to be fairly automated. In normal event use, the
operator should mainly interact with the Narrative quick-entry box, Narrative tab, and the
small set of top detail fields.

Fields that belong in the top detail area:

- Category
- Type
- Priority
- Status
- Task ID
- Location
- Assignment
- Requestor
- Primary Channel
- Assigned Teams list

The narrative quick-entry box belongs below the assignment/requestor and assigned-teams row,
outside the tabs, with behavior kept the same as the current full Task Detail window.

The `primary_channel` field can be included in the top detail controls, likely as a compact
dropdown near the status/type controls or near the location/assignment area, depending on
space.

First-draft mockup:

```text
+------------------------------------------------------------------------------+
| Event Task Detail - EVT-024                                                   |
+------------------------------------------------------------------------------+
| Category: Medical v   Type: Runner Assist v   Priority: High v   Status: Open v|
| Task ID: 024          Primary Channel: MED-1 v                                 |
|                                                                              |
| Location                                                                     |
| +--------------------------------------------------------------------------+ |
| | Mile 2 Aid Station                                                       | |
| +--------------------------------------------------------------------------+ |
|                                                                              |
| +---------------------------------------------+ +--------------------------+ |
| | Assignment                                  | | Assigned Teams            | |
| | +-----------------------------------------+ | | Med-1      On Scene       | |
| | | Check runner, request EMS if needed.    | | | Ops-2      Available      | |
| | +-----------------------------------------+ | |                          | |
| | Requestor: Aid Station Lead                 | | [ Add ] [ Remove ]        | |
| +---------------------------------------------+ +--------------------------+ |
|                                                                              |
| Narrative Entry                                                              |
| +--------------------------------------------------------------------------+ |
| | Med-1 reports runner conscious, requesting wheelchair transport.         | |
| +--------------------------------------------------------------------------+ |
| Team: Med-1 v       Type: Status Update v       Critical [ ]       [ Add Entry]|
+------------------------------------------------------------------------------+
| Narrative | Team | Attachments | Log                                          |
+------------------------------------------------------------------------------+
```

Assigned Teams interaction:

- Right-clicking a team in the Assigned Teams list opens a context menu for status changes.
- Status options should match the planned-event team/unit status vocabulary.
- The user should be able to update the assigned team's status without opening the full team
  detail window.
- Opening the full team detail remains available through a deliberate action such as
  double-click or context-menu "Open Team".

## Event Request Board

The Event Request Board is the planned-event intake layer for requests submitted by field
users, staff, partners, or command. It is a general request board, not a logistics-only board
and not a formal ICS-213RR workflow.

Purpose:

- Collect requests from field/mobile users and desktop users.
- Let command/ops/logistics/medical/etc. triage them.
- Approve, deny, close, or ask for more information.
- Create an event task only when a request actually requires actionable field work.

Important design decision: **approving a request must not automatically convert it into a
task**. Some valid requests are informational, administrative, or command-decision items and
do not require team assignment.

Core workflow:

```text
New
  -> Reviewing
  -> Approved / Needs Info / Denied / Duplicate / Canceled
  -> Closed
```

Optional task workflow:

```text
Approved request
  -> Create Event Task, only when actionable work is needed
```

Approval means:

> The request is legitimate and accepted for handling.

Approval does not mean:

> A team needs to be assigned.

Candidate request statuses:

- New
- Reviewing
- Approved
- Needs Info
- Denied
- Duplicate
- Canceled
- Closed

Candidate request types:

- Supply
- Equipment
- Personnel
- Medical
- Traffic
- Security
- Facilities
- Communications
- Information
- Command Decision
- Other

Candidate board columns:

- Req #
- Status
- Priority
- Type
- Location / Post
- Summary
- Requested By
- Owner
- Submitted
- Linked Task

Candidate actions:

- Open / Review
- Claim / Assign Reviewer
- Approve
- Deny
- Need Info
- Mark Duplicate
- Close
- Create Task
- Log Decision
- Open Linked Task

Candidate close reasons:

- Resolved Without Task
- Information Provided
- Decision Logged
- Denied
- Duplicate
- Canceled
- Converted to Task

Candidate data class:

```python
@dataclass
class EventRequest:
    request_id: str
    incident_id: str
    request_number: str
    status: str
    priority: str
    request_type: str
    owner_section: str
    location: str
    zone: str
    post_id: str
    summary: str
    details: str
    requested_by: str
    requested_by_contact: str
    submitted_from: str
    needed_by: str
    submitted_at: str
    reviewed_by: str
    reviewed_at: str
    decision_note: str
    duplicate_of_request_id: str
    linked_event_task_id: str
    closed_reason: str
    closed_at: str
    created_at: str
    updated_at: str
```

When a request is converted to an event task, copy:

- `request_type` -> task category/type
- `priority` -> task priority
- `location` / `post_id` -> task location/post
- `summary` / `details` -> assignment and initial narrative
- `requested_by` -> requestor
- `request_id` -> source request link

The request remains visible after task creation with its `linked_event_task_id` populated.

First-draft request detail mockup:

```text
+------------------------------------------------------------------------------+
| Request Detail - REQ-014                                                      |
+------------------------------------------------------------------------------+
| Type: Supply v     Priority: Normal v     Status: Reviewing v     Req ID: 014 |
| Owner: Logistics v Submitted: 09:14       Needed By: 10:00                    |
|                                                                              |
| Location                                                                     |
| +--------------------------------------------------------------------------+ |
| | Mile 2 Aid Station                                                       | |
| +--------------------------------------------------------------------------+ |
|                                                                              |
| Requested By                                                                 |
| +------------------------------+   Contact                                  |
| | Aid Station Lead             |   | Radio MED-1 / 555-0100                 |
| +------------------------------+   +---------------------------------------+ |
|                                                                              |
| Summary                                                                      |
| +--------------------------------------------------------------------------+ |
| | Need 2 cases of water.                                                    | |
| +--------------------------------------------------------------------------+ |
|                                                                              |
| Details                                                                      |
| +--------------------------------------------------------------------------+ |
| | Current supply is below half. Estimate another 45 minutes of runners.     | |
| +--------------------------------------------------------------------------+ |
|                                                                              |
| Decision Note                                                                |
| +--------------------------------------------------------------------------+ |
| | Approved. Logistics will restock during next route sweep.                 | |
| +--------------------------------------------------------------------------+ |
|                                                                              |
| [ Approve ] [ Need Info ] [ Deny ] [ Create Task ] [ Close ] [ Open Task ]    |
+------------------------------------------------------------------------------+
| Narrative | Attachments | Log                                                 |
+------------------------------------------------------------------------------+
```

Request detail tabs:

- **Narrative**
- **Attachments**
- **Log**

The Narrative tab keeps the naming consistent with task detail. For requests, it functions
as the clarification/conversation/decision-history text area rather than a field-execution
narrative.

Suggested tabs:

### Narrative Tab

Fast chronological notes and assignment text. This replaces most of the detailed assignment
fields from the full task detail window for planned-event use.

Candidate fields per narrative entry:

- `entry_id`
- `event_task_id`
- `timestamp`
- `entered_by`
- `entry_type`: Note, Assignment, Status Update, Decision, Safety, Medical, Other
- `team_id`
- `text`
- `critical`
- `created_at`
- `updated_at`

### Team Tab

Team/unit assignment and status for the selected event task. This should reuse the existing
team implementation as much as practical. Current direction: do not build a separate
lightweight Team module for planned events unless later design identifies specific fields or
workflows that must be hidden.

Candidate fields:

- `event_task_id`
- `assigned_team_ids`
- `assigned_unit_ids`
- `assigned_person_ids`
- `lead_contact`
- `team_status`
- `team_location`
- `team_notes`

### Attachments Tab

Simple file attachments for the selected event task. Use the canonical GridFS attachments
service. Do not duplicate the full incident task detail window's Attachments/Forms behavior
and do not add form generation to this tab.

Candidate attachment fields:

- `attachment_id`
- `event_task_id`
- `owner_type`: planned_event_task
- `owner_id`
- `file_name`
- `content_type`
- `attachment_type`: Photo, Document, Map, Message Screenshot, Other
- `description`
- `uploaded_by`
- `uploaded_at`

Suggested actions:

- Add File
- Open
- Edit Description
- Remove

### Log Tab

Read-oriented activity history for the selected event task. This should show generated task
events such as create, assign, status change, clear/cancel, and optionally narrative entries.
It should not expose the full ICS-214/task/team-log nested tab structure unless the user opens
Advanced Tools.

Candidate log event fields:

- `log_entry_id`
- `event_task_id`
- `timestamp`
- `event_type`
- `summary`
- `actor`
- `source`
- `metadata`

### PlannedEventWorkspace

Represents planned-event presentation state for an incident.

Candidate fields:

- `incident_id`
- `event_name`
- `event_type`
- `workspace_phase`: Planning, Setup, Active, Wrap-Up, Complete, Canceled
- `starts_at`
- `ends_at`
- `timezone`
- `primary_location`
- `route_id`
- `command_post_location_id`
- `default_dashboard_layout_id`
- `notes`
- `created_at`
- `updated_at`

### EventCall

Dispatch-style event issue/call record.

Candidate fields:

- `call_id`
- `incident_id`
- `call_number`
- `call_type`: Medical, Traffic, Lost Person, Suspicious Activity, Supply Need, Staffing,
  Weather, Facility, Information, Other
- `priority`: Low, Normal, High, Critical
- `status`: Open, Assigned, En Route, On Scene, Resolved, Canceled, Referred
- `summary`
- `details`
- `location`
- `zone`
- `post_id`
- `reported_by`
- `reported_via`
- `assigned_unit_ids`
- `received_at`
- `dispatched_at`
- `enroute_at`
- `onscene_at`
- `cleared_at`
- `disposition`: Resolved, Transported, Referred To Agency, No Action Needed, Duplicate,
  Canceled
- `linked_tasking_id`
- `linked_log_entry_ids`
- `created_by`
- `created_at`
- `updated_at`

### EventNeed

Lightweight planned-event need or supply request, separate from formal ICS-213RR unless
promoted.

Candidate fields:

- `need_id`
- `incident_id`
- `title`
- `description`
- `need_type`: Supplies, Equipment, Personnel, Transportation, Facilities, Food/Water,
  Communications, Other
- `priority`
- `status`: Open, Assigned, In Progress, Filled, Canceled
- `requested_by`
- `needed_at`
- `needed_location`
- `assigned_to`
- `source_call_id`
- `linked_resource_request_id`
- `created_at`
- `updated_at`

### EventPost

Known fixed event location or function.

Candidate fields:

- `post_id`
- `incident_id`
- `name`
- `post_type`: Command Post, Aid Station, Checkpoint, Traffic Post, Staging, Volunteer Post,
  Supply Point, Route Marker, Other
- `location`
- `zone`
- `map_feature_id`
- `radio_channel`
- `assigned_unit_ids`
- `staffing_minimum`
- `staffing_target`
- `notes`
- `created_at`
- `updated_at`

### EventRosterEntry

Planned-event expected participant/staff/volunteer record. Actual arrival should still be
handled by Check-In / resource status.

Candidate fields:

- `roster_entry_id`
- `incident_id`
- `person_record`
- `display_name`
- `event_role`
- `assigned_post_id`
- `assigned_unit_id`
- `expected_arrival_at`
- `expected_release_at`
- `checkin_status`: Expected, Checked In, No Show, Released
- `registration_source`
- `external_registration_id`
- `waiver_status`
- `notes`
- `created_at`
- `updated_at`

## Open Design Questions

- Should Event Operations Board combine calls, units, and needs in one panel, or use
  separate docks that work well together in the default planned-event layout?
- Should EventCall be its own collection, or should it reuse/extend existing planned
  Quick Assignments?
- Should EventUnit reuse Operations Teams directly, or remain a lighter event-specific
  projection that can optionally link to a team?
- What is the right first-release scope for Tunnel to Towers: calls/units only, or also
  event roster/check-in and supply needs?
- Which event types need templates first: charity run, parade, fair/festival, ceremony,
  training/exercise?
- Should planned-event modules use "incident_id" everywhere, or introduce an explicit
  "event_id" alias only at the UI/text layer?
