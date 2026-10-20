# Resource Requests

## Purpose

Manage requests for resources or support needs from fast initial intake through review, approval, assignment, fulfillment, delivery/closure, and printed/exported documentation.

Resource Requests should start as a lightweight operational intake tool, especially during initial response. A user should be able to record "Need X by Y at Z" quickly and move on. The same record can later deepen into a managed logistics request or a tracked resource/inventory/finance workflow only when the incident requires that extra structure.

Using this module should never be mandatory for ordinary planning or tasking. If a user is building a work assignment and confirms "I need two X and one Y" from resources already known to be available, they should be able to mark those needs as filled and keep going without creating a Resource Request. Resource Requests are the escalation path for unmet, uncertain, externally sourced, approval-sensitive, or track-worthy needs.

At the same time, the full ICS-213RR workflow should remain a first-class formal path. When a request needs official documentation, formal approval routing, procurement support, cost tracking, signatures, or reimbursement/audit evidence, the module should capture the complete resource-request record rather than only a lightweight note.

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

- Create a quick resource request with minimal required information.
- Add/edit request header information and requested items.
- Save a draft request.
- Submit a request for review.
- Review, approve, deny, or cancel a request.
- Assign fulfillment to supplier/team/vehicle/destination/ETA.
- Update fulfillment status and ETA.
- View approval history and audit history.
- Print/export an ICS-213 RR or summary sheet.
- Filter and bulk-process requests from the list.
- Complete a formal ICS-213RR-style request packet when documentation, procurement, finance/admin, or reimbursement requirements apply.

## Progressive Workflow Principle

The product should not expose "quick", "managed", and "tracked" as separate modes the user must choose. Instead, every request should begin as a quick request and naturally reveal more structure as the user adds information or takes actions.

The module should also be bypassable. Resource needs can live directly on planning work assignments, operations tasks, team assignments, or resource-status records when they are already resolved. The Resource Request workflow is for moments when someone needs help sourcing, approving, delivering, documenting, or tracking the need beyond the local planning/tasking context.

The default path should be:

- Request: capture what is needed, priority, needed-by time, location/facility, and a note.
- Decide: approve, deny, cancel, or mark handled without forcing a full approval package.
- Fulfill: assign an owner/source and optional ETA.
- Close: delivered, closed, cancelled, denied, or no longer needed.

Additional detail should be optional and additive:

- Line items can be added when a one-line request is not specific enough.
- Approval history can be used when the incident needs review discipline.
- Fulfillment records can track sourcing, ETA, delivery, partial delivery, or handoff.
- Resource-status links can be added when a request affects a real team, vehicle, aircraft, equipment item, or personnel resource.
- Inventory reservation, procurement, and finance/cost fields should appear only when those workflows are relevant.
- Formal ICS-213RR fields, signatures, approval routing, requisition/purchase-order references, attachments, and finance/admin fields should be available for requests that require official processing.

The user should never have to complete a long form or step through a full lifecycle just to capture an urgent initial-response need. Logistics staff can enrich the request later without forcing the requester to understand the full backend model.

## When To Use A Resource Request

Use a Resource Request when:

- The need cannot be filled immediately from known available resources.
- Logistics, command, finance, or an outside supplier must take action.
- Approval, denial, delivery, ETA, partial fulfillment, or audit history matters.
- The request needs to appear in logistics dashboards or printed/exported ICS-213 RR documentation.

Do not require a Resource Request when:

- A planner is listing resource needs for a work assignment.
- Operations is assigning already-available people, teams, vehicles, aircraft, or equipment to a task.
- A team leader is confirming resources they already have.
- The only needed action is "yes, those resources are available; continue."

In those cases, the user should be able to record the requirement and mark it filled, assigned, or acknowledged in the originating workflow. Creating a Resource Request should remain an available action from that context, not a required detour.

## Formal ICS-213RR Path

The formal path should support the complete resource-request packet for incidents and agencies that need it. This includes:

- Requester, requesting section/unit, contact information, priority, needed-by time, delivery location/facility, and justification.
- One or more requested line items with quantity, unit, description/type, and notes.
- Approval routing and history, including section/command/logistics/finance review when configured for the incident.
- Denial, return-for-information, cancellation, partial fulfillment, and closeout reasons.
- Supplier/source, assigned team/vehicle/resource, destination, ETA, delivery status, and fulfillment notes.
- Requisition number, purchase order number, estimated cost, actual cost, funding/cost code, vendor/supplier reference, receipt/attachment links, and finance/admin review fields when available.
- Print/export output that can produce an ICS-213RR-style packet or summary sheet from the same request record.

