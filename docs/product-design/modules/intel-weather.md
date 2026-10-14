# Intel And Weather

## Purpose

Collect, organize, analyze, and disseminate incident intelligence and weather information.

This document covers two related areas: the Intel module for subjects, leads, intel items, assessments, logs, and forms; and the Weather tooling for forecast, aviation, alerts, history, stations, and weather briefings.

## Users

- Intelligence staff and investigators managing subjects, leads, items, assessments, and logs.
- Operations and task staff creating task-linked leads or intel items.
- Planning and safety staff using weather and intelligence in products and briefings.
- Command staff reviewing open leads, assessments, and major weather concerns.
- Air operations users reviewing aviation weather.

## Current Features

- Standalone desktop Intel Module window with tabs for Dashboard, Subjects, Leads, Intel Items, Assessments, Intel Log, and Forms.
- Subjects tab supports profiles for missing persons, witnesses, reporting parties, contacts, patients, vehicles, and aircraft.
- Subject detail windows include overview, timeline, linked records, and activity log.
- Leads tab supports new leads, lead priority/status concepts, lead assignment, source categories, and creation of contact/reporting-party/witness subjects from lead intake.
- Leads can be converted into subjects, intel items, or assessments while preserving relationships.
- Intel Items tab supports new intel item creation, source lead linkage, subject linkage, location text, priority, notes, and file attachments.
- Assessments tab and assessment detail windows exist for analytical records.
- Intel Log tab provides cross-record log/activity navigation.
- Forms tab exists inside Intel for intel-related form outputs.
- SAR-135 export service exists for intel forms.
- Weather dashboard tile exists as an at-a-glance live widget.
- Weather detail panel exists with Current & Forecast, Aviation, Alerts + HWO, History, and Stations tabs.
- Weather settings support polling interval and Go/No-Go thresholds.
- Weather briefing export supports PDF or PNG.
- Weather station management supports configured weather locations, aviation identifiers, and automatic/incident-related locations.
- Aviation weather includes station cards and detailed METAR/TAF decode dialogs.
- Weather alerts and Hazardous Weather Outlook display are present.

## Core Workflows

- Capture or update a subject profile.
- Capture a lead from team, staff, agency liaison, public tip, or other sources.
- Assign a lead and move it through investigation/conversion.
- Convert a lead into a subject, intel item, or assessment.
- Create and review intel items with linked subjects, locations, notes, and attachments.
- Review assessments and open related detail windows.
- Use the intel log to navigate across related intel records.
- Open weather detail, choose/manage stations, review forecast and aviation conditions, acknowledge/review advisories, and export a weather briefing.
- Feed weather summaries into safety/planning products.

## Build Status

Partial but substantial on desktop.

The Intel Module has a real multi-tab workspace and detail-window pattern. Subjects, leads, intel items, assessments, and logs all have concrete UI. The conversion behavior between leads and other record types is a strong built feature.

Weather is also a real desktop submodule with a detail panel, dashboard tile, station management, forecast, aviation, alerts/HWO, history, settings, and briefing export. Some weather backlog remains, but the current surface is much more than a placeholder.

Mobile does not currently expose a dedicated intel or weather workspace. Intel appears mainly through task detail links and field dashboard future actions, while weather is indirectly consumed through safety/planning products rather than a mobile weather screen.

## Screens And UI Inventory

- Desktop: Intel Module window.
- Desktop: Intel Dashboard tab.
- Desktop: Subjects tab.
- Desktop: Subject Detail window.
- Desktop: New/Edit Subject dialogs.
- Desktop: Leads tab.
- Desktop: Lead Detail window.
- Desktop: New Lead dialog.
- Desktop: Intel Items tab.
- Desktop: Intel Item Detail window.
- Desktop: New Intel Item dialog.
- Desktop: Assessments tab.
- Desktop: Assessment Detail window.
- Desktop: Intel Log tab.
- Desktop: Intel Forms tab.
- Desktop: Weather Dashboard Tile.
- Desktop: Weather Detail Panel.
- Desktop: Weather Settings dialog.
- Desktop: Weather tabs: Current & Forecast, Aviation, Alerts + HWO, History, Stations.
- Desktop: Aviation Detail dialog.
- Desktop: Add Airports / station edit dialogs.
- Mobile: no dedicated intel/weather workspace identified.

## Links To Other Modules

- Tasking: task detail can create/open intel leads, intel items, and subject records.
- Command: command dashboard reserves open-lead KPI space, but it is not fully wired.
- Safety: weather summaries can be imported into ICS-208 safety messages; weather hazards inform safety decisions.
- Planning: assessments, subjects, leads, and weather support planning products and operational-period readiness.
- GIS/Maps: intel items and subjects can carry locations and should link to spatial objects over time.
- Forms: intel forms and SAR-135-style outputs are exported through the forms system.
- Public Information: subject/reporting-party/contact information may inform public messaging, with privacy controls needed.
- Communications: leads can originate from reports over radio/messages and should eventually connect to traffic/log records.

## Desktop Experience

Desktop is the primary Intel and Weather workspace.

Intel uses a standalone modeless window rather than an ADS dock. This allows investigators to keep the intel window open while working elsewhere. The tab structure separates the record types clearly, and detail windows allow multiple records to be opened side by side.

Weather is a separate detail panel with a concise dashboard tile for at-a-glance status. The detail panel is organized around operational questions: current/forecast, aviation, alerts/HWO, historical trend, and station setup.

## Mobile Experience

No dedicated mobile intel or weather screen was identified.

Mobile field users currently encounter intel/weather indirectly through tasks, field dashboard shortcuts, safety placeholders, messages, and assignment context. A field dashboard action for Intel Report is marked coming soon, so mobile intel capture appears planned but not built.

## Current Gaps

- Mobile Intel Report action is not implemented.
- No mobile weather view was identified.
- Command dashboard open-lead KPI is not wired.
- Intel, tasking, GIS, public information, and communications relationships need clearer user-facing rules.
- Weather briefing export exists, but its role in IAP/safety/product packets needs design clarification.
- Weather backlog remains for some provider/details work.
- Intel privacy, sensitivity, public-release, and distribution controls need customer-level design.

## Design Questions

- What is the canonical lifecycle of a lead from intake to assignment, conversion, closure, or archival?
- When should a lead become a subject, intel item, assessment, task, or public-information item?
- Which intel records are operationally visible to teams versus restricted to intel/command staff?
- Should mobile field users submit intel as leads, reports, task narratives, or a separate field intel report?
- How should weather affect tasking, safety, aviation, and planning products automatically?
- What is the customer distinction between an intel item, assessment, report, and log entry?
- Which weather conditions should trigger command/safety alerts?

## Future Design Ideas

- Mobile Intel Report workflow from the field dashboard.
- Unified intelligence timeline combining leads, subjects, intel items, assessments, attachments, and task links.
- Review board for new/unassigned leads with triage, assignment, priority, and conversion actions.
- Weather risk cards that push concerns into safety products, command dashboard, and aviation tasking.
- Spatial intel view showing subjects, clues, leads, sightings, weather stations, and hazard areas on the map.
- Privacy/sensitivity controls for intel records and public-release review.
