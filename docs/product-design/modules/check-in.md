# Check-In

## Purpose

Record arrival, availability, planning/check-in status, and accountability for personnel and incident resources. Support fast intake at a check-in desk, broader ICS-211 style resource intake, team package check-in, and mobile QR identity.

## Users

- Logistics/check-in staff.
- Planning staff maintaining accountability.
- Operations staff monitoring team availability.
- Field personnel using mobile QR identity.
- Team leaders checking in or managing team rosters.

## Current Features

- Working: Quick Check In desktop window for scan-and-go personnel workflows.
- Working: Quick Check In can search by scanned mobile QR, personnel ID, CAPID/person ID, name, callsign, or phone.
- Working: Quick Check In supports status buttons for Expected, Enroute, Checked In, and Check Out/Demobilized.
- Working: Mobile Check-in QR screen generates a personal QR from the on-device profile and works without a network connection.
- Working: Shared QR payload format is documented as `SARAPP:CHECKIN:v1:<person_id>`.
- Working: ICS-211 Resource Check In desktop workbench has tabs for Personnel, Groups / Teams, Vehicles, Aircraft, and Equipment.
- Working: Resource tabs support fast lookup, selecting existing records by organization, reporting location, LDW date/notes, check-in notes, status actions, and adding new records.
- Working: Resource status actions include Enroute, Preparing for Demobilization, and Cancelled.
- Working: Team check-in confirmation can check in members/assets and either keep the team together or disband it.
- Working: Team check-in can notify an operational unit when applicable.
- Partial: The README still describes old implementation assumptions and does not match the current desktop workflow.
- Partial: Mobile incident session startup best-effort associates the user with a team through check-in, but the user-facing check-in lifecycle on mobile is not fully designed.

## Core Workflows

- Scan or enter a personnel identifier at the desktop check-in desk.
- Review the matched personnel record.
- Mark a person expected, enroute, checked in, or demobilized.
- Show a mobile QR code for a desktop scanner to read.
- Check in a person, vehicle, aircraft, or equipment record from the ICS-211 workbench.
- Record reporting location, LDW information, and notes during intake.
- Change resource planning status from the check-in workbench.
- Add a new basic master record during intake if the record does not exist.
- Check in a team package and decide whether to keep the team together or disband it.

## Build Status

Working/partial. The desktop workflow is real and fairly broad. The mobile QR support is real. The design still needs cleanup because check-in overlaps heavily with personnel, teams, resource status, logistics, and mobile session identity. Some documentation is stale.

## Screens And UI Inventory

- Desktop Quick Check In window.
- Quick Check In search/scan field.
- Quick Check In read-only record preview.
- Quick Check In status button row.
- Desktop Resource Check In workbench.
- Resource Check In tabs: Personnel, Groups / Teams, Vehicles, Aircraft, Equipment.
- Fast Check-In section.
- Select Existing Record section.
- Reporting / LDW section.
- Status Actions section.
- Add New Record section.
- Team Check-In confirmation dialog.
- Mobile Check-in QR screen.
- Mobile QR display card.
- Mobile team check-in/member status view in Team Management.

## Links To Other Modules

- Personnel provides responder identity and contact/profile data.
- Teams use check-in status for member accountability and team package check-in.
- Logistics uses check-in for resource intake and availability.
- Resource status reflects vehicles, aircraft, equipment, and personnel-like resource states.
- Mobile profile and QR identity feed desktop check-in.
- Tasking may depend on checked-in teams and resources being available.
- GIS tracking plan depends on check-in/team association to resolve team identity for mobile location.

## Desktop Experience

Desktop has two main check-in surfaces. Quick Check In is for rapid personnel intake with scanner-friendly lookup and status buttons. Resource Check In is the broader workbench for personnel, teams, vehicles, aircraft, and equipment, including LDW/reporting details and status actions.

## Mobile Experience

Mobile currently provides a QR code generated from the local profile so a check-in desk can scan the person. Mobile also joins an incident with a selected team and attempts to associate that person/team through check-in data. The mobile app does not yet read as a full check-in/check-out workflow for the field user.

## Current Gaps

- The old module README is stale and should be rewritten or replaced.
- Check-in status terms overlap with team status, personnel status, resource status, and task assignment status.
- The user-facing relationship between Quick Check In and Resource Check In needs clarification.
- Mobile QR identity exists, but mobile self check-in/check-out design is not complete.
- Team check-in behavior is powerful but needs a clearer lifecycle design, especially disbanding.
- Add New Record during check-in captures only minimal fields, so it may create incomplete master records.
- Needs verification: how check-in history/audit is presented to users outside the immediate workbench.

## Design Questions

- Is check-in primarily a logistics workflow, an accountability workflow, or both?
- Should mobile users be allowed to self check in/out, or should QR desk scanning remain the main model?
- What statuses should be canonical across personnel, teams, and resources?
- Should "Expected" and "Enroute" be planning statuses before actual check-in, or check-in records with pending arrival?
- How should LDW information surface in teams, planning, and logistics views?
- What should happen when a checked-in person is removed from a team or demobilized?

## Future Design Ideas

- Redesign check-in around a single accountability lifecycle shared by personnel, teams, and resources.
- Create a clear comparison of Quick Check In versus Full Resource Check In.
- Add a current accountability view showing who/what is expected, enroute, checked in, assigned, preparing for demob, and demobilized.
- Decide whether mobile should support self-service check-in, check-out, or only QR identity.