Finance/Admin is currently underdeveloped, so the Resource Request design should not depend on a complete Finance module being present before the formal logistics flow works. Cost/procurement fields can initially live on the request as optional finance-facing metadata, then later synchronize or link to Finance/Admin expense, funding, approval, and reimbursement records as that module matures.

## Formal Flow Current Evaluation

Current formal-flow coverage is partial but real:

- Present: API-backed `resource_requests` collection with request header, items, approvals, fulfillments, audit, lifecycle status, versioning, and canonical Mongo storage.
- Present: Desktop list/detail workspace with Details, Items, Approvals, Fulfillment, Audit, Print ICS-213 RR, and Print Summary.
- Present: Planning work-assignment resource requirements can create and link a Logistics Resource Request / ICS-213RR record when a resource need must be escalated.
- Present: FEMA and ICS Canada ICS-213RR templates exist in the forms system, and the resource-request export builder can generate an ICS-213RR PDF from a request record.
- Present but shallow: approval actions support submit, review, approve, deny, cancel, and reopen-like status flow, but they are generic actions rather than named section/command/logistics/finance approval steps.
- Present but shallow: fulfillment supports supplier ID, team ID, vehicle ID, destination, facility, ETA, status, and note, but not supplier contact details, requisition/order numbers, procurement method, receipt tracking, or finance review.
- Missing: formal requester name/position/contact fields.
- Missing: section-chief approval, logistics representative approval, finance approval, signature/date fields, and configurable approval chain presets.
- Missing: formal ICS-213RR order/procurement fields such as logistics order number, requisition number, purchase order number, supplier/POC contact, suitable substitutes/suggested sources, order placed by, cost-per-line, total estimated cost, total actual cost, funding/cost code, and finance comments.
- Missing: formal completeness/checklist behavior that tells the user whether a request is quick, managed, or complete enough for official ICS-213RR processing.
- Missing: Finance/Admin integration. Finance is not mature enough to own these fields yet, so Resource Requests must carry finance-facing metadata until Finance/Admin can consume it.
- Gap: current PDF mappings populate only part of the ICS-213RR form; many official fields remain blank because the request record does not yet store the necessary data.

## Finished Formal Flow Design

The formal flow should be a progressive expansion of the same request record, not a separate module or duplicate request type. A quick request becomes formal when the user chooses an action such as "Complete ICS-213RR", "Route for approval", "Procure/order", or "Finance review required."

Formal requests should have these sections:

- Intake: title, request number, incident, requester name, requester position, requester contact, requesting section/unit, priority, needed-by time, delivery/reporting location, delivery facility, justification, and special instructions.
- Items: quantity, unit, kind, resource type, detailed description/specifications, suitable substitutes, suggested source, requested arrival, estimated arrival, estimated unit/line cost, actual unit/line cost, and item notes.
- Routing and approvals: current approval route, required approval steps, approver role, approver name/id, action, timestamp, comments, return-for-information reason, denial reason, and final approval state.
- Logistics/order: supplier/source, supplier POC, supplier phone/email, logistics order number, requisition number, purchase order number, order placed by, order placed time, procurement method, delivery status, destination, ETA, fulfillment notes, and partial/failed fulfillment reason.
- Finance/admin: finance required flag, finance reviewer, finance approval timestamp, funding source/code, cost category, estimated total, actual total, reimbursement/export flag, finance comments, receipt/attachment references, and eventual linked finance expense/approval ids.
- Audit and documents: append-only audit events, generated ICS-213RR exports, summary exports, attachments, signatures, and links back to planning work assignments, operations tasks, teams, or resource-status rows.

The formal flow should use configurable approval presets rather than hardcoding one process for every incident:

- None: no approval route; record and fulfill only.
- Operational: requester/section review plus logistics action.
- Command: section approval plus command approval before fulfillment.
- Procurement: logistics approval plus requisition/order fields.
- Finance: logistics approval plus finance review before order or closeout.
- Full ICS-213RR: section/command/logistics/finance route with completeness checks and printable packet readiness.

Completeness should be visible but not punitive:

- Quick: enough to understand the need.
- Ready to Review: requester, section/unit, priority, needed-by, delivery target, justification, and at least one item.
- Ready to Order: approved, source/supplier identified, order/procurement fields filled as required by preset.
- Ready for Finance: estimated/actual costs, funding/cost code, receipt/attachment references, and finance comments where required.
- Ready to Close: fulfillment status resolved, partial/failed reasons handled, required approvals complete, and final packet/export available if needed.

Users should be able to see missing formal fields as a checklist inside the request detail view. The checklist should guide formal completion without blocking quick intake, local resource assignment, or initial-response operations.

## Build Status

