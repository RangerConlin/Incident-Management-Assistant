# Command

## Purpose

Give incident leadership a current command picture and maintain the command-level records that define the incident.

Command covers the Incident Commander dashboard, incident identity/overview, incident objectives, command/staff organization, situation reports, and handoffs into IAP/planning, resource requests, tasking, logistics, communications, and maps.

## Users

- Incident Commander and command staff monitoring the overall incident.
- Section chiefs reviewing current work, resource pressure, and operational-period status.
- Planning staff maintaining objectives, SITREPs, and planning products.
- Operations staff receiving objective-linked tasks and maintaining section structure.
- Logistics staff responding to command-level resource request shortcuts and resource pressure.
- Mobile field users who need incident identity, operational period, and team context but not full command editing.

## Current Features

- Incident Dashboard / IC Overview with incident name, number, status, ICP location, incident commander field, next meeting field, operational-period selector, live clock, refresh controls, and quick actions.
- Dashboard panels for team status, tasks due soon, critical alerts, geographic snapshot, and KPI strip.
- Dashboard quick actions for New Objective, Resource Request, Open IAP, alert/team/task/comms/logistics/planning destinations, and expanded map.
- Dashboard explicitly leaves unbacked metrics blank rather than inventing values; personnel, leads, and safety issue KPIs currently show as unavailable when no data source is wired.
- Incident Objectives workspace with objective cards, search, new objective, new-from-template, manage templates, clone from previous operational period, reorder guidance, quick status, duplicate, complete/cancel, ICS-202 export, and print preview.
- Objective detail dialog with overview, linked strategies/work assignments, linked tasks, narrative, log, task creation, Tactics and Resources Planner shortcut, and ICS-202 snippet/export behavior.
- Incident Organization Management panel with command/staff organization tree, assigned personnel table, personnel pool search, add/edit/deactivate positions, templates, assignment workflow, and prepare ICS 203 / ICS 207 actions.
- Assignment dialog supports checked-in personnel, database search, and new person entry, with primary/deputy/assistant-style assignment choices.
- Operations Section Organization window for building branch/division/group/position structure under Operations, assigning personnel, and assigning resources.
- SITREP / ICS-209 workspace with Current SITREP, Changes / Events, Operational Summary, Distribution, and Archive tabs.
- SITREP workflow supports new SITREP, quick SITREP/duplicate, refresh from modules, save draft, approve, export text, archive, event management, operational summary insertion, distribution records, and duplicate-as-next-SITREP from archive.
- Incident Overview panel implementation exists for editing incident name, number, type, status, ICP facility, start/end time, description, and training flag.
- Mobile can load/select an incident and team, start an incident session, and show incident name, operational period, team name, and team status in the shared header.

## Core Workflows

- Open the Incident Dashboard to review team state, upcoming tasks, alerts, map snapshot, resource request counts, and operational-period context.
- Use command quick actions to open objectives, resource requests, IAP, alerts, tasks, communications, logistics, and map views.
- Create or update incident objectives, optionally from templates or prior operational periods.
- Link objectives to strategies/work assignments and tasks through objective detail and planning workflows.
- Maintain the incident organization chart, assign personnel into command/staff/section positions, and prepare organization-form outputs.
- Maintain Operations Section structure separately when branch, division, group, position, personnel, and resource assignments need more detail.
- Create and maintain SITREPs, collect significant events, refresh operational summaries from modules, approve/distribute/archive reports, and duplicate prior reports for the next update.
- Mobile users choose an incident/team and then consume command context through the app header and field dashboard.

## Build Status

Partial but important and fairly broad.

The Command module has several real desktop workspaces: IC Overview, Incident Objectives, Incident Organization, Operations Section Organization, and SITREP. These give command staff meaningful current-state control over objectives, organization, reports, and high-level operational awareness.

The module is also uneven. Some dashboard panels are intentionally placeholders, including pending approvals, section health, operational-period readiness, and recent major activity. Some KPI fields are deliberately blank because the backing data source is not available. The Incident Overview edit panel exists, but the public factory currently returns a simpler placeholder panel, so the active menu wiring should be verified before treating incident overview editing as user-accessible.

Mobile has command context but not command management. It lets a user choose the incident and team and then carries incident/operational-period/team context through the field experience.

## Screens And UI Inventory

- Desktop: Incident Dashboard / IC Overview.
- Desktop: Incident Overview placeholder factory.
- Desktop: Incident Overview edit panel implementation.
- Desktop: Incident Objectives panel.
- Desktop: Objective Detail dialog.
- Desktop: Objective Template Picker dialog.
- Desktop: Objective Templates manager, owned by Planning but opened from Command.
- Desktop: Incident Organization Management panel.
- Desktop: Unified Assignment dialog.
- Desktop: Organization Templates dialog.
- Desktop: Operations Section Organization window.
- Desktop: SITREP / ICS-209 panel.
- Desktop: Significant Event dialog.
- Desktop: Distribution Record dialog.
- Desktop: IAP Builder entry point, delegated to Planning.
- Mobile: Incident Picker screen.
- Mobile: shared Incident Header bar.
- Mobile: Field Dashboard command context through incident name, operational period, team name, and team status.

