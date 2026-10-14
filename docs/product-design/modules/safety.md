# Safety

## Purpose

Track incident hazards, safety analysis, safety messaging, and safety incident reports.

Safety is split between planned-risk work, such as hazard registers and ICS-215A/ICS-208 products, and incident-reporting work, such as injury/illness/accident reports and corrective actions.

## Users

- Safety Officer and safety staff.
- Planning staff preparing safety products for the operational period.
- Operations staff reviewing task/work-assignment hazards.
- Command staff reviewing unresolved risk and safety products.
- Team leaders who eventually need mobile GAR/SPE-style field risk workflows.

## Current Features

- Incident Hazard Register / Safety Risk Manager with add, import from library, edit, remove, summary cards, detail pane, filtering, and PDF export.
- Incident Hazard Detail with hazard details, safety content, SPE assessment, links, notes/metadata, hazard-zone selection, and copy-from-library behavior.
- Hazard linking to work assignments, teams, and tasks.
- ICS-208 Safety Message panel with dashboard-assisted authoring, current hazard table, selected hazard summary block, cached weather summary import, draft-block rebuild, append/replace final message, save, and refresh.
- ICS-215A Incident Action Safety Analysis panel with consolidated, by-assignment, and canonical-register views.
- Safety Incident / IWI dashboard with table view, refresh, new report, open, and delete.
- Safety Incident Report detail dialog with occurrence, classification, people/events, narrative/analysis, resolution, witnesses, corrective actions, sign/approval behavior, and save.
- ICS-206 generation support exists in safety services/printing.
- Mobile Safety screen exists as a scaffold for future GAR calculations.

## Core Workflows

- Build and maintain an incident-wide hazard register.
- Import/copy hazards from a hazard library into the active incident.
- Link hazards to operational work, teams, tasks, and hazard zones.
- Review hazards through ICS-215A views for planning and assignment safety analysis.
- Build an ICS-208 safety message from hazard summaries, weather information, and authored safety text.
- Record safety incident/IWI reports, including involved people, injuries/illness, event sequence, witness statements, analysis, corrective actions, and approval.
- Export safety register and safety products for documentation packets.

## Build Status

Partial but meaningful.

Desktop safety has several concrete workspaces. The hazard register, hazard detail, ICS-208, ICS-215A, and safety incident reporting surfaces are real and cover much of the planned safety product workflow.

The generic Safety Dashboard menu entry still returns a placeholder overview, so the module currently works as several specialized tools rather than one unified safety home. Mobile is intentionally not complete: it shows a preview/scaffold for GAR calculations and explicitly avoids presenting fake safety data.

## Screens And UI Inventory

- Desktop: Safety Dashboard placeholder.
- Desktop: Incident Hazard Register / Safety Risk Manager.
- Desktop: Incident Hazard Detail window.
- Desktop: Link Hazard To dialog.
- Desktop: ICS-208 Safety Message panel.
- Desktop: ICS-215A Incident Action Safety Analysis panel.
- Desktop: Safety Incident / IWI dashboard.
- Desktop: Safety Incident Report detail dialog.
- Desktop: supporting dialogs for people involved, injury/illness, witness statements, and corrective actions.
- Mobile: Safety screen scaffold for GAR calculations.

## Links To Other Modules

- Planning: ICS-215A, operational-period safety analysis, work assignments, and safety products feed planning packets.
- Tasking: task safety tab and hazard links connect field assignments to safety content.
- Teams: hazard links and future GAR/SPE work need team context.
- GIS/Maps: hazard zones are spatial features and can be selected/linked.
- Intel/Weather: ICS-208 can import cached weather summaries.
- Forms: ICS-208, ICS-215A, ICS-206, and safety incident reports are documentation outputs.
- Admin/Settings: hazard type library supports hazard classification and copy-from-library workflows.
- Command: safety KPIs/readiness are a future command dashboard need.

## Desktop Experience

Desktop is the only currently usable safety management surface.

The hazard register acts as the canonical safety-risk inventory. ICS-215A and ICS-208 turn that inventory into operational-period safety products. Safety incident reporting is a separate report workflow with its own dashboard and detailed form tabs.

The current experience is capable but fragmented. A Safety Officer can get work done, but they move among specialized windows rather than starting from a unified safety dashboard.

## Mobile Experience

Mobile safety is scaffold-only.

The mobile Safety screen shows a preview banner and placeholder sections for GAR calculator, SPE/GAR inputs, and current status. The Start GAR Calculation button intentionally reports that GAR calculations are not available in this build.

## Current Gaps

- Generic Safety Dashboard is still a placeholder.
- Mobile GAR/SPE calculation is not implemented.
- Safety concepts are spread across hazard register, ICS-208, ICS-215A, IWI, task safety tabs, planning, and admin hazard libraries.
- Command dashboard safety issue counts are not wired.
- The production readiness of ICS-206/208/215A exports should be verified as part of forms standardization.
- Some safety UI still appears to use local styling/color choices that should be reconciled with shared theme tokens.

## Design Questions

- What should the Safety Officer's primary home screen show first: hazards, GAR/SPE scores, safety incidents, safety products, or readiness?
- What is the canonical lifecycle of a hazard from library item to incident hazard to mitigated/closed hazard?
- How should hazard links to tasks, teams, work assignments, and map zones be shown so users trust the relationship?
- Should GAR/SPE be team-owned, task-owned, work-assignment-owned, or hazard-owned?
- Which safety products must be completed before an operational period can be approved?
- How should IWI/safety incident reports affect command dashboard alerts, logs, and corrective-action tracking?

## Future Design Ideas

- Unified Safety Home with open hazards, high-risk assignments, safety incidents, pending corrective actions, and product readiness.
- Mobile GAR/SPE workflow tied to the current team and task.
- Hazard lifecycle board with draft, active, mitigated, monitored, closed, and archived states.
- Safety product readiness checklist for ICS-208, ICS-215A, ICS-206, and related planning products.
- Map-first hazard view showing zones, linked tasks, linked teams, and mitigation notes.
- Corrective-action tracker with owners, due dates, and command visibility.