Working/partial. The new Resource Request workspace is a real feature with list/detail, approvals, fulfillment, audit, and print outputs. The formal ICS-213RR flow has the core skeleton but not the complete packet: request headers, items, approvals, fulfillment, audit, and PDF export exist, while procurement, finance/admin, formal signatures, configurable approval routes, supplier contact details, and completeness checks remain design/build gaps. The other major gap is integration: how requests reserve resources, create assignments, affect resource status, and connect to finance/inventory is not fully designed.

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
- Formal packet/completeness section is needed but not yet present.
- Procurement/finance section is needed but not yet present.
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
- Planning and Tasking should be able to record resource requirements and confirmed assignments without creating a Resource Request unless the need must be escalated.
- Finance/Admin should eventually consume request cost, procurement, funding, receipt, approval, and reimbursement data, but Resource Requests need enough optional fields to support formal ICS-213RR processing before Finance/Admin is fully mature.

## Desktop Experience

Desktop has a full request management workspace. It is list/detail oriented, with request selection on the left and detailed editing/status tabs on the right.

## Mobile Experience

No clear mobile resource request workflow is visible in the current app. Mobile team management can assign resources to a team, but that is not the same as creating or approving a resource request.

## Current Gaps

- Request fulfillment is not yet clearly tied to inventory reservation or resource-status lifecycle.
- Cost tracking is not implemented.
- The formal ICS-213RR packet shape needs to be defined against the actual printable/exportable output, including which finance/procurement fields are stored now versus linked later.
- Current ICS-213RR export mappings leave many official fields blank because requester, approval, supplier, order, cost, and finance fields are not yet captured.
- Approval actions are generic and do not yet model named section, command, logistics, or finance approval steps.
- No formal packet readiness/completeness checklist exists.
- The older placeholder request panel should be removed or clearly routed away from.
- The customer-visible difference between requested item, fulfillment record, assigned team/vehicle, and tracked resource needs design.
- The list/detail UI is functional but may need standardization with other table/detail workspaces.
- The quick initial-response intake path needs explicit protection so future inventory, approval, procurement, and finance features do not make every request feel heavyweight.
- Planning and tasking workflows need a clear "filled locally / escalate to Resource Request" choice so users can bypass this module when resources are already available.

## Design Questions

- Should approved requests automatically create resource status rows or assignments?
- What is the handoff from approval to logistics sourcing?
- Should resource requests reserve existing inventory, create new procurement needs, or both?
- How should partial fulfillment appear to requesters and logistics staff?
- Which request actions should require notes, identity, or role-based authorization?
- Should mobile users be able to submit requests from the field?
- Which fields are truly required for a quick request, and which should remain optional until logistics staff enrich the record?
- When should the UI reveal advanced tabs or fields: based on status, user role, request complexity, or explicit user action?
- From a work assignment or task, what is the simplest interaction for marking resource needs as filled without creating a Resource Request?
- What conditions should suggest creating a Resource Request from a resource need, without forcing it?
- Which fields are required for a complete ICS-213RR packet, and which are agency-specific optional fields?
- Should finance/procurement fields live directly on the resource request until Finance/Admin matures, or should they be stored as linked draft finance records?
- What approval chain presets are needed: no approval, section approval only, logistics approval, command approval, finance approval, or fully sequential formal approval?

## Future Design Ideas

- Design an end-to-end request-to-resource workflow.
- Add inventory reservation and cost tracking.
- Add a requester-facing simplified request form.
- Add clearer dashboard widgets for pending approval, awaiting sourcing, in transit, and partially fulfilled requests.
- Add a first-class quick-entry workflow for initial response that can later expand into the full list/detail workspace without creating a second kind of request.
- Add inline "mark filled" and "escalate to request" actions from planning/resource requirement screens.
- Add a formal ICS-213RR completeness/checklist view for requests that need official documentation, procurement, finance, reimbursement, or audit handling.
- Add configurable approval-route presets for no approval, operational review, command review, procurement, finance, and full ICS-213RR processing.
- Expand the request schema/UI/export builder to fill official ICS-213RR requester, supplier, order, approval, cost, and finance fields.

## Web Implementation

The browser workspace is live at `/logistics/resource-requests`. It starts with a short
request header and expands into items, fulfillment, history and print sections after the
request is saved. Search/status/priority filters and sorting are stored in the URL.
Actions use the shared approval/status endpoints, with allowed transitions matching the
server; critical header fields lock after submission. Header PATCHes include only changed
editable fields and the actor, never embedded approval/audit/fulfillment arrays.

Line items use their own save action and retain existing item IDs/reference fields.
Fulfillment supports supplier references and current incident team/vehicle selections,
facility destinations, ETA and status. Fulfillment updates do not automatically advance
the request's overall status. The browser can print/save a request summary and download a filled FEMA ICS-213RR through
the shared export endpoint. Extra line items paginate and full source text is retained in
continuation pages. The PDF remains editable; signatures and unavailable fields remain blank.