## Links To Other Modules

- Planning: objectives, objective templates, operational periods, tactics/resources, IAP builder, and work assignments all cross the Command/Planning boundary.
- Tasking: objectives can show and create linked tasks; dashboard shows due tasks; command quick actions open task boards.
- Teams: dashboard team status and alerts depend on checked-in team state.
- Check-In: dashboard team availability and mobile join flow depend on checked-in teams/personnel.
- Logistics: dashboard resource request counts and shortcuts connect to resource requests and logistics workspaces.
- Resource Requests: command has quick access to create and review resource requests.
- GIS/Maps: dashboard includes a geographic team snapshot and map expansion shortcut.
- Communications: command quick actions open communications plan surfaces.
- Forms: objectives, organization, SITREP, IAP, ICS-202, ICS-203, ICS-207, ICS-209, and related exports are all command/planning product outputs.
- Safety and Intel: dashboard has placeholder KPIs for safety issues and open leads; task/objective/SITREP workflows can reference safety and intel information indirectly.
- Personnel: incident organization assignment relies on checked-in personnel, database search, and new person creation.

## Desktop Experience

Desktop is the command workbench.

The Incident Dashboard is designed as the commander's live operating picture. It combines the incident identity band, operational-period picker, map snapshot, team state, urgent alerts, tasks due soon, quick actions, and a KPI strip. Several dashboard areas are intentionally honest placeholders where the product does not yet track the needed concept.

Objectives and organization are more administrative but still operationally important. Objectives use a card-based list and detail dialogs, while organization uses a tree/table layout to assign people to positions and prepare organization forms. SITREP uses a five-tab report workspace, which is appropriate for a document/reporting workflow but visually different from the dashboard and objectives surfaces.

The module needs UI standardization across these surfaces. Command currently mixes card dashboards, tree/table organization editing, report tabs, dialogs, and placeholder panels. That is not inherently wrong, but shared language, status chips, toolbar behavior, table standards, and form/export patterns should be tightened.

## Mobile Experience

Mobile does not currently provide command editing or command dashboards.

The mobile command role is context-setting: users select an incident and team, then carry incident name, operational period, team identity, and team status through the field dashboard, task list, communications, check-in, and related mobile screens.

This is likely the right scope for field users, but a future supervisor/mobile-command mode would need to be designed separately rather than quietly added into the field UI.

## Current Gaps

- Incident Overview editing appears implemented but may not be wired to the active Command menu path.
- Dashboard pending approvals, section health, operational-period readiness, recent activity, personnel checked-in, open leads, and safety issue tracking are incomplete or placeholder-backed.
- Command dashboard status colors and some SITREP styling include local hardcoded colors in code; future UI standardization should align them with shared theme tokens.
- Command, Planning, and Operations share objectives/work assignments/tasks, but the customer-facing vocabulary and lifecycle are not yet fully clear.
- SITREP has a strong workspace, but export/distribution/form-readiness boundaries need verification.
- Incident organization can prepare ICS 203/207, but the readiness state of those outputs should be documented.
- Mobile has no command/supervisor mode.
- Approval concepts appear in dashboard placeholders but do not yet have a clear product model.

## Design Questions

- What is the customer's mental model for Command versus Planning: who owns objectives, operational periods, IAP, and approval?
- Should the Incident Dashboard be the first screen for command staff, and should it become the app-level incident home?
- Should Incident Overview editing be a command-level screen, an admin/settings screen, or part of incident setup?
- What is the canonical approval workflow: objectives, IAP products, SITREPs, resource requests, tasks, communications plan, or all of these?
- How should incident organization, operations section organization, teams, and checked-in personnel relate without creating duplicate assignment concepts?
- Which command metrics must be real before the dashboard is considered production-ready?
- Should mobile ever support command functions, or should it stay field-oriented with only incident context?

## Future Design Ideas

- A unified Command Home that combines dashboard, incident overview, current operational period, command staff, open approvals, and current products.
- A command readiness checklist for operational period changeover: objectives approved, organization staffed, IAP ready, resource gaps reviewed, SITREP status known, safety/communications products reviewed.
- Clear objective-to-work-assignment-to-task traceability from Command without requiring the user to know which module owns each step.
- Incident organization health indicators showing unstaffed required positions, duplicate assignments, expired shifts, and missing contact information.
- A command product packet view for current ICS-202, ICS-203, ICS-207, ICS-209, IAP, communications, safety, and related outputs.
- A supervisor mobile mode with read-only command dashboard, team/task status, urgent alerts, and SITREP summaries.
