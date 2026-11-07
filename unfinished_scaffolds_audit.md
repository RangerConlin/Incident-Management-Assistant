# Unfinished Scaffolds and Implementation Gaps Audit

**Audit date:** 2026-11-01  
**Scope:** Repository-wide static review of executable product code, navigation entries, backlog notes, and status documents.  
**Method:** Searched for explicit placeholders, scaffolds, TODOs, `NotImplementedError`, disabled or "coming soon" actions, stub-returned data, and navigation entries whose backing implementation is incomplete. Findings were cross-checked against `backlog.md`, `docs/web_client_status.md`, and `form_builder_inventory.md` where possible.

The application is substantially built, but several user-visible areas are still placeholders or only partially wired despite appearing in menus or navigation.

## Confirmed unfinished or scaffolded areas

### Desktop client

#### 1. Desktop IAP Builder is broken

The Command menu entry imports a nonexistent `app.modules...` path. A fuller legacy implementation exists, but it is SQLite-backed and does not comply with the current UI -> API -> MongoDB architecture. This is the most severe finding because the feature is exposed but fails when opened.

Evidence: [`backlog.md`](backlog.md)

#### 2. Planning Dashboard and Pending Approvals are placeholder panels

Both factories return generic label-only widgets instead of their real implementations.

Evidence: [`apps/desktop/sarapp_desktop/modules/planning/windows.py`](apps/desktop/sarapp_desktop/modules/planning/windows.py)

#### 3. Operations Dashboard is a placeholder panel

The exposed dashboard factory returns a generic widget containing only an overview label.

Evidence: [`apps/desktop/sarapp_desktop/modules/operations/windows.py`](apps/desktop/sarapp_desktop/modules/operations/windows.py)

#### 4. Command Incident Overview and Situation Report factories contain placeholders

Generic implementations exist in both the command `windows.py` module and its `windows` package. This duplication also makes it unclear which path the application is intended to use.

Evidence:

- [`apps/desktop/sarapp_desktop/modules/command/windows.py`](apps/desktop/sarapp_desktop/modules/command/windows.py)
- [`apps/desktop/sarapp_desktop/modules/command/windows/__init__.py`](apps/desktop/sarapp_desktop/modules/command/windows/__init__.py)

#### 5. Command Dashboard is only partially data-backed

The following remain empty-state or constant KPI sections:

- Section Health
- Operational Period Readiness
- Recent Major Activity
- Personnel Checked In
- Open Leads
- Safety Issues
- Some domain-specific approval sources

These require new schemas, repositories, API routes, or aggregation endpoints rather than only UI wiring.

Evidence: [`backlog.md`](backlog.md)

#### 6. Demobilization Board action is explicitly unimplemented

Opening it produces a "not implemented yet" dialog.

Evidence: [`apps/desktop/sarapp_desktop/main.py`](apps/desktop/sarapp_desktop/main.py)

#### 7. Liaison Contacts, Agreements, and Liaison Log are scaffolds

Their screens exist, but their source documentation says the backing repositories and schemas do not exist. Buttons and detail areas are consequently disabled or empty.

Evidence:

- [`apps/desktop/sarapp_desktop/modules/liaison/panels/contacts_panel.py`](apps/desktop/sarapp_desktop/modules/liaison/panels/contacts_panel.py)
- [`apps/desktop/sarapp_desktop/modules/liaison/panels/agreements_panel.py`](apps/desktop/sarapp_desktop/modules/liaison/panels/agreements_panel.py)
- [`apps/desktop/sarapp_desktop/modules/liaison/panels/liaison_log_panel.py`](apps/desktop/sarapp_desktop/modules/liaison/panels/liaison_log_panel.py)

#### 8. Desktop Incident Map has unfinished tools

Vertex editing, moving features, operational feature shortcuts, timeline, and downloads are marked "coming soon." These are visible interface elements rather than hidden extension points.

Evidence:

- [`apps/desktop/sarapp_desktop/modules/gis/map_window/incident_map_window.py`](apps/desktop/sarapp_desktop/modules/gis/map_window/incident_map_window.py)
- [`apps/desktop/sarapp_desktop/modules/gis/map_window/ribbon/incident_tab.py`](apps/desktop/sarapp_desktop/modules/gis/map_window/ribbon/incident_tab.py)
- [`apps/desktop/sarapp_desktop/modules/gis/map_window/bottom_panel.py`](apps/desktop/sarapp_desktop/modules/gis/map_window/bottom_panel.py)

#### 9. Resource-request linking is incomplete

Team Detail exposes a message stating that linking is scaffolded and will be connected later.

Evidence: [`apps/desktop/sarapp_desktop/modules/operations/teams/panels/team_detail_window.py`](apps/desktop/sarapp_desktop/modules/operations/teams/panels/team_detail_window.py)

