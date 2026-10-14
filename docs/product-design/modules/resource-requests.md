# Resource Requests

## Purpose

Manage requests for resources or support needs from draft through review, approval, assignment, fulfillment, delivery/closure, and printed/exported documentation.

## Users

- Logistics staff receiving and fulfilling requests.
- Section staff requesting resources.
- Approvers/reviewers.
- Planning/finance staff reviewing status, audit, fulfillment, and documentation.

## Current Features

- Working: Full Resource Request workspace opens as a split view with request list on the left and detail panel on the right.
- Working: Request list includes filters, table columns for title, priority, status, needed by, and updated time.
- Working: Request list supports New Request, Submit, Approve, Deny, Cancel, multi-select bulk actions, and double-click/open.
- Working: Detail panel supports title, priority, current status, requesting section, needed by, delivery location/facility, comms requirements, links, and justification.
- Working: Items tab supports request line items.
- Working: Approvals tab shows approval timeline and actions for Submit, Review, Approve, Deny, and Cancel.
- Working: Fulfillment tab supports assigning fulfillment and updating fulfillment status/ETA.
- Working: Audit tab shows request audit entries.
- Working: Print actions exist for ICS-213 RR and summary sheet outputs.
- Working: Facility picker is integrated for delivery facilities.
- Working: Request lifecycle is modeled for draft, submitted, reviewed, approved, assigned, in transit, delivered, closed, denied, cancelled, and partial/failed fulfillment states.
- Partial: Older simple `RequestsPanel` still exists and explicitly says the legacy resource-request board has been removed.
- Planned/README: Cost tracking and inventory reservation are listed as future enhancements.

## Core Workflows

- Create a new resource request.
- Add/edit request header information and requested items.
- Save a draft request.
- Submit a request for review.
- Review, approve, deny, or cancel a request.
- Assign fulfillment to supplier/team/vehicle/destination/ETA.
- Update fulfillment status and ETA.
- View approval history and audit history.
- Print/export an ICS-213 RR or summary sheet.
- Filter and bulk-process requests from the list.

## Build Status

Working/partial. The new Resource Request workspace is a real feature with list/detail, approvals, fulfillment, audit, and print outputs. The main gap is less about existence and more about integration: how requests reserve resources, create assignments, affect resource status, and connect to finance/inventory is not fully designed.

## Screens And UI Inventory

- Resource Request split workspace.
- Resource Request List panel.
- Filters bar with status/priority/search-style controls.
- Request list table.
- Bulk action button bar.
- Resource Request Detail panel.
- Header row: title, priority, status.
- Details tab.
- Items tab.
- Approvals tab.
- Fulfillment tab.
- Audit tab.
- Note dialog.
- Assign fulfillment dialog.
- ETA/status update dialog.
- Print ICS-213 RR action.
- Print Summary action.
- Older simple Resource Requests placeholder panel.

## Links To Other Modules

- Logistics Dashboard counts open requests and pending approvals.
- Facilities can be selected as delivery destinations.
- Resource Status Board should eventually reflect resources sourced or assigned through request fulfillment.
- Teams may receive fulfilled resources.
- Vehicle/aircraft/equipment inventory should eventually support sourcing or reservation.
- Finance may eventually consume cost data.
- Planning/ICS documentation uses printed/exported request outputs.

## Desktop Experience

Desktop has a full request management workspace. It is list/detail oriented, with request selection on the left and detailed editing/status tabs on the right.

## Mobile Experience

No clear mobile resource request workflow is visible in the current app. Mobile team management can assign resources to a team, but that is not the same as creating or approving a resource request.

## Current Gaps

- Request fulfillment is not yet clearly tied to inventory reservation or resource-status lifecycle.
- Cost tracking is not implemented.
- The older placeholder request panel should be removed or clearly routed away from.
- The customer-visible difference between requested item, fulfillment record, assigned team/vehicle, and tracked resource needs design.
- The list/detail UI is functional but may need standardization with other table/detail workspaces.

## Design Questions

- Should approved requests automatically create resource status rows or assignments?
- What is the handoff from approval to logistics sourcing?
- Should resource requests reserve existing inventory, create new procurement needs, or both?
- How should partial fulfillment appear to requesters and logistics staff?
- Which request actions should require notes, identity, or role-based authorization?
- Should mobile users be able to submit requests from the field?

## Future Design Ideas

- Design an end-to-end request-to-resource workflow.
- Add inventory reservation and cost tracking.
- Add a requester-facing simplified request form.
- Add clearer dashboard widgets for pending approval, awaiting sourcing, in transit, and partially fulfilled requests.
