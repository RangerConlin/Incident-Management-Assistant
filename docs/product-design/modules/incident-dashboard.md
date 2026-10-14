# Incident Dashboard

## Purpose

Give command staff a live, at-a-glance view of the active incident.

The Incident Dashboard is part of the broader [Command](command.md) module, but it deserves its own page because it is the closest thing to a command home screen.

## Users

- Incident Commander.
- Command staff and section chiefs.
- Operations staff watching task/team state.
- Planning/logistics users who need fast access to objectives, IAP, and resource requests.

## Current Features

- Incident identity band with incident name, incident number, status, ICP location, incident commander field, next meeting field, operational-period selector, and live clock.
- Quick actions for New Objective, Resource Request, and Open IAP.
- Auto-refresh and manual refresh controls.
- Team Status panel showing checked-in teams and last check-in timing.
- Tasks Due Soon panel showing upcoming task work.
- Critical Alerts panel showing check-in warnings, overdue check-ins, assistance needs, and emergency conditions.
- Geographic Snapshot panel with compact team-location map and expand action.
- KPI strip for active tasks, teams deployed, teams available, open resource requests, personnel checked in, open leads, and safety issues.
- Some dashboard panels intentionally show empty/unavailable states rather than fabricated data.

## Core Workflows

- Open the dashboard as the command home view.
- Review incident identity, operational period, and clock.
- Scan team state, urgent alerts, due tasks, map snapshot, and KPI strip.
- Use shortcuts to create objectives, start a resource request, or open IAP/planning work.
- Use dashboard route shortcuts to jump into team status, task board, comms plan, logistics requests, and map views.
- Pause/resume auto-refresh or refresh manually.

## Build Status

Partial but useful.

The dashboard has a real widget, wrapper panel, signal wiring, quick-action routing, team/task/alert/KPI sections, and refresh behavior. It is more built than a mockup.

Several dashboard concepts are not complete: pending approvals, section health, operational-period readiness, recent major activity, personnel checked-in, open leads, and safety issues either show placeholder text or unavailable values because the backing product concepts are not fully wired.

## Screens And UI Inventory

- Desktop: Incident Dashboard panel wrapper.
- Desktop: IC Overview widget.
- Desktop dashboard sections: identity band, quick-action dock, team status, pending approvals, geographic snapshot, tasks due soon, critical alerts, section health, operational-period readiness, recent major activity, KPI strip.
- Mobile: no equivalent command dashboard; mobile field dashboard is a separate field-user surface.

## Links To Other Modules

- Command: parent module and objective/incident leadership context.
- Planning: New Objective and Open IAP shortcuts.
- Logistics/Resource Requests: Resource Request shortcut and open request KPI.
- Teams/Check-In: team status, last check-in, alert logic, and team map markers.
- Tasking: active tasks and due-soon tasks.
- GIS/Maps: geographic snapshot and expanded map action.
- Communications: comms plan shortcut.
- Safety/Intel: planned KPI slots for safety issues and open leads.

## Desktop Experience

Desktop dashboard is a dense command overview.

It uses multiple dashboard panels and a KPI strip rather than a form/table-heavy layout. It is intended for scanning and navigation more than editing. Quick actions route users into the deeper modules where work is performed.

## Mobile Experience

There is no mobile Incident Dashboard equivalent.

Mobile has a Field Dashboard for team users, but that is not the same as the command dashboard. A future supervisor/mobile-command mode would need its own design.

## Current Gaps

- Pending approvals are not tracked yet.
- Section health is not tracked yet.
- Operational-period readiness checklist is not tracked yet.
- Recent major activity feed is not available yet.
- Personnel checked-in, open leads, and safety issue KPI values are not wired.
- Dashboard route/deep-link behavior should be verified end to end.
- The dashboard needs alignment with future UI standardization, especially status chips, panels, and KPI styling.

## Design Questions

- Should this become the default first screen for command staff?
- Which dashboard panels are must-have for a production command home?
- What data freshness indicator should the dashboard show?
- Which dashboard actions should be deep links versus broad module opens?
- Should mobile supervisors get a reduced command dashboard?
- What does operational-period readiness mean, and which modules feed it?

## Future Design Ideas

- Command readiness strip for the active operational period.
- Unified major activity feed.
- Approval inbox across objectives, IAP, SITREPs, resource requests, communications, and public releases.
- Drill-down KPI cards that explain what records are counted and why.
- Configurable dashboard layout by role.
- Mobile supervisor dashboard with read-only KPIs, alerts, team/task state, and map snapshot.
