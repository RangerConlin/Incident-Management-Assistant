# Teams

## Purpose

Manage operational teams as deployable groups of people and assets, including team identity, type, leader, members, vehicles, equipment, aircraft, status, task linkage, logistics state, and mobile team-level workflows.

## Users

- Operations staff building and assigning teams.
- Planning staff reviewing team capability and readiness.
- Logistics/check-in staff checking in team packages.
- Team leaders and field users using mobile team management.
- Safety staff reviewing team status, location, and assistance indicators.

## Current Features

- Working: Desktop Team Detail window exists as a large widget-based editor.
- Working: Team identity fields include name, type, leader, phone, status, linked task, assignment, location, assigned unit, and current task actions.
- Working: Desktop team status can be changed and appears connected to activity logging/signaling.
- Working: Desktop team detail has tabs for Personnel, Vehicles, Equipment, Logistics, Logs, and Safety.
- Working: Desktop team personnel table supports adding/removing members, role selection, leader/PIC/medic flags depending on team type, and member detail affordances.
- Working: Desktop vehicle/equipment/aircraft assignment dialogs search available assets and can open check-in if an asset/person needs to be added.
- Working: Desktop team logistics area tracks check-in status, linked resource request status, and logistics resource rows.
- Working: Desktop team logs include ICS-214-related refresh/export/edit/delete/open actions.
- Working: Desktop team check-in can keep a team together or disband it after check-in.
- Working: Mobile Team Management screen has tabs for Members, Resources, and Check-In.
- Working: Mobile can add, edit, and remove team members; adding a member searches incident personnel and writes check-in/team membership.
- Working: Mobile can add, edit, and remove team resources for vehicles, aircraft, and equipment.
- Working: Mobile Check-In tab highlights checked-in assigned members.
- Partial: Team location tracking is planned/design-documented, and mobile tracking service code exists, but the design doc says the full desktop GIS map/panel is not yet built.
- Partial: Team concepts appear in operations, logistics, check-in, GIS planning, mobile, and tasking; the user-facing model needs consolidation.

## Core Workflows

- Create or open a team detail record.
- Set team type and operational status.
- Assign or change a team leader.
- Add/remove personnel from the team.
- Set member roles and special flags.
- Add/remove vehicles, aircraft, and equipment.
- Link or unlink a task.
- View or change team logistics/check-in status.
- Review team logs/activity.
- On mobile, manage current team members/resources and review checked-in members.
- Check in a team as a package, either preserving the team or disbanding it.

## Build Status

Partial but substantial. Teams are one of the most feature-rich areas, but the feature surface is distributed and dense. Desktop has a powerful Team Detail window. Mobile has a focused team management workflow. Team check-in and team location planning create important cross-module behavior that needs a cleaner design map.

## Screens And UI Inventory

- Desktop Team Detail window.
- Team header/details area.
- Needs Assistance button.
- Team type selector.
- Team status selector.
- Linked task field and Link/Unlink/View Task actions.
- Assignment and location fields.
- Assigned unit selector.
- Personnel tab with member table and Add Personnel/Detail actions.
- Vehicles tab with asset table and Add Vehicle action.
- Equipment tab with equipment table and Add Equipment action.
- Logistics tab with check-in status, linked request status, refresh/link request actions, and resource table.
- Logs tab with ICS-214 table and refresh/export/edit/delete/open full log actions.
- Safety tab.
- Add Personnel to Team dialog.
- Add Vehicle to Team dialog.
- Add Equipment to Team dialog.
- Select Task to Link dialog.
- Team Check-In confirmation dialog.
- Mobile Team Management screen.
- Mobile Members tab.
- Mobile Resources tab.
- Mobile Check-In tab.
- Mobile add member search dialog.
- Mobile member edit dialog.
- Mobile resource picker/edit dialogs.

## Links To Other Modules

- Personnel supplies team members, leaders, medics, and profile/contact data.
- Check-in records team member incident status and supports team package check-in.
- Tasking links teams to tasks and tracks team assignment status.
- Logistics/resource status tracks assets assigned to teams.
- Resource requests may link to team logistics needs.
- GIS/location tracking is planned around one current location per team.
- ICS-214/logging records team status and assignment events.
- Mobile uses the selected team as a primary incident context.

## Desktop Experience

Desktop has the deepest team experience. The Team Detail window is effectively a team workbench: identity/status at the top, then tabbed member, asset, logistics, log, and safety sections. It is powerful, but dense.

## Mobile Experience

Mobile provides a narrower team-management surface for the currently selected team. It supports member and resource management and a checked-in member view. Mobile also treats the team as part of the session context selected when joining an incident.

## Current Gaps

- Team design spans operations, logistics, check-in, tasking, GIS, and mobile, but the product model is not yet documented in one place.
- Desktop Team Detail appears very dense and may need workflow grouping before UI standardization.
- It is not yet clear which team edits should be available on mobile versus desktop-only.
- Team location tracking is conceptually designed but appears only partially implemented.
- Team status, check-in status, resource status, task assignment status, and assistance status may be confusing without a unified state model.
- Some team detail naming still reflects older UI assumptions, which makes the current design boundary harder to read.

## Design Questions

- What is the canonical team lifecycle from creation through demobilization?
- Which status fields should be separate, and which should be merged or visually grouped?
- Should team check-in be a logistics workflow, an operations workflow, or both?
- Should mobile users be allowed to change membership/resources, or should mobile be limited to status and field updates?
- How should teams, tasks, resource requests, and assets be linked in the UI?
- What should happen to a team's task/resource links when the team is disbanded?

## Future Design Ideas

- Create a team lifecycle diagram that separates operational status, logistics check-in status, assignment status, and assistance/safety state.
- Redesign Team Detail around clearer sections: identity, staffing, assets, assignment, logistics, safety, activity.
- Make mobile team management explicitly field-focused: roster, resources, status, location/tracking, and assigned work.
- Use the team design as the bridge between tasking, check-in, logistics, and GIS.
