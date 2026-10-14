# Personnel

## Purpose

Track the people who may participate in an incident, identify them across desktop and mobile workflows, and provide the source information used by check-in, teams, tasking, logistics, and mobile profiles.

## Users

- Planning and operations staff building teams.
- Logistics/check-in staff processing responders.
- Administrators maintaining organizations, units, ranks, and qualification catalogs.
- Field users creating or syncing their mobile profile.

## Current Features

- Working: Desktop units and organizations editor with organization tree, organization table, detail form, organization type management, rank templates, CSV import, and CSV export.
- Working: Personnel certification and qualification catalog data exists, with qualification/profile concepts used by personnel validation.
- Working: Mobile local profile captures person ID, first name, last name, organization, title, phone, email, and radio ID.
- Working: Mobile profile can use a bundled or synced organization hierarchy, with an "Other / Not Listed" fallback.
- Working: Mobile profile sync is part of joining an incident; the app tries to bring the connected server's personnel record in line with the on-device profile.
- Partial: Personnel appears inside check-in, team membership, tasking, and resource workflows, but those experiences are spread across modules rather than presented as one unified personnel workspace.
- Needs verification: The current desktop surface for creating and editing individual personnel records outside check-in/team workflows.

## Core Workflows

- Maintain organization and unit hierarchy.
- Manage organization types and rank templates.
- Import and export organization data.
- Create or edit a mobile user profile on-device.
- Sync the mobile profile when joining an incident.
- Use personnel records as selectable responders for check-in and team assignment.
- Search personnel when assigning mobile team members.

## Build Status

Partial. Organization/unit management is a concrete desktop feature. Mobile profile identity is also concrete. The broader personnel concept is still fragmented: people are used heavily by check-in and teams, but the design does not yet read as a single finished personnel module.

## Screens And UI Inventory

- Desktop Units and Organizations window.
- Organization tree with search/filter.
- All Organizations table.
- Organization Details form.
- Toolbar actions: New Org, New Sub-Org, Duplicate, Delete, Move Up, Move Down, Manage Types, Rank Templates, Expand All, Collapse All, Import CSV, Export CSV.
- Organization Type Manager dialog.
- Rank Template Manager dialog.
- Reparent Organization dialog.
- Mobile Create/Edit Profile screen.
- Mobile Organization Picker screen.
- Mobile profile removal confirmation.
- Personnel search dialogs in team management/check-in contexts.

## Links To Other Modules

- Check-in uses personnel records to identify responders, record incident status, and support QR-based intake.
- Teams use personnel as members, leaders, medics, and role-bearing assignments.
- Tasking uses teams and personnel-derived team details.
- Mobile identity depends on a personnel profile and feeds incident session startup.
- Logistics/resource status can show personnel as a resource-like incident participant.
- Organization data supports profile, personnel, and catalog-driven filtering.

## Desktop Experience

The clearest desktop personnel-adjacent experience is Units and Organizations: a modeless three-pane editor for organization hierarchy and details. Individual responders appear mainly through check-in and team-detail workflows.

## Mobile Experience

Mobile has a first-class on-device profile flow. The profile is required enough to support incident joining, check-in QR identity, and downstream display. It is device-local first, then synced when the user connects to an incident/server.

## Current Gaps

- The product boundary between "personnel", "check-in roster", and "team member" is not yet clear from a user-design standpoint.
- The desktop individual personnel management experience needs a current-state audit.
- Mobile organization selection has a synced hierarchy fallback, but still carries bundled/hardcoded behavior.
- Personnel status, check-in status, team role, and resource status are related but not presented as one coherent person lifecycle.
- The old check-in README is no longer a reliable product-state description for the personnel/check-in boundary.

## Design Questions

- Should there be one primary Personnel workspace, or should personnel remain mostly embedded inside check-in and teams?
- What is the canonical responder lifecycle: expected, enroute, checked in, assigned to team, assigned to task, demobilized?
- Which fields belong to a master person profile versus an incident-specific check-in record?
- Should mobile users be able to edit all profile fields after syncing, or only device-local identity fields?
- How should qualifications/certifications affect team creation and assignment?

## Future Design Ideas

- Create a unified personnel design that ties together master profile, incident check-in state, team assignment, qualifications, contact info, and mobile identity.
- Add a clear personnel dashboard/list if one does not already exist in a usable form.
- Show a person's current incident state in one place: checked-in status, team, task, role, location, and contact details.
