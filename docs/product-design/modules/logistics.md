# Logistics

## Purpose

Coordinate incident support resources: checked-in resources, personnel availability, vehicles, aircraft, facilities, resource requests, team assets, logistics dashboarding, demobilization/returns, and logistics-facing accountability.

## Users

- Logistics Section Chief and logistics staff.
- Check-in/resource-unit staff.
- Operations staff assigning teams and resources.
- Planning staff reviewing readiness and demobilization state.
- Field/team users managing team resources from mobile.

## Current Features

- Working: Main Logistics workspace opens with Dashboard and Checked-In Resources tabs.
- Working: Logistics Dashboard shows KPIs for open requests, approvals pending, check-ins today, vehicles ready, facilities status, alerts, top actions, resource snapshot, supply/comms placeholders, and demob queue.
- Working: Resource Status Board tracks incident resources across personnel, vehicles, aircraft, and equipment.
- Working: Resource Status Board supports status/resource type/assignment/ETA/search filters, sorting, add/edit, context-menu status changes, source-record opening, and team opening when assigned.
- Working: Logistics Personnel Manager shows incident personnel roster with search/status filters, availability summary, status changes, history, selected-person detail opening, and check-in opening.
- Working: Vehicle Inventory panel exists with searchable/filterable table, pagination, detail pane, import wizard, export flow, keyboard shortcuts, tags, status pills, sync/resync controls, and edit dialog integration.
- Working: Aircraft Inventory window exists with search, filters, sort, pagination, import/export, row status colors, assignment to team, status setting, print summary, history/log affordance, and delete.
- Working: Facilities Manager exists for facility records, filters, search, manager picker, geocode/reverse-geocode, primary facility flag, function tags, served sections, and notes.
- Working: Resource Request workspace exists with list/detail split view, filters, approval actions, items, fulfillment, audit, and print/export actions.
- Working: Desktop team detail and mobile team management can assign vehicles, aircraft, and equipment to teams.
- Partial: Supply and comms-cache portions of the Logistics Dashboard are visible as "No data" placeholders.
- Partial: Some older placeholder panels still exist for assignment dashboard and legacy request panel, but the newer resource request workspace is the active fuller workflow.

## Core Workflows

- Review logistics dashboard status for requests, resources, facilities, check-ins, alerts, actions, and demob queue.
- Track all checked-in or pending incident resources on the Resource Status Board.
- Add or edit a tracked resource, including status, ETA, assignment, location/facility, and notes.
- Open assigned team or source record from a resource row.
- Manage logistics-facing personnel status and view status history.
- Manage vehicle inventory and import/export vehicle records.
- Manage aircraft inventory, assignment, status, capabilities, maintenance notes, and exports.
- Manage facilities and geocoded locations used by logistics/request/resource workflows.
- Create, review, approve, assign, fulfill, audit, and print resource requests.
- Use Resource Requests either as quick operational intake or as a full formal ICS-213RR workflow with approvals, fulfillment, procurement/finance metadata, and exportable documentation.
- Assign resources to teams from desktop team detail or mobile team management.

## Build Status

Substantial but uneven. Logistics has several real, usable workspaces and some of the more mature operational panels in the app. It also has visible placeholders and overlapping concepts: resource status, check-in, inventory, teams, facilities, and requests all touch the same resources from different angles.

## Screens And UI Inventory

- Main Logistics workspace tab container.
- Logistics Dashboard.
- Checked-In Resources / Resource Status Board.
- Resource Details dialog.
- Logistics Personnel Manager.
- Personnel Status History dialog.
- Vehicle Inventory panel.
- Vehicle edit dialog.
- Vehicle import wizard.
- Vehicle export dialog.
- Aircraft Inventory window.
- Aircraft detail window/pane.
- New Aircraft dialog.
- Assign Aircraft to Team dialog.
- Set Aircraft Status dialog.
- Import Aircraft dialog.
- Facilities Manager panel.
- Resource Request list/detail workspace.
- Legacy Resource Requests placeholder panel.
- Legacy Assignments placeholder panel.
- Check-in windows and Resource Check In workbench, covered in [Check-In](check-in.md).

## Links To Other Modules

