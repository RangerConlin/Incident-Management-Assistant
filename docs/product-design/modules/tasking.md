# Tasking

## Purpose

Define, assign, monitor, and close operational work during an incident.

Tasking is where incident objectives and work assignments become concrete field work. It connects plans, teams, personnel, vehicles, aircraft, locations, safety notes, communications, intelligence, debriefing, logs, and generated forms around a single assignment.

## Users

- Operations staff creating and supervising field assignments.
- Planning staff linking tasks back to objectives and work assignments.
- Team leaders and field users viewing their current assignment on mobile.
- Logistics staff coordinating resources assigned to tasks.
- Intelligence, safety, and command staff who need task-linked findings, hazards, logs, and debriefs.

## Current Features

- Desktop task status board with filters, column configuration, status presets, context actions, open-detail behavior, and new-task entry.
- Large desktop Task Detail window covering task identity, title, location, priority, status, assigned team, assignment narrative, planning links, teams, personnel, vehicles, communications, safety, debriefing, attachments, forms, intelligence, and logs.
- Task detail supports geocoding, GIS object linkage, planning linkage refresh/link/send-to-liaison actions, task narrative quick entry, team assignment controls, GAR rollup display, air and ground assignment detail sections, form generation, and log exports.
- Operations glance dashboard widget exists with active task KPIs, due-soon items, team assignment counts, blocking/debrief indicators, top tasks, team snapshot, communications snapshot, and shortcut actions.
- Mobile task list shows live tasks with filters for all tasks, my team, open tasks, and completed tasks.
- Mobile task cards show task number, title, type, status, location, priority, and "My Team" indication.
- Mobile task detail shows type, priority, status, location, and narrative/notes preview.
- Mobile field dashboard highlights the current task, task location, team status, assignment reference, and task narrative feed.

## Core Workflows

- Create or open a task from the desktop operations/task status workspace.
- Fill task identity, type/category, priority, status, location, narrative, and assignment details.
- Link the task to a planning work assignment when planning context exists.
- Assign one or more teams, mark a primary team, and review assigned personnel, vehicles, and air/ground details.
- Confirm already-available task resources directly on the task, or escalate an unmet need into Resource Requests only when sourcing/tracking is needed.
- Add safety, communication, intelligence, forms, attachments, and log records as the task evolves.
- Use desktop task status views to monitor work, filter by operational state, and change status quickly.
- Use mobile to find assigned tasks, view current assignment context, monitor status, and read narratives.

## Build Status

Partial but substantial.

The desktop Task Detail window is one of the most built-out operational surfaces in the app. It is broad enough to act as the assignment command center for a task. The task status board also appears to be a usable supervisory view.

Mobile currently supports task awareness more than task execution. The task list and task detail views are present, and the field dashboard has useful current-task context, but the mobile action buttons for acknowledge, en route, on scene, and complete are still placeholder/not-available interactions.

There is also a wiring question around the desktop Operations Dashboard: a rich `OpsGlanceWidget` exists, while the operations window factory still returns a placeholder dashboard. The actual menu/runtime path should be verified before deciding whether the dashboard is built, orphaned, or partially integrated.

## Screens And UI Inventory

- Desktop: Task Status Panel.
- Desktop: Task Detail Window.
- Desktop: Operations Glance/Dashboard widget.
- Mobile: Task List screen.
- Mobile: Task Detail screen.
- Mobile: Field Dashboard / MDT home screen.
- Related desktop task tabs: Narrative, Planning, Teams, Assignment Details, Safety, Communications, Debriefing, Attachments/Forms, Intel, Log.

## Links To Other Modules

- Planning: tasks can be linked to objectives/work assignments and surfaced from the tactics/resources planning flow.
- Teams: tasks assign teams, track primary team, show team status, and pull team resources into the assignment.
- Personnel: task team/personnel tabs expose assigned people and their roles.
- Logistics: vehicles, aircraft, resource status, and resource requests can support task fulfillment. Tasking should not require a Resource Request when the needed resources are already available and can simply be assigned or acknowledged.
- GIS/Mapping: task locations can be geocoded and linked to GIS objects.
- Communications: task communications channels are managed from the task detail workflow.
- Safety: hazards, safety notes, and GAR-style risk rollups attach to task work.
- Intelligence: task detail can create/open leads, intel items, and subject-related records.
- Documentation/Forms: task forms, ICS-214-style logs, exports, and attachments live inside the task detail workflow.
- Mobile: field task views depend on team membership and current incident context.

## Desktop Experience

Desktop is the primary authoring and supervision surface for tasking.

The task status board acts as the overview workspace: users can filter, sort, configure visible columns, open details, create tasks, and change statuses from context menus. The Task Detail window is the full authoring surface and is intentionally dense. It brings together planning context, team assignments, assignment detail, safety, communications, debriefing, forms, intelligence, and logs.

The desktop experience currently favors comprehensive control over simplicity. It is useful for staff roles, but it will need UI standardization so related concepts such as status, assignment, team resources, logs, and planning links feel consistent with logistics and planning screens.

## Mobile Experience

Mobile is focused on field awareness.

Users can see a task list, filter to their team's work, open a task, and review key details. The field dashboard also gives a more operational current-task view with assignment metadata, task location, narrative feed, team status controls, and shortcut actions.

Mobile task status actions are not complete yet. The visible acknowledge/en route/on scene/complete buttons currently indicate that those actions are unavailable, so mobile should be treated as read-mostly for task state until that workflow is finished.

## Current Gaps

- Mobile task lifecycle updates are visible but not implemented.
- Operations dashboard wiring needs verification because placeholder and richer dashboard implementations both exist.
- The boundary between a planning work assignment and an operations task is conceptually strong, but the user-facing handoff needs clearer language and workflow.
- Status vocabulary should be standardized across task detail, task board, mobile task cards, teams, logistics, and planning.
- Task detail has many linked tabs; the information architecture may need tightening before adding more features.
- It is unclear which task-linked forms and exports are production-ready versus partially generated.
- Mobile field actions such as hazard reports, forms, more actions, and some dashboard shortcuts are still incomplete or marked coming soon.

## Design Questions

- What is the canonical task lifecycle from draft through assigned, active, completed, reviewed, and archived?
- Which task fields are required before a task can be assigned to a team?
- Should mobile users be able to change task status directly, or should those changes require team leader role checks?
- How should planning work assignments, operations tasks, and resource requests appear together so users understand the handoff?
- What is the fastest task-level path for "we have the needed resources; continue" without opening Logistics?
- Which task tabs are essential for field operations, and which are specialist/staff-only?
- Should task logs, team logs, and ICS-214 logs remain separate views or become one filtered activity timeline?
- What must happen when a task is completed: debrief required, resource release, team status change, forms generated, planning objective updated?

## Future Design Ideas

- A clearer task lifecycle rail showing assignment state, team state, required closeout steps, and missing information.
- Mobile task action flow for acknowledge, travel, arrival, pause/block, complete, and debrief.
- A unified task timeline combining status changes, narratives, team logs, communications, intel links, attachments, and debrief events.
- A simplified dispatcher view for assigning teams/resources to open tasks.
- A planning-to-operations handoff view showing which work assignments have generated tasks and which still need action.
- Role-based task detail layouts so field, operations, planning, intelligence, and safety users see the right level of detail.
