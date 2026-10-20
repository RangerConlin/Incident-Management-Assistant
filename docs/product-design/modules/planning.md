# Planning

## Purpose

Turn incident objectives into operational periods, work assignments, resource requirements, meeting outputs, and tasking handoffs.

Planning is the bridge between high-level incident direction and executable operations. It owns the planning cycle, operational periods, objective templates, tactics/resources planning, work assignments, resource gaps, hazards, meetings, and demobilization planning.

## Users

- Planning Section staff building objectives, operational periods, work assignments, and planning products.
- Operations staff receiving planned work as executable tasks.
- Logistics staff responding to resource gaps and resource requests created from planning needs.
- Command staff reviewing planning cycle status, blockers, approvals, and readiness.
- Safety staff reviewing hazards and ICS-215A-style planning concerns.

## Current Features

- Planning dashboard/glance widget with planning-cycle status, blockers, approvals, resource/safety gaps, and objective-to-strategy momentum.
- Operational Period Manager for creating, cloning, editing, setting active periods, defining start/end/duration, adding situation summary, command emphasis, weather, objectives, and carry-forward notes.
- Meetings panel for planning meetings, agenda, attendees, notes, note categories, routing notes to logs, meeting templates, operational-period meeting sets, and ICS-230 printing.
- Objective Templates manager with create/edit/archive/unarchive/delete, CSV import/export, tags, priorities, and status fields.
- Tactics and Resources Planner organized around objectives, strategies/work assignments, resource gaps, hazards, agency requests, outputs, and operations task creation.
- Work Assignment detail window with overview, resources/ICS-215, hazards/ICS-215A, tasks, agency requests, and outputs.
- Resource requirement editing from planning, including ability to assign resources and open related resource request workflows.
- Demobilization planning panel with priorities, nearing-release resource/team table, and checklist concepts.

## Core Workflows

- Define or select an operational period.
- Create or refine incident objectives and planning templates.
- Build work assignments/strategies under objectives.
- Identify required resources, hazards, agency requests, and planning outputs.
- Confirm available resource needs directly on a work assignment when they are already filled, or escalate only unresolved needs into Resource Requests.
- Generate or link operations tasks from planned work.
- Run meetings and capture planning notes, action items, and logs.
- Track planning-cycle blockers, approvals, gaps, and readiness.
- Prepare demobilization priorities and release considerations.

## Build Status

Partial with several strong islands.

The tactics/resources planner and work assignment detail flow appear to be the most important built planning surfaces. They establish a clear hierarchy: incident objectives lead to work assignments/strategies, which then connect to operations tasks and resource needs.

Operational period management, meeting management, and objective templates also appear to have real desktop UI. The planning dashboard/glance widget exists and is conceptually useful, but its live-data completeness should be verified. Some planning entry points still return placeholders, including dashboard/approval-style windows, so the planning module should be treated as uneven rather than uniformly complete.

Demobilization planning exists as a planning panel, but it appears more like an early planning/checklist concept than a fully integrated release workflow.

## Screens And UI Inventory

- Desktop: Planning Glance/Dashboard widget.
- Desktop: Operational Period Manager.
- Desktop: Meetings panel.
- Desktop: Meeting Template Manager.
- Desktop: Objective Templates editor.
- Desktop: Tactics and Resources Planner.
- Desktop: Work Assignment Detail window.
- Desktop: Resource Requirement editor/dialogs.
- Desktop: Demobilization panel.
- Desktop: placeholder planning windows for some dashboard/approval paths.
- Mobile: no dedicated planning workspace identified.

## Links To Other Modules

- Tasking: planning work assignments can produce or link to operations tasks.
- Logistics: resource requirements, gaps, agency requests, and demobilization planning connect to resource status, facilities, resource requests, vehicles, aircraft, and personnel availability. Resource Requests should be used as an escalation path for unresolved or track-worthy needs, not as a mandatory step for every work-assignment resource line.
- Command: objectives, command emphasis, approvals, and incident readiness are command-facing planning outputs.
- Safety: hazards and ICS-215A-style planning data connect planning to risk review.
- Documentation/Forms: operational periods, meetings, ICS-230, ICS-215/215A concepts, and planning outputs become incident documents.
- Situation/Intel: situation summaries, objectives, and planning assumptions depend on current incident information.
- Logs: meeting notes and planning actions can be routed into logs.

## Desktop Experience

Desktop is the planning workbench.

The module is split across specialized windows rather than one single planning cockpit. Operational periods, meetings, templates, tactics/resources, work assignment details, and demobilization each have their own workspace. This matches the way planning work happens, but it also makes cross-window consistency important.

The Tactics and Resources Planner is the clearest center of gravity. It frames planning as objectives, strategies/work assignments, resource requirements, hazards, agency requests, outputs, and task handoff. That is likely the best anchor for future design work.

## Mobile Experience

No dedicated mobile planning workspace was identified.

Mobile receives planning outcomes indirectly through tasking, field dashboard context, team assignment information, forms, and incident operational-period context. It should probably remain consumption-focused unless a future design intentionally adds field planning, supervisor review, or meeting-note workflows.

## Current Gaps

- Planning module wiring is uneven: some windows are real, while some entry points still show placeholders.
- The planning dashboard/glance widget needs verification for live data versus static/demo-style presentation.
- Demobilization planning is not yet clearly tied into logistics resource release and team/resource lifecycle.
- The user-facing distinction between objective, strategy/work assignment, operations task, and resource request needs to be made clearer.
- Planning outputs and generated forms need a documented readiness state.
- Mobile has no explicit planning experience.
- Planning status and approval workflows are not yet clearly defined as a customer-facing lifecycle.

## Design Questions

- What is the canonical planning cycle from operational period setup through approval and operations handoff?
- Should Tactics and Resources become the primary planning workspace, with other planning screens treated as supporting tools?
- What exactly is a work assignment in customer language, and how is it different from an operations task?
- When a resource gap is identified in planning, what should happen automatically: create a resource request, alert logistics, reserve inventory, or simply flag the gap?
- How should the planner mark "needed resources are available" and continue without creating a Resource Request?
- Which planning products must be printable/exportable for an operational period to be considered complete?
- How should meeting notes become tasks, resource requests, safety items, or log entries?
- What does "approval" mean in the planning module: command approval, section approval, document approval, or all of these?

## Future Design Ideas

- A planning cycle board showing objectives, strategies, resource gaps, safety review, approvals, meetings, and task handoff in one place.
- A clearer work-assignment-to-task conversion flow with visible handoff status.
- Operational period readiness checklist with missing objectives, unresolved hazards, unfilled resources, unapproved products, and unassigned tasks.
- Meeting action extraction that can create tasks, resource requests, safety items, or log entries from meeting notes.
- Integrated demobilization workflow that coordinates planning priorities with logistics release state and team/resource availability.
- A planning product packet view for all documents/forms tied to an operational period.
