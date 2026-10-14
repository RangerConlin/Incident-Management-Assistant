# Communications

## Purpose

Manage the incident communications plan, radio/channel assignments, communications traffic log, notifications, and mobile messages.

Communications currently spans formal ICS-205 planning, traffic logging, and mobile incident chat/messages.

## Users

- Communications Unit Leader and communications staff.
- Operations and team leaders who need the current radio plan.
- Dispatch/logging staff capturing radio or message traffic.
- Field users reading the communications plan and sending/receiving mobile messages.
- Command staff reviewing communications issues, alerts, and logged traffic.

## Current Features

- Desktop ICS-205 Communications Plan editor window.
- ICS-205 editor includes a channel library, active communications plan table, operational-period selector, special instructions, column visibility menu, validation, preview, and PDF generation.
- Users can create channels, edit channel assignments, duplicate/delete/reorder rows, import from ICS-217, add library channels to a plan, and generate ICS-205 output.
- Communications channel dialogs support channel/function/frequency/tone/system/mode/remarks-style fields.
- Traffic Log service and repository support creating, listing, updating, filtering, marking disposition/follow-up/status update, attachments, and CSV/PDF export.
- Communications Log Board panel provides table-focused log review with New Entry, filters, context notifications, alert notification, and emergency notification actions.
- Combined log/entry window and quick-entry window exist for traffic capture.
- Canned communication picker exists for inserting reusable communication text.
- Add Field Clue dialog can create a clue-style intel item from communications traffic.
- Mobile Comms Plan screen reads the live ICS-205 plan for the current/best-effort operational period, shows special instructions and channel cards, and supports refresh/retry.
- Mobile Messages screen supports channel list, active channel selection, live subscription, message history loading, refresh, and sending messages when signed in.

## Core Workflows

- Build or update the operational-period ICS-205 plan from a channel library.
- Add or edit channel assignments and special instructions.
- Validate and generate the ICS-205 PDF.
- Capture communications traffic as log entries.
- Filter/review communications log entries and mark disposition/follow-up/status-update flags.
- Export communications logs to CSV/PDF.
- Send communications-log notifications when an entry needs alert/emergency visibility.
- Use mobile to read the current comms plan and participate in incident chat.

## Build Status

Substantial but split across several concepts.

The desktop ICS-205 editor appears mature enough to support real communications-plan work. The communications traffic log also has a service layer, board panel, entry/detail surfaces, canned messages, export, notifications, and clue handoff.

Mobile has a read-only comms plan viewer and a functioning messages/chat screen pattern. Mobile does not appear to edit the ICS-205 plan or create formal communications-log entries.

## Screens And UI Inventory

- Desktop: ICS-205 Communications Plan editor.
- Desktop: New Channel dialog.
- Desktop: Edit Channel Assignment dialog.
- Desktop: Import ICS-217 dialog.
- Desktop: ICS-205 Preview dialog.
- Desktop: Communications Log Board panel.
- Desktop: Communications Log window.
- Desktop: combined Log + Entry window.
- Desktop: Quick Entry window/widget.
- Desktop: Log Detail drawer.
- Desktop: Log Filters panel.
- Desktop: Canned Communication picker.
- Desktop: Add Field Clue dialog.
- Mobile: Comms Plan / ICS-205 viewer.
- Mobile: Messages inbox/chat screen.

## Links To Other Modules

- Planning: ICS-205 belongs in operational-period/IAP products.
- Command: command dashboard shortcuts open communications plan surfaces.
- Tasking: task detail can carry communications channels and assignment communications context.
- Teams: mobile/team users consume communications plan and chat.
- Intel: communications traffic can become clues/intel items.
- GIS/Maps: communications sites and repeaters can be spatial features.
- Forms: ICS-205 generation uses the forms/export system.
- Notifications: traffic log can send alert/emergency notifications.

## Desktop Experience

Desktop is the authoring and logging surface.

The ICS-205 editor uses a split layout: channel library on the left, active plan table on the right, operational-period and special-instructions controls below. The traffic-log side is more dispatch-like, with board/table views, filters, detail editing, quick entry, canned messages, and exports.

The module would benefit from clearer navigation between "communications plan" and "communications traffic log," since those are different jobs with different user expectations.

## Mobile Experience

Mobile is consumption and messaging oriented.

The Comms Plan screen is intentionally read-only and shows the current ICS-205 plan in field-friendly cards. The Messages screen provides incident chat/channel messaging, including live updates and sending when the user/session supports it.

Mobile does not edit channel plans and does not appear to create formal traffic-log entries.

## Current Gaps

- Mobile cannot edit ICS-205 or submit formal traffic-log entries.
- The product distinction between chat messages, radio traffic log entries, notifications, and task narratives needs customer-facing clarity.
- Communications spatial features exist conceptually through GIS adapters, but the user workflow for repeater sites/comms sites needs design.
- ICS-205 publication state is not obvious: mobile says no plan has been published, but desktop plan editing/generation language should make publication/readiness clearer.
- Traffic-log-to-intel clue handoff exists, but broader workflows for task/log/follow-up conversion need design.
- Communications approval/review workflow is not yet clear.

## Design Questions

- What makes an ICS-205 "published" for mobile users?
- Should chat messages ever become formal communications log entries, or are they separate records?
- Who can edit the channel library versus an incident-specific channel assignment?
- How should traffic log entries create follow-up tasks, intel clues, safety issues, or notifications?
- Should communications plan channels be attachable to tasks, teams, facilities, and map features?
- What offline behavior is required for mobile comms-plan access?

## Future Design Ideas

- Clear Communications Home separating Plan, Traffic Log, Messages, Sites, and Exports.
- ICS-205 publication workflow with draft, validated, approved, published, superseded states.
- Mobile offline cached comms plan with last-updated indicator.
- Convert chat/radio traffic into task, intel, safety, or follow-up records from one action menu.
- Communications map layer for repeaters, radio sites, dead zones, and coverage notes.
- Role-based channel-plan editing and approval.