#### 10. Reference Library help/about factories are placeholders

User Guide and About still return placeholder widgets.

Evidence: [`apps/desktop/sarapp_desktop/modules/referencelibrary/helpdocs.py`](apps/desktop/sarapp_desktop/modules/referencelibrary/helpdocs.py)

### Web client

The web registry currently marks every module as `live`. The remaining incompleteness therefore exists inside nominally live modules rather than as clearly marked planned entries.

#### 1. Incident Map is only partially implemented

Missing functionality includes:

- Point, line, and area creation
- Draw, edit, move, and buffer interactions
- Quick Add
- Measurement
- Layer management
- Team and task extents
- UTM and MGRS conversion
- Timeline
- Downloads

Evidence:

- [`docs/web_client_status.md`](docs/web_client_status.md)
- [`apps/web/src/modules/incidentMap/IncidentMapPage.tsx`](apps/web/src/modules/incidentMap/IncidentMapPage.tsx)

#### 2. Team Detail resource-request linking is missing

The tab visibly says "Resource request linking coming soon."

Evidence: [`apps/web/src/modules/operations/teamStatus/TeamDetailPage.tsx`](apps/web/src/modules/operations/teamStatus/TeamDetailPage.tsx)

#### 3. Task Detail has unbuilt tabs

Safety, Communications, Debriefing, Attachments, Intel, and Log remain pending module integration.

Evidence: [`docs/web_client_status.md`](docs/web_client_status.md)

#### 4. Authentication is not enforced

Login can issue a JWT, but no server router validates it. Password reset/change is also incomplete.

Evidence: [`backlog.md`](backlog.md)

#### 5. Several web relationships use primitive strings instead of catalogs

Team personnel, vehicles, and equipment are edited as raw string arrays because the corresponding catalogs are not integrated.

Evidence: [`backlog.md`](backlog.md)

### Mobile client

Mobile contains the largest clearly identified set of deliberate scaffolds.

#### 1. Shared Coming Soon destinations

Map, Intel Report, Forms, and additional field actions route through a generic placeholder screen.

Evidence: [`apps/mobile/lib/screens/coming_soon_screen.dart`](apps/mobile/lib/screens/coming_soon_screen.dart)

#### 2. Hazard reporting is nonfunctional

The form has no corresponding server endpoint and submission only reports that the feature is not ready. "Attach Photo" triggers the same placeholder behavior rather than a photo picker.

Evidence: [`apps/mobile/lib/screens/report_hazard_screen.dart`](apps/mobile/lib/screens/report_hazard_screen.dart)

#### 3. Safety/GAR workflow is a scaffold

The stable navigation screen exists, but mobile SPE/GAR calculation and persistence are not connected.

Evidence: [`apps/mobile/lib/screens/safety_screen.dart`](apps/mobile/lib/screens/safety_screen.dart)

#### 4. Task status actions are UI-only

Status advancement is not persisted because the required mobile write endpoints do not exist.

Evidence: [`apps/mobile/lib/screens/task_detail_screen.dart`](apps/mobile/lib/screens/task_detail_screen.dart)

#### 5. Navigation tools use sample coordinates

No location-target endpoint exists, so the screen displays explicitly labeled sample/preview data.

Evidence: [`apps/mobile/lib/screens/navigation_tools_screen.dart`](apps/mobile/lib/screens/navigation_tools_screen.dart)

## Form and template work still incomplete

The form inventory identifies two distinct categories:

- Some form packages remain generic starter scaffolds with empty field mappings.
- Several otherwise usable forms still have unresolved or unverified field bindings.

This is real unfinished authoring work, although it does not mean the entire form system is a scaffold.

Evidence: [`form_builder_inventory.md`](form_builder_inventory.md)

## Items not classified as unfinished

The audit deliberately excluded:

- Normal empty states such as "No attachments yet."
- Input placeholder text
- Abstract base methods that intentionally raise `NotImplementedError`
- Buttons disabled until a row is selected or validation succeeds
- Temporary widgets replaced with live editors after a record is saved
- Exception handlers containing `pass`
- Test fixtures and generated Flutter platform templates
- Legacy compatibility code unless it is still exposed by the current application

## Recommended priority

1. Repair or replace the broken desktop IAP Builder.
2. Replace exposed desktop Planning, Operations, Command, and Liaison placeholder panels.
3. Implement real persistence for mobile hazard reporting and task-status changes.
4. Finish map creation and editing consistently across desktop and web.
5. Finish authentication as a coordinated desktop/mobile/web change.
6. Complete form mappings and secondary actions such as timeline and downloads.

## Audit limitations

This was a read-only static audit. It did not launch every screen or exercise every interaction, so additional runtime-only gaps may exist. No tests were run because the audit did not modify executable code.