- Check-in feeds personnel/resource availability into logistics status.
- Personnel provides responders for check-in, logistics roster, facility managers, and team membership.
- Teams consume vehicles, aircraft, equipment, personnel, and logistics status.
- Tasking depends on teams/resources being available and assigned.
- Resource requests can lead to fulfillment, assignment, and tracked resource changes.
- Resource requests also provide the formal ICS-213RR path for documented requests, including approval, fulfillment, procurement/finance metadata, and printed/exported packets when the incident requires that level of process.
- Facilities are used by resource status, delivery locations, check-in/resource movement, and request delivery.
- Mobile team management can assign resources to teams.
- Planning/demobilization depends on resource status and preparation for demob.

## Desktop Experience

Desktop is the primary logistics experience. It contains the dashboard, resource status board, personnel manager, inventory management, facilities, resource requests, check-in, and team asset assignment. The desktop logistics surface is powerful but spread across multiple panels.

## Mobile Experience

Mobile logistics is mostly embedded in team management today. A mobile user can manage team resources for the selected team, choosing from vehicle, aircraft, and equipment catalogs and updating assignment/resource status. Mobile does not yet appear to expose the broader logistics dashboard, request workflow, facilities manager, or inventory administration.

## Current Gaps

- Logistics has multiple overlapping resource concepts: inventory records, checked-in resources, resource status rows, team assets, request fulfillment, and check-in records.
- Supply and comms-cache dashboard areas are placeholders.
- Legacy placeholder panels still exist and may confuse the current product map.
- Vehicle and aircraft inventories have their own UI patterns and status vocabularies that may not fully align with Resource Status Board statuses.
- Facility manager status feedback styling should eventually align with shared UI/theme standards.
- Resource assignment can happen from team detail, mobile team management, resource status, and request fulfillment; the canonical workflow needs design.
- Needs verification: how equipment inventory is managed as a first-class logistics screen outside team/resource-status workflows.

## Design Questions

- What is the canonical object: inventory item, checked-in resource, resource-status row, or team asset?
- Should Resource Status Board be the logistics source of truth for all active resources?
- Which logistics workflows should be dashboard-driven versus table/detail driven?
- How should vehicle/aircraft/equipment inventory relate to check-in and resource status?
- Should resource requests create or reserve resource-status rows automatically?
- When should logistics users stay in the quick request path versus convert a request into the full formal ICS-213RR packet?
- Which logistics workflows should be exposed to mobile field users?
- How should facilities appear across check-in, requests, resource status, maps, and planning?

## Future Design Ideas

- Build a logistics lifecycle diagram: requested, approved, sourced, enroute, checked in, assigned, in use, preparing for demob, returned/demobilized.
- Standardize resource status labels across resource status, check-in, team assets, vehicle inventory, aircraft inventory, and requests.
- Decide whether vehicle, aircraft, and equipment deserve separate design docs or remain subareas of Logistics.
- Replace legacy placeholder panels with links to the active workspaces or remove them.
- Turn the Logistics Dashboard into a true navigation hub for the logistics section.

## Web Experience

The web Logistics home (`/logistics`) joins existing shared API reads for requests,
checked-in resources and facilities. It shows open/awaiting-approval requests, resources
checked in today, available vehicles, active facilities, needs due within 24 hours and
the preparing-for-demobilization queue. Failed data sources show unavailable totals.
Existing Resource Status and Check-In pages remain the resource entry points.

Resource Requests now provide quick intake, route-based details, separate line-item saves,
approval actions with denial notes, supported request lifecycle transitions, multiple
fulfillment records with assignment/destination/ETA/status updates, approval/audit history,
and browser-printable summaries. Submitted critical header fields are locked; closed
requests are read-only and denied/cancelled requests can be reopened. Unsaved item edits
block section/lifecycle changes until saved or discarded. Filled ICS-213RR PDF downloads are available through the shared export API, alongside
the browser-printable request summary. Signatures and unrecorded fields remain blank.

Facilities provide searchable/filterable lists and create/update/delete detail pages,
primary-by-type selection, personnel manager search, contact details, addresses/coordinates,
function tags and served sections. The server enforces the primary facility constraint.
The browser edits canonical fields only and preserves existing metadata on full PUT saves.
Geocoding services and standalone vehicle/aircraft/equipment catalog administration remain
outside this browser implementation; the existing Check-In catalog lookup is available.

Supply/comms stock levels still lack backing data. No stock estimates or inventory
reservations are generated. Request fulfillment and the overall request status are separate
records: updating one does not automatically advance the other.
