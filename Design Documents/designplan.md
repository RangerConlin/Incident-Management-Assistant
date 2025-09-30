# ICS Command Assistant - Design Plan

## Table of Contents
  - [Overview](#overview)
  - [System Architecture](#system-architecture)
  - [Module Overview](#module-overview)
  - [UI Layout](#ui-layout)
  - [Key Features](#key-features)
  - [Design Phases](#design-phases)
  - [Future Considerations](#future-considerations)

 
ICS Command Assistant - Desktop Application
## Phase 1: Core System & User Foundation
## Phase 2: Team Operations, Personnel, and Status Boards
## Phase 3: Communications & Public Information
## Phase 4: Forms, Documentation, & Reference Library
## Phase 5: Logistics, Medical, & Safety
## Phase 6: Intel & Mapping
## Phase 7: Advanced Operations & Toolkits
## Phase 8: UI Customization & Multi-Window UX
## Phase 9: Status Boards, Automation, & Reporting
## Phase 10: Finance/Admin & Incident Closeout
## Phase 11: Mobile Integration & Future Systems
## Phase 12: Special/Planned (AI & Advanced GIS)
## Module 1: Command
## Module 2: Planning
## Module 2-1: Strategic Objectives
## Module 3: Operations
## Module 3-1: Taskings
## Module 4: Logistics
## Module 4-1: Resource Request
## Module 5: Communications
## Module 6: Medical and Safety
## Module 6-1: CAP Operational Risk Management
## Module 6-2: Weather
## Module 7: Intel
## Module 8: Liaison
## Module 9: Personnel and Role Management
## Module 9-1: Personnel Certifications
## Module 10: Reference Library
## Module 11: ICS Forms and Documentation
## Module 12: Finance/Admin
## Module 13: Status Boards
## Module 14: Public Information
## Module 15: Mobile App Integration
## Module 16: Training/Sandbox Mode
## Module 17: Search and Rescue Toolkit
## Module 18: Disaster Response Toolkit
## Module 19: Planned Event Toolkit
## Module 19-1: Event Promotions and Communications
## Module 19-2: Vendor & Permitting Coordination
## Module 19-3: Public Safety & Incident Management
## Module 19-4: Mini Tasking Module
## Module 19-5: Public Health & Sanitation Oversight
## Module 20: Initial Response Toolkit
## Module 21: UI Customization
## Module XX: AI Integration (Wishlist Phase)
 
ICS Command Assistant - Desktop Application
### Overview
The ICS Command Assistant is a Windows desktop application designed to support emergency management, search and rescue, and incident command operations. Its goal is to streamline information flow, tasking, personnel/resource tracking, documentation, and reporting, with a flexible, modular design based on the Incident Command System (ICS) framework.

Target Users:
  - Incident Commanders
  - Section Chiefs and ICS staff
  - Logistics and Planning personnel
  - Field teams (via desktop, future mobile integration)
  - Emergency management staff at local, state, and federal levels
### System Architecture
Frontend:
  - Developed with Qt Widgets (PySide6), NiceGUI, and Tkinter for UI and Python for logic
  - Modular UI layout with each module having its own:
o	Models/ for class definitions
o	Panels/ for PySide6 widgets (e.g., status boards)
o	Tkinter for simple popups/utility tools where minimal overhead is preferred.
  - Supports:
o	Modeless windows
o	Multi-monitor layouts
o	User-selectable themes (dark mode, light mode, and custom color profiles)
Backend:
  - Python FastAPI server (bundled and run locally)
  - SQLite databases:
o	master.db (persistent personnel, equipment, templates, etc.)
o	Incident-specific DBs (all incident/event data, audit trail, forms)
  - Local LAN/WebSocket support for real-time collaboration
File System & Data:
  - Root-Level Folders
o	/data : All databases and uploads
o	/modules : All feature-specific logic and UI (subfolders for each module)
o	/qml : Shared QML ui files for program level forms and windows.
  - Each module folder contains:
o	modules/<module_name>/models/ – Python classes and datatypes
o	modules/<module_name>/panels/ – Qt Widget panels (tables, editors, status boards)
o	modules/<module_name>/widgets/ – Additional Qt Widget dialogs/windows
o	modules/<module_name>/nicegui/ – NiceGUI endpoints/components (optional)
o	modules/<module_name>/tk/ – Tkinter utilities (optional)
  - Drag-and-drop upload interface for:
o	Documents, ICS forms, media (photos, video, and audio), other attachments
Security & Perincidents:
  - Role-based UI/perincidents
o	User role affects visible modules, context menu options, and edit rights
  - Audit logs for all changes
o	All data changes tracked per user in the incident-specific database

### Module Overview
The app is divided into major ICS sections, each with its own modules:
### Command: Incident command, objectives, situational awareness
### Planning: Tasking, action plans, documentation, mapping
### Operations: Field teams, assignments, real-time tracking
### Logistics: Personnel, check-in, resources, supplies, transportation
### Communications: Radio logs, comms plans, chat, frequency/resource management
### Medical and Safety: Medical plans, safety messages, incident tracking
### Intel: Data, weather, intelligence, and clue management
### Liaison: Agency contacts, notifications, support requests
### Personnel and Role Management: Assignments, qualifications, accountability
### Reference Library: ICS forms, agency forms, guides, regulations, state/county resources
### ICS Forms and Documentation: All fillable forms, auto-fill from data, upload/digitization of custom forms
### Finance/Admin: Time tracking, expense reporting, procurement, reimbursement
### Status Boards: Global/module-specific boards (team, personnel, equipment, resource requests, etc.)
### Public Information: Press releases, briefing log, public info contacts
### Mobile App Integration: Sync/bridge with field/mobile app (future)
### Training/Sandbox Mode: Simulated incidents, user practice environment
### Search and Rescue Toolkit: Specialized tools, calculators, and workflows for SAR operations
### Disaster Response Toolkit: Dedicated modules for disaster incident types (floods, wildfires, hurricanes, etc.)
### Planned Events Toolkit: Event-specific planning and resource management tools
### Initial Response Toolkit: Tools for hasty search, rapid tasking, and initial response workflows
### UI Customization: End-user module for UI Template Selector, Custom Theme Editor, and Dashboard Builder (custom layouts, colors, and widget arrangements)
Special/Planned:
  - Module XX: AI Integration (future AI assistant, data automation, recommendations)
  - Module XX: GIS Integration (future advanced GIS and mapping platform)

### UI Layout
Main Window:
  - Persistent header: Incident name, incident number, operational period, user role
  - Section tabs (top-level): Command, Planning, Operations, etc.
  - Modules appear as sub-tabs/side menu items
  - Modeless windows for all modules (multi-monitor ready)
  - Quick-access dashboard with widgets for key stats/alerts
  - Team and Task Status boards always accessible
  - Built-in search/filter and help
  - Theme selector (light/dark/custom color profiles)

  - Docking Improvements
  - Center area: Establishes CenterDockWidgetArea so docks snap relative to the full window.
  - Margins: Zeroed central/container layout margins and spacing to make the dock area fill the window.
  - Constructors: Standardized on CDockWidget(self.dock_manager, title) to avoid deprecated paths and ensure full ADS behavior.
  - Default Layout
  - Forced defaults: Added FORCE_DEFAULT_LAYOUT = True to always start with a known-good layout.
  - Default docks: Creates “Mission Status” (center), “Team Status” (left), and “Task Status” (bottom).
  - Reset: Debug menu adds “Reset Layout (Default)” to clear saved perspectives and rebuild.
  - Status Boards
  - Unified panels: Default docks now use the same rich panels as menu items:
  - modules/operations/panels/team_status_panel.py
  - modules/operations/panels/task_status_panel.py
  - Row coloring: Applies centralized palettes from styles.py (team/task).
  - Live updates: Changing a Status cell recolors the entire row instantly.
  - Right click menu: Per-row context menus for status changes and “View Detail”.
  - Menu Behavior
  - Undocked by default: Panels opened via menu now float (open undocked). They can be docked by the user afterward.
  - QML docks: When QML is used for a panel, it’s wrapped in a QQuickWidget inside a CDockWidget so it’s dockable.
  - Layout Persistence
  - Save/load: Persists perspectives to settings/ads_perspectives.ini (“default”) on close, auto-loads on startup when not forcing defaults.
  - Safe fallback: If loading fails or yields no docks, seeds the default layout.
  - Mission Status
  - Converted from fixed header to a movable “Mission Status” dock showing incident/user/role; stays in sync with title and AppState.
  - Multi Window Workspaces
  - New workspace: Window → “New Workspace Window” creates a floating dock container you can move to a second monitor and dock panels into.
  - Debug Utilities
  - Debug menu: “Open Default Docks” and “Reset Layout (Default)” for quick recovery during testing.
  - Print active incident: Quick inspection action remains.

Module Windows:
  - Consistent layout for tables, forms, and detail views
  - Drag-and-drop upload areas where relevant
  - Print/export/report buttons for all major forms
  - User presence/status shown throughout

### Key Features
  - Modular architecture, with ability to enable/disable modules per incident
  - Multi-database support (persistent master, incident-specific DBs)
  - Fillable ICS and agency forms (auto-filled from live data)
  - Real-time LAN/WebSocket collaboration and updates
  - Detailed audit trail/change logs, versioned form history
  - Global and module-specific search and filters
  - User presence/status indicators and login auditing
  - Status boards for personnel, teams, equipment, tasks, resource requests, etc.
  - Quick-entry hotkey panel and UI shortcuts
  - Form dependency hints and workflow suggestions
  - Multi-monitor/multi-window capability
  - Drag-and-drop file uploads (media, forms, documents)
  - Embedded training/sandbox mode for onboarding/practice
  - Scheduled task alerts and reminders
  - Time synchronization with GPS or NTP
  - Mapping and GIS integration for task, team, and resource tracking
  - Multiple UI themes and color profiles

### Design Phases
## Phase 1: Core System & User Foundation
  - QML/PySide6 UI scaffold and main window shell
  - FastAPI backend integration
  - Database architecture: master and incident DBs
  - Role-based login & user management
  - Incident creation, selection, and loading
  - Top-level navigation with module placeholders

## Phase 2: Team Operations, Personnel, and Status Boards
  - Personnel roster and org structure
  - Role assignment, team creation, and status tracking
  - Planning module (tasking, SITREP, time tracking)
  - Operations dashboard (team/assignment views)
  - Initial Status Boards (team and personnel)
  - ICS 214 logging interface

## Phase 3: Communications & Public Information
  - Chat/messaging system (IM-style)
  - ICS 213 structured messaging
  - Notification system for updates/alerts
  - Public Information module (press log, bulletins, approvals)
  - File attachments in chat/messages

## Phase 4: Forms, Documentation & Reference Library
  - ICS Forms engine (213, 214, 206, 205, 205A, etc.)
  - Auto-fill and digitization framework
  - Custom form uploader and template management
  - Versioned form/document history
  - Reference Library browser (SOPs, agency docs, guides)
  - Related Forms linking system

## Phase 5: Logistics, Medical, & Safety
  - Logistics inventory manager (supplies, vehicles, equipment)
  - Check-in/check-out system
  - Medical/Safety log (ICS 206, safety messages)
  - Resource tracking and assignment
  - Reimbursement/cost tracking

## Phase 6: Intel & Mapping
  - Intel dashboard (data, weather, intelligence, clue management)
  - GIS mapping engine (KML/GeoJSON import, task/resource plotting)
  - Layer toggles (search areas, hazards, units)
  - Time synchronization (GPS/NTP)
  - SITREP builder

## Phase 7: Advanced Operations & Toolkits
  - SAR Toolkit (tools, calculators, clue management)
  - Disaster Response Toolkit (incident-specific)
  - Planned Events Toolkit (event planning)
  - Initial Response Toolkit (hasty search, rapid tasking)
  - Liaison/agency support module

## Phase 8: UI Customization & Multi-Window UX
  - UI Template Selector (layout/theme options)
  - Custom Theme Editor (color palette, dark/light mode)
  - Dashboard Builder (custom widgets, drag/drop layouts)
  - Multi-window and multi-monitor support
  - System tray/background integration

## Phase 9: Status Boards, Automation & Reporting
  - Dedicated status boards (resource, team, comms, task, medical, logistics)
  - Workflow automation (reminders, overdue alerts, form dependency hints)
  - Auto-generation of logs (ICS 214, etc.) from activity data
  - Filtering, sorting, PDF export, report generation

## Phase 10: Finance/Admin & Incident Closeout
  - Full Finance/Admin module (time tracking, cost centers, audit trail)
  - End-of-incident tools (export, ZIP archive, printable reports)
  - Embedded sandbox/training mode
  - Global and module-level search/filter

## Phase 11: Mobile Integration & Future Systems
  - Cross-platform sync (desktop ↔ mobile app)
  - Import/export for tasks, logs, forms, and status
  - Real-time mobile device reflection in boards
  - Shared templates and LAN/USB/manual sync

## Phase 12: Special/Planned (AI & GIS Integration)
  - AI Integration (assistant, automation, smart forms)
  - Advanced GIS Integration (external systems, overlays, AVL, drone feeds, etc.)

### Future Considerations
  - Embedded AI assistant for data entry, search, and suggestions
  - Integration with external CAD, GIS, or incident planning platforms
  - Offline/online sync for mobile/field deployments
  - Internationalization (multi-language support)
  - Custom report generator, print-ready exports
  - Scheduled upgrades based on user feedback
  - Additional module/toolkit categories (as user needs evolve)
  - Advanced analytics/dashboarding
  - Additional theme and branding options
  - Enhanced mapping (e.g., drone overlays, live AVL)

 
## Phase 1: Core System & User Foundation

## Phase 1 Goals:
Establish the backbone of the application, ensuring the system runs locally, supports users, and lays groundwork for all future modules. Build a stable, modular, and secure core that is easy to extend.
Major Components to Build
### QML/PySide6 UI Scaffold and Main Window Shell
  - QML UI/frontend
  - Build the main window with persistent header (shows incident name, op period, user role, etc.).
  - Implement top-level navigation (tab bar for Command, Planning, Operations, etc.).
  - Display empty placeholders or "coming soon" for modules not yet built.
  - Enable basic theming (at least dark and light mode toggles).

### FastAPI Backend Integration
  - Create the initial FastAPI project structure.
  - Set up API routing and allow connection from the Electron frontend.
  - Enable CORS to allow local frontend-backend communication.
  - Add a health check endpoint for dev testing (/api/health).

### Database Architecture: Master and Incident DBs
  - Implement master.db for persistent records (personnel, equipment, templates).
  - Set up folder for incident-specific databases (/data/incidents/).
  - Create API endpoints for:
  - Creating new incident DBs (from UI or CLI)
  - Selecting/loading a incident (returns incident metadata)
  - Ensure data folder exists and is writable.

### Role-Based Login & User Management
  - Create a login screen as the first UI the user sees.
  - Implement ID entry and role selection (roles pulled from personnel database in master.db).
  - Basic role management: restrict some features/menus by role (stubbed for now).
  - Store current user/role in app state and audit logs.

### Incident Creation, Selection, and Loading
  - Provide UI for creating a new incident (form: name, type, description, etc.).
  - Display list of existing incidents; allow selection and loading.
  - Show incident info in the persistent header after selection.
  - Only allow one active incident at a time.

### Top-Level Navigation with Module Placeholders
  - Render tabs for all major modules, even if not implemented (greyed out/“coming soon”).
  - Place quick-access dashboard (widgets for: current incident, op period, alerts).
  - Enable a “dummy” personnel/team status board for early testing.

### System Settings & Data Folder
  - Allow user to set/change /data directory (for DBs, uploads, attachments).
  - Ensure the app checks for this folder on startup and prompts if missing.

Security and User Experience
  - Store all sensitive data (user/incident) only locally—no cloud sync in Phase 1.
  - Ensure user actions (login, incident select, create) are logged (audit trail foundation).
  - Display current user, role, and incident context at all times.

## Phase 1 Exit Criteria (Definition of Done)
  - App launches from a single executable (or from dev environment) and shows the main window.
  - User can:
  - Log in with an ID and select a role.
  - Create and select a incident.
  - See a dashboard with incident/user context.
  - Navigate top-level tabs (see placeholder screens).
  - master.db and at least one incident DB exist in /data.
  - No critical errors or crashes in normal use.
  - All persistent data is stored locally in the correct folder.

Optional (Phase 1.5 / Stretch Goals):
  - Add basic in-app help/about screen.
  - Support for minimal user settings (theme, font size).
  - Allow basic app update checking (if relevant).
 
## Phase 2: Team Operations, Personnel, and Status Boards
## Phase 2 Goals:
Enable robust management and real-time tracking of all teams, personnel, and their statuses. Implement organization structure, assignments, dashboards, and initial activity logging to support incident operations and accountability.
Major Components to Build
### Personnel Roster and Org Structure
  - Design and build the Personnel Roster UI: searchable, filterable table of all personnel (with columns for name, role, status, assignment, contact info, etc.).
  - Implement add/edit/remove personnel workflows (data stored in master.db).
  - Build the Organizational Structure Manager:
  - Allow creation and editing of org units (sections, teams, branches, etc.).
  - Implement drag-and-drop assignment of personnel to roles and teams.
  - Show interactive org chart/tree.

### Role Assignment, Team Creation, and Status Tracking
  - Implement team creation and editing UI: assign name, team type, members, and supervisor/leader.
  - Enable assignment of personnel to teams and ICS roles.
  - Track real-time status for each person and team (Available, Assigned, Out of Service, etc.).
  - Store all assignments, changes, and status updates in incident-specific DB for audit and after-action review.
  - Allow for “hot swap” of roles and team assignments, preserving assignment history.

### Planning Module (Tasking, SITREP, Time Tracking)
  - Develop task assignment and tracking tools:
  - Allow creation of new tasks with description, priority, category, and assigned team(s).
  - Implement task board UI: show tasks by status (Draft, Planned, In Progress, Completed, Cancelled).
  - Add time tracking functionality:
  - Record shift start/stop, on-duty/off-duty status for each person.
  - Store time logs for personnel, teams, and assignments.
  - Enable SITREP (Situation Report) entry and display:
  - Simple form and log of recent operational events, visible to Planning/Command.

### Operations Dashboard (Team/Assignment Views)
  - Build an Operations Dashboard displaying:
  - Current teams, assignments, and statuses.
  - Map/table/list views of team locations (location may be manual for now).
  - Live updates for critical team changes or status updates.
  - Allow filtering/sorting by assignment, role, status, team, or operational period.

### Initial Status Boards (Team and Personnel)
  - Implement Status Boards Module:
  - Create separate boards for team status and personnel status.
  - Board should be real-time (auto-update or with refresh button).
  - Enable filters (by team, status, role, etc.).
  - Visual indicators for status (color-coding, icons).
  - Enable printing or exporting current board state.

### ICS 214 Logging Interface
  - Develop a basic ICS 214 Activity Log interface:
  - Each team, unit, and the overall Operations section gets its own log stream.
  - Allow manual entry and edit of log items (who, what, when, notes).
  - Auto-populate logs from status changes, assignments, and critical events.
  - Enable export/print of activity log for recordkeeping.

Security and User Experience
  - Enforce role-based perincidents for sensitive actions (e.g., only Ops/Planning/Command can change teams or assignments).
  - All personnel and assignment changes are recorded in audit trail.
  - UI always shows current user, role, and incident context.

## Phase 2 Exit Criteria (Definition of Done)
  - User can view and edit personnel roster, including assignments, roles, and teams.
  - Teams can be created, edited, and assigned to tasks.
  - Real-time status boards for personnel and teams are visible, filterable, and color-coded.
  - Operations dashboard shows assignments and status.
  - ICS 214 logs are available, and logs can be exported/printed.
  - All actions and changes are stored in the appropriate incident database.
  - No critical errors or crashes during normal use.

Optional (Phase 2.5 / Stretch Goals)
  - Implement drag-and-drop task assignment on dashboards.
  - Add shift/relief tracker with tie-in to ICS 214 logs.
  - Enable basic map visualization for team locations (if not done in Phase 1).
  - Add automated reminders/alerts for overdue tasks or status changes.

 
## Phase 3: Communications & Public Information

 
## Phase 4: Forms, Documentation, & Reference Library

 
## Phase 5: Logistics, Medical, & Safety

 
## Phase 6: Intel & Mapping

 
## Phase 7: Advanced Operations & Toolkits

 
## Phase 8: UI Customization & Multi-Window UX

 
## Phase 9: Status Boards, Automation, & Reporting

 
## Phase 10: Finance/Admin & Incident Closeout

 
## Phase 11: Mobile Integration & Future Systems

 
## Phase 12: Special/Planned (AI & Advanced GIS)

 

## Module 1: Command
1. Module Name & Description
This module provides high-level control over incident setup, incident configuration, and global status settings. It is typically used by Incident Commanders or authorized supervisors at the top of the ICS structure.
2. Primary Functions
  - Define incident type to dynamically load relevant modules (e.g., SAR, Fire, Multi-Agency, Training)
  - Designate incident as a training incident with limited or sandboxed data persistence
  - Create and manage incidents/incidents
  - Set incident type, name, and geographic scope
  - Define operational periods
  - Set incident status flags (e.g., Active, Standby, Terminated)
  - Lock/unlock incident data for editing
  - Archive or export incidents
  - Set incident objectives (tie-in with ICS 202 and Planning's Strategic Tasks)
  - Optional: Track financial allocation and spending at a incident level
3. Submodules / Tools
  - Incident Overview Panel: Dashboard showing basic info, time, status
  - Incident Configuration Form: Detailed editor for incident profile
  - Incident Status Controls: Toggle incident state (Active, Paused, Standby, Terminated); includes timestamps and reason codes
  - Objective Tracker: Link or manage ICS 202 objectives and feed into Planning's Strategic Tasks Module
  - Finance Overview Panel (optional): Displays total budget, spend-to-date, and remaining balance
  - IAP Builder: Wizard-style interface that supports ICS 201 and 202 entry and integrates data from other modules (Personnel, Operations, Logistics, Communications, Safety) to support auto-population of additional forms like ICS 203, 204, 205, 206, and 207
4. Key Data Modules
Operational period rollover logic can be optionally enabled per incident. If active, the system will automatically close and create a new period at a defined time (e.g., 0700 local), carrying forward uncompleted objectives.
  - Incident: id (int, PK), name (str), number (str), type (str), description (str), status (str), search_area (str), icp_location (str), start_time (str ISO8601 UTC), end_time (str ISO8601 UTC), is_training (BOOLEAN)
  - OperationalPeriod: id (int, PK), incident_id (str, FK incidents(id)), op_number (str), start_time (str ISO8601 UTC), end_time (str ISO8601 UTC)
  - IncidentObjective: id (int, PK), incident_id (str, FK incidents(id)), text (str), priority (int), tags[]
5. UI Components
  - - Incident creation/edit form
  - - Incident status display (e.g., badge or label in header)
  - - Operational period timeline/selector
  - - Export/archive buttons
  - - Dashboard card with live incident metadata
  - - Finance overview widget (if enabled)
6. API Endpoints
```
  - - GET /api/incidents
  - - POST /api/incidents
  - - PUT /api/incidents/{id}
  - - DELETE /api/incidents/{id}
  - - GET /api/incident/{id}/periods
  - - POST /api/incident/{id}/periods
  - - GET /api/incident/{id}/objectives
  - - POST /api/incident/{id}/objectives
  - - GET /api/incident/{id}/finance
  - - PUT /api/incident/{id}/finance
```
7. Database Tables
```
  - - incidents
  - - operationalperiods
  - - incidentobjectives
  - - incidentfinance
```
8. Inter-Module Connections
  - - Command Module: Objectives feed directly into Strategic Tasks
  - - Operations: Task visibility filtered by operational period and linked objectives
  - - Forms Module: 202, 203, and others rely on incident metadata
  - - Finance/Admin: Aggregates incident-level financial data
9. Special Features / Notes
  - - Incidents may be flagged as "Planned" to indicate upcoming events or operations that have not yet started
  - - Incident type selection determines which modules and features are loaded and visible
  - - Training incidents are isolated and may use non-persistent data for exercise or simulation purposes
  - - Only one incident may be "active" at a time
  - - System auto-locks editing of closed/archived incidents
  - - Built-in validation to prevent overlapping operational periods
  - - All timestamps stored in UTC
  - - Optional finance tracker can be toggled on/off based on organization policy or role access
  - - The incident status is displayed in context (e.g., header or dashboard) but does not persist as a banner across unrelated modules
 
## Module 2: Planning
1. Module Name & Description
Planning Module
The Planning Module manages forward-looking operations, documentation, and coordination for all incident activities. It supports the development of objectives, tracks strategic tasks, and interfaces with time-based tools like the IAP and ICS 214 activity logs.
2. Primary Functions
  - - Convert high-level objectives into strategic taskings
  - - Manage task tracking, priority, and completion
  - - Manage operational periods and planning timelines
  - - Prepare planning inputs for IAP development
  - - Interface with ICS 214 activity logging
  - - Coordinate with other modules to populate IAP forms
3. Submodules / Tools
  - - Pending Approval Queue: Separate interface for reviewing and approving tasks before they are assigned or published to the IAP.
  - - Planning Forecast Tool: Projects anticipated personnel or resource requirements based on planned tasks in upcoming operational periods.
  - - Operational Period Cloning Tool: Allows duplication of prior periods, including tasks, objectives, and structure for rapid reuse.
  - - Task Metrics Dashboard: Summarizes task volume, status distribution, and completion trends across periods and sections.
  - - Strategic Task Tracker: Tracks requests and objectives converted into actionable tasks. Authorized positions can promote external requests into incident objectives, which are then visible in the Command module and Planning dashboard.
  - - Planning Dashboard: Overview of operational period status, task load, and pending approvals
  - - IAP Input Panel: View and edit inputs for forms like 202, 203, 204, 215
  - - Operational Period Scheduler: Adjust and define timeframes for each period
  - - Planning History View: Displays changes to strategic tasks, objectives, and planning entries over time with timestamps and editor details
  - - Task-to-Form Mapping Panel: Allows planners to link tasks to associated ICS forms (e.g., 204, 206, 215), track form status and completion, and validate documentation coverage
4. Key Data Modules
  - - StrategicObjectives: id (int PK), incident_id (int, FK incidents(id)), objective_id (str), description (str), status (str), assigned_section (str), priority, due_time (str ISO8061 UTC), is_external_request (boolean), customer (int, FK agency_contacts(id))
  - - PlanningLog: id (int PK), incident_id (int, FK incidents(id)), text (str), timestamp (str ISO8061 UTC),, entered_by (int, FK personnel(id))
  - - PlanningNote: id (int PK), incident_id (int, FK incidents(id)), user_id (int, FK personnel(id)), text, tags[]
5. UI Components
  - - Task entry form and assignment table
  - - Task prioritization interface (drag-and-drop or rank-based)
  - - Strategic objective linkage display
  - - Operational period timeline tool
  - - Planning summary feed or board
6. API Endpoints
```
  - - GET /api/planning/tasks
  - - POST /api/planning/tasks
  - - PUT /api/planning/tasks/{id}
  - - GET /api/planning/logs
  - - POST /api/planning/logs
  - - GET /api/planning/notes
  - - POST /api/planning/notes
```
7. Database Tables
```
  - - strategicobjectives
  - - planning_logs
  - - planning_notes
```
8. Inter-Module Connections
  - - Command Module: Receives linked objectives for strategic breakdown
  - - Operations: Task status updated based on field execution
  - - Forms Module: Data feeds into ICS 202, 203, 204, 215, and 214
  - - Personnel Module: Tasks may be linked to positions/roles
9. Special Features / Notes
  - - Pending task approvals must be cleared before integration into the IAP or Operations workflow
  - - Forecasting engine helps anticipate personnel/resource needs based on scheduled or recurring tasks
  - - Operational periods can be cloned to streamline multi-day event planning
  - - Real-time task metrics and summaries help Planning Chiefs prepare SITREPs or time-critical reports
  - - Tasks can be internal or external in origin
  - - ICS 214 activity logs can optionally be auto-linked to strategic tasks
  - - Users can tag, prioritize, and track task chains across periods
  - - Supports comment threads or updates on task cards
  - - Built for tight integration with IAP and Form Builder workflows
  - - Planning history view provides version tracking and accountability for strategic decisions
  - - Risk assessment logic deferred to the Safety Module
## Module 2-1: Strategic Objectives
1. Module Name & Description
The Objective Tracker submodule provides centralized management of all objectives derived from incident objectives, external requests, or manual entry by Planning or Command staff. It tracks the full lifecycle of each objective—creation, approval, assignment, status changes, audit log, and closure—and links each objective to its originating objective or request for comprehensive accountability.
2. Primary Functions
  - Create, edit, and manage objectives (manual, from objectives, or external requests)
  - Link objectives to incident objectives
  - Status and lifecycle tracking (pending, approved, assigned, in progress, completed, cancelled)
  - Approval workflow: approve, reject, or return objectives for more information
  - Full audit trail: every change, who, what, when
  - View, filter, and report on objectives by status, priority, assignment, period, and origin
3. Submodules / Tools
  - Objective List: Filterable, sortable list of all objectives
  - Objective Detail Window: Modeless, resizable window with full detail view and editor for each objective
  - Objective Linkage Panel: Visual link and reference to originating objective
  - Approval Workflow Panel: Approve/reject/return controls for pending objectives
  - Audit Trail Viewer: Timeline of all changes for each objective
4. Key Data Modules
Objective
  - id (int)
  - incident_id (int)
  - originating_objective_id (nullable int)
  - description (text)
  - status (enum: pending, approved, assigned, in_progress, completed, cancelled)
  - assigned_section_id (nullable int)
  - priority (enum: low, normal, high, urgent)
  - due_time (datetime)
  - customer (text) // Name of customer or requesting party
  - created_by (user id)
  - created_at (datetime)
  - updated_at (datetime)
  - closed_at (nullable datetime)
AuditLog
  - id (int)
  - task_id (int)
  - user_id (int)
  - timestamp (datetime)
  - action (enum: create, update, status_change, approve, reject, assign, comment)
  - details (text)
Comment
  - id (int)
  - task_id (int)
  - user_id (int)
  - timestamp (datetime)
  - text (text)
5. UI Components
  - Objective List/Table (filter, sort, search, batch actions)
  - Objective detail window (modeless, resizable; fields: description, status, assignment, objective, audit, comments)
  - Objective linkage panel (popover/modal for objective details)
  - Approval workflow controls (buttons for approve/reject/return)
  - Assignment dropdowns/dialogs
  - Status quick-update controls
  - Comments panel (threaded, with notifications)
  - Audit trail timeline
Objective Detail Window Tabs
Tab 1: Narrative
  - Read-only, sortable table with columns:
o	Date/Time
o	Entry
o	Entered By
o	Critical (rows highlight red if Yes)
  - Narrative entries are text-editable only by Admin users.
  - The “Critical” flag is editable by any user (Yes/No toggle; Yes highlights row red).
Tab 2: Strategies
  - Editable two-column table:
o	Strategy (free text; describes the specific action or approach)
o	Entered By (user who entered/updated the strategy)
  - Users can add, edit, or delete strategies as needed.
Tab 3: Linked Tasks
  - Read-only list of tasks associated with this objective.
  - Tasks can be associated with multiple objectives.
  - Button at the top: [Create New Task] (automatically associates new task with this objective).
  - Columns will be the same as those on the task status board.
Tab 4: Approvals
  - (To be defined: will handle approval workflow/status/actions.)
Tab 5: Customer
  - Information about the requesting customer/agency and contact details (free text fields for name, agency, contact info, request number, etc.).
Tab 6: Log
  - Full audit trail and comment history for this objective.
  - Read-only, sorted chronologically.
6. API Endpoints
```
  - GET /api/planning/objectives – List/filter all objectives
  - POST /api/planning/objectives – Create new objective
  - PUT /api/planning/objectives/{id} – Update/edit objective
  - POST /api/planning/objectives/{id}/approve – Approve objective
  - POST /api/planning/objectives/{id}/reject – Reject or return objective
  - POST /api/planning/objectives/{id}/assign – Assign/reassign objective
  - POST /api/planning/objectives/{id}/status – Update status
  - POST /api/planning/objectives/{id}/comment – Add comment
  - GET /api/planning/objectives/{id}/history – Fetch full audit log
```
7. Database Tables
```
  - strategic_tasks
  - audit_logs
  - comments
```
8. Inter-Module Connections
  - Objectives Module: Link objectives to originating objectives
  - Personnel/Teams: Assign and track objective responsibility
  - Forms Module: Strategic objectives populate relevant ICS forms (e.g., 202, 204)
  - Status Boards: Show objective status and progress in dashboards
  - Audit Trail: Log all actions system-wide
9. Special Features / Notes
  - All changes and status transitions are audit-logged and timestamped
  - Approval workflow enforces review before assignment
  - Objective-objective linkage allows for comprehensive operational traceability
  - Threaded comments enable collaboration and handoffs
  - Objective Detail Window is modeless and resizable for side-by-side workflow
  - Full export/reporting capability for incident reviews and after-action reports

 
## Module 3: Operations
1. Module Name & Description
The Operations Module coordinates tactical field execution of tasks, tracks live team status, and manages assignments. It provides real-time situational awareness for operations leaders and integrates with Planning, Communications, and Personnel modules.
2. Primary Functions
  - - View and manage task assignments from Planning
  - - Track real-time task progress and field updates
  - - Display personnel and unit assignments
  - - Log field activity and status changes
  - - Interact with communications and resource logs
  - - Interface with ICS 204, 214, and 215 forms
3. Submodules / Tools
  - - Task Action Log: Maintains a chronological activity history for each task, including status changes, comments, field updates, and attached logs
  - - Team & Section Loggers (ICS 214): Each team/unit and the overall Operations section will have its own ICS 214-compatible logging view to track activities, changes, and incident actions
  - - Rapid Assignment Tool: Drag-and-drop interface for assigning tasks to available units or personnel in real time. Useful for contingency response and last-minute adjustments.
  - - Assignment Viewer: Displays active and upcoming tasks by section/unit
  - - Task Status Updater: Allows field teams or supervisors to update status (Not Started, In Progress, Complete, Blocked)
  - - Unit Status Tracker: Shows current position, availability, and team composition for each unit
  - - Operations Log (ICS 214): Auto-populates based on actions, can be manually edited
  - - Form Link Panel: Pulls in related ICS 204/215 data for task reference
4. Key Data Modules
  - - TaskActionLog:
  - - id, task_id, author_id, timestamp, action_type, note, attachment_url
  - - TeamLog:
  - - id, team_id, entered_by, text, timestamp
  - - SectionLog:
  - - id, section, entered_by, text, timestamp
  - - OpsAssignment:
  - - id, task_id, assigned_to, start_time, end_time, status, notes
  - - UnitStatus:
  - - id, unit_id, location, status, available_personnel[], timestamp
  - - OpsLogEntry:
  - - id, incident_id, entered_by, text, timestamp, related_task_id
5. UI Components
  - - Task board by unit or section
  - - Assignment update interface
  - - Unit availability dashboard
  - - 214 log feed with filtering by user/task/unit
6. API Endpoints
```
  - - GET /api/operations/assignments
  - - POST /api/operations/assignments
  - - PUT /api/operations/assignments/{id}
  - - GET /api/operations/units
  - - POST /api/operations/units
  - - GET /api/operations/logs
  - - POST /api/operations/logs
```
7. Database Tables
```
  - - task_action_logs
  - - team_logs
  - - section_logs
  - - ops_assignments
  - - unit_status
  - - ops_log_entries
```
8. Inter-Module Connections
  - - Planning Module: Tasks are received and status updates are fed back
  - - Personnel Module: Assignments linked to individuals and teams
  - - Communications Module: Status updates may trigger alerts/messages
  - - Forms Module: ICS 204 and 214 integration
9. Special Features / Notes
  - - Every task maintains a self-contained action log with a chronological activity record
  - - Each team/unit and the Operations section has a 214-based log stream to support official documentation and after-action reviews
  - - Rapid Assignment Tool enables dynamic reassignment in response to emerging operational needs
  - - Color-coded status tracking for quick situational scanning
  - - Blocked tasks can be flagged and escalated
  - - Integrated time tracking for resource management
  - - Mobile-compatible views for field updates
  - - Logs tied to individual personnel, teams, or specific tasks
## Module 3-1: Taskings
Module Name & Description
This submodule provides Operations personnel with a centralized interface to manage tactical and logistical taskings during an incident. It enables:
  - Task ingestion: Receive assignment requests (reflex taskings) from Planning or Command
  - Task creation & editing: Define new tasks with detailed attributes
  - Assignment & tracking: Assign tasks to teams, units, or individuals and monitor status
  - Notifications & alerts: Notify recipients via the Communications module
  - Form integration: Quick-print relevant ICS forms (e.g., ICS 213 General Message, ICS 215 Operational Planning Worksheet, ICS 218 Resource Status Change)
2. Primary Functions
  - Task List Dashboard: Paginated, sortable, and filterable grid showing all active and archived tasks
  - Task Detail View: Full metadata display (description, priority, due time, assigned unit, creator, ICS form links)
  - New Task Wizard: Step-by-step form to capture all required fields and suggest ICS form templates
  - Bulk Actions: Enable batch assignment, status updates, or printing multiple form outputs
  - Real-time Status Updates: Reflect changes instantly in the dashboard and send notifications
  - Role-Based Access: Only Operations Officer and above can create or delete; Team Leads can update status
3. Submodules / Tools
### Task Detail Window
4. Key Data Modules
Table Name	Purpose	Key Columns (non-exhaustive)
tasks	Core task records	id (PK), title, description, priority, status, task_type_id, category_id, assigned_to, created_by, created_at, due_time, ics_form_link, updated_at
task_types	Lookup of task types (filtered by category)	id (PK), category_id (FK), name
categories	Lookup of task categories	id (PK), name
narrative_entries	Logs of narrative updates	id (PK), taskid (FK), timestamp, entry_text, entered_by, team_number, critical_flag, entered_at
task_teams	Which teams are assigned to each task	id (PK), taskid (FK), team_id (FK), sortie_number, status, assigned_ts, briefed_ts, enroute_ts, arrival_ts, discovery_ts, complete_ts
teams	Master list of teams	id (PK), name, leader_id (FK→personnel), leader_phone
task_personnel	Personnel on a task	id (PK), task_id (FK), personnel_id (FK), role, organization, time_assigned
personnel	Master list of personnel	id (PK), name, phone, organization, …
task_vehicles	Vehicles on a task	id (PK), taskid (FK), vehicle_id (FK)
vehicles	Master list of vehicles	id (PK), type, identifier, …
assignment_ground	“Ground Information” subtabs for task	taskid (PK & FK), prev_search_efforts, time_allocated, size, pod_responsive, pod_unresponsive, pod_clues, dropoff_instructions, pickup_instructions
assignment_air	“Air Information” subtabs for task	taskid (PK & FK), wmirs_area, dep_airport, dest_airport, etd, ete, … (all fields from Air Information)
radio_channels	Radios tied to a task (ICS 205 fields)	id (PK), taskid (FK), channel_name (FK→ics205_channels), function, zone, channel_number, rx_freq, rx_tone, tx_freq, tx_tone, mode, remarks
ics205_channels	Master list of ICS 205 channel definitions	channel_name (PK & FK), zone, channel_number, rx_freq, rx_tone, tx_freq, tx_tone, mode, remarks
debriefs	Debrief header records	id (PK), task_id (FK), sortie_number, debriefer_id (FK→personnel), debrief_type, created_at, updated_at
debrief_ground_sar	Ground-SAR debrief detail	debrief_id (PK & FK), assignment_summary, search_efforts, unable_to_search, clues_tracks_signs, hazards_encountered, suggestions, time_entered, time_exited, time_spent, conditions_clouds, precipitation, light_conditions, visibility, terrain, ground_cover, wind_speed
debrief_area_search	Area Search Supplement	debrief_id (PK & FK), num_searchers, time_spent, search_speed, area_size, spacing, visibility_distance, vis_determination, areas_skipped, pattern_description, additional_comments
debrief_tracking	Tracking Team Supplement	debrief_id (PK & FK), likelihood, existing_trap_desc, erased_trap_desc, new_trap_desc, route_taken, discontinue_reason
debrief_hasty_search	Hasty Search Supplement	debrief_id (PK & FK), visibility, attract_methods, hearing_conditions, trail_conditions, offtrail_conditions, map_accuracy, found_features, tracking_conditions, hazards_attractions
debrief_air_general	Air (General) Debrief	debrief_id (PK & FK), flight_plan_closed, atd, ata, hobbs_start, hobbs_end, hobbs_total, tach_start, tach_end, fuel_used, oil_used, fuel_oil_cost, receipt_no, summary, results, weather, remarks, sortie_effectiveness, not_success_reason
debrief_air_sar	Air (SAR Worksheet) Debrief	debrief_id (PK & FK), area_name, grid, nw_lat, nw_long, ne_lat, ne_long, sw_lat, sw_long, se_lat, se_long, pattern, visibility_nm, altitude_agl, speed_knots, track_spacing, terrain, cover, turbulence, pod, time_to_search, time_started, time_ended, time_in_area, time_from_area, total_sortie_time, crew_remarks, effectiveness_rating, visibility_rating
audit_logs	Change log entries	id (PK), taskid (FK), timestamp, field_changed, old_value, new_value, changed_by
attachments	Uploaded files and form outputs	id (PK), taskid (FK), filename, file_type, uploaded_by, timestamp, size, version
planning_links	Links tasks to strategic goals	id (PK), taskid (FK), goal_id (FK→strategic_goals), checklist_data (JSON)
strategic_goals	Master list of planning goals	id (PK), name, description

5. UI Components
5.1 Task Screen Layout
  - Main Status Board: Full-page, row-based view where each task occupies one row; column headers allow sorting and reordering. (Columns to be defined later.)
  - Row Interaction: Single-click selects a row; double-click opens the Task Detail window.
5.2 Task Detail Window
Design Note: Layout and element grouping should draw inspiration from the CAD-style screenshot provided, but this submodule’s UI should not be an exact copy—use our app’s theme, clean spacing, and simplified controls.
A floating, draggable window containing:
  - Window Background: Color varies by Task Category.
  - Top Toolbar (4 dropdowns):
### Category: Dropdown with predefined options: <New Task>(Default)/Air SAR/Damage Assessment/Ground SAR/Logistics Support/Other/Photography/Relocation
### Task Type: Dropdown list populated from a predefined CSV of task types, dynamically filtered based on the selected Category.
### Priority: Predefined choices: Low, Medium, High, Critical.
### Status (Task): Predefined workflow states: Draft, Planned, In Progress, Completed, Cancelled.
Note: This dropdown controls the overall task status only; the Status column in the Teams tab uses its own set of team-specific statuses.
### Task ID: Free-text input for entering or overriding the unique Task Identifier.
  - Location Bar:** Single-line free-text input for location or assignment name.
  - Narrative Entry Box: Large multiline input; pressing Enter appends to the narrative log.
Dropdown Options Reference:
  - Categories: <New Task>(Default)/Air SAR/Damage Assessment/Ground SAR/Logistics Support/Other/Photography/Relocation
  - Priorities: Low, Medium, High, Critical
  - Statuses (Task): Draft, Planned, In Progress, Completed, Cancelled Low, Medium, High, Critical
Bottom Tab Panel
The Task Detail window includes a tab panel with ten tabs:
### Narrative
Read only, sortable table with columns:
o	Date/Time
o	Entry
o	Entered By
o	Team Name (Only populates if the person who made the entry is assigned to a team)
o	Critical (rows highlight red if Yes)
o	ICS 214 Export button
Text editable only by admin; Critical flag editable by any user.
### Teams
Sortable table with columns:
o	Sortie Number (optional)(Manually entered here)
o	Team Name
o	Team Leader
o	Team Leader Phone Number
o	Status: Dropdown presenting only the statuses valid for the task’s category or type, enabling quick manual updates.
o	Assigned: Date/time stamp set when assigned.
o	Briefed: Date/time stamp set on “Briefed.”
o	Enroute: Date/time stamp set on “En Route.”
o	Arrival: Date/time stamp set on “On Scene.”
o	Discovery: Date/time stamp set on “Discovery/Find.”
o	Complete: Date/time stamp set on “Complete.”
o	Primary: Boolean flag that indicates if the team is primary on the task.  Only one team may be primary on a task.  The first team assigned to a task is automatically marked as primary.
Actions: Add Team, Remove Team, Change Status (triggers timestamp update).
### Personnel
Table view, sortable by any column:
o	Auto Populate: Entries derive from team assignments; manual add/remove allowed.
o	Columns:
	ID
	Name
	Role
	Phone Number
	Organization
	Team Name
	Time Assigned
Actions: Add/Remove Personnel, Edit Time Assigned (inline date/time picker).
Features: Filtering by Organization/Role; Bulk operations.
### Vehicles
Table view, sortable by any column:
o	Auto Populate: Entries derive from team assignments; manual add/remove not permitted.
o	Columns:
	Vehicle ID
	Type
	Team Assignment
Actions: Reassign Vehicle (inline dropdown).
Features: Live status indicator; Inventory filter.
### Assignment Details
Goal: Support CAPF 109, SAR 104, and ICS 204 by capturing form-specific details not located elsewhere in the tab.
Contains two subtabs:
o	Ground Information (default) 
	Previous and Present Search Efforts in Area
	Time Allocated
	Size of Assignment
	Expected POD
### Options of High/Medium/Low in categories of Responsive Subj, Unresponsive Subj, Clues
	Drop off and Pickup instructions
o	Air Information — Aviation assignment details
	WMIRS Area of Operations
	Dep. Airport
	Dest. Airport
	ETD
	ETE
	Other Aircraft in Area (Location & Callsign)
	Ground Teams in Area (Location & Callsign)
	Sortie Objectives
	Sortie Deliverables
	Actions To Be Taken on Objectives & Deliverables
	Route of Flight
	Altitude Assignment & Restrictions
	Airspeed Expected & Restrictions
	Aircraft Separation (Adjoining Areas)
	Emergency/Alternate Fields
	Military Low Altitude Training Routes
	Hazards to Flight
	Sortie Search Plan
### Search Pattern
### Search Visibility (NM)
### Search Altitude (AGL)
### Search Speed (Knots)
### Track Spacing (NM)
### Terrain
### Flat/Rolling Hills/Rugged Hills/Mountainous
### Cover
### Open/Moderate/Heavy/Light Snow/Heavy Snow
### Turbulence
### Light/Moderate/Heavy
### Probability of Detection
### Time to Search Area
### Time Started Search
### Time Ended Search
### Time in Search Area
### Time from Search Area
### Time From Search Area
### Total Sortie Time
### Communications
Table mirroring ICS 205 Basic Radio Channel Use; only Channel Name and Function editable, others read only. Data populates from ICS 205 via selected channel:
o	Channel Name (dropdown)
o	Zone
o	Channel Number
o	Function (editable)
o	RX Frequency
o	RX Tone/NAC
o	TX Frequency
o	TX Tone/NAC
o	Mode (A/D/M)
o	Remarks
### Debriefing
Post-task review interface capturing debrief notes, lessons learned, and personnel feedback. Initial screen contains a log of completed debriefs.  Button at the top labeled “Add Debrief”.  This opens a window asking for the sortie number, Debriefer (Enter ID to reference name) and a checklist of different debrief types.  Types include Ground (SAR), Area Search Supplement, Tracking Team Supplement, Hasty Search Supplement, Air (General), Air (SAR Worksheet).  Ground (SAR) must be selected in order for area search, tracking team, or hasty search to be selected.  Air (General) must be selected in order for Air (SAR Worksheet) to be selected.  This check list selects which forms will be displayed.  After entering sortie number, debriefer ID, and selecting forms, the user clicks create which opens up the appropriate forms.  After saving the form, debriefs may be edited.  Information is sent to the planning debrief module and flagged for review.
o	Ground (SAR) 
	Assignment Summary (Free Text)
	Describe Search Efforts in Assignment (Free Text)
	Describe Portions Unable to Search (Free Text)
	Describe Clues/Tracks/Signs or any Interviews (Free Text)
	Describe any Hazards or Problems Encountered (Free Text)
	Suggestions for Further Search Efforts In or Near Assignment (Free Text)
	Time Entered
	Time Exited
	Time Spent
	Conditions
### Clouds
### Clear/Scattered/Broken/Overcast
### Precipitation
### None/Rain/Scattered/Snow
### Light Conditions
### Bright/Dull/Near Dark/Night
### Visibility
### > 10 Miles/> 5 Miles/> 1 Mile/< 1 Mile
### Terrain
### Flat/Rolling Hills/Rugged Hills/Mtns
### Ground Cover
### Open/Moderate/Heavy/Other
### Wind Speed
### Calm/< 10 mph/< 20 mph/< 30 mph
	Attachments
### Debriefing Maps
### Original Briefing Document
### Supplemental Debriefing Forms
### Interview Log
### Other
o	Area Search Supplement
	Number of Searchers
	Time Spent Searching
	Search Speed
	Area Size (Actually Searched)
	Spacing
	Visibility Distance (Free Text)
	How was Visibility Distance Determined (Free Text)
	Types of Areas Skipped Over (Ie Heavy Brush, Wetlands, Cliffs) (Free Text)
	Describe the Direction and Pattern of your Search (Free Text)
	Comments for Additional Area Searching of this Assignment (Free Text)
o	Tracking Team Supplement
	Discuss Likelihood of Finding Tracks or Sign on the Trails (Free Text)
	Describe the Location and Nature of Existing Track Traps (Free Text)
	Did You Erase Any Track Traps (Free Text)
	Did You Create Any New Track Traps (Free Text)
	Describe the Route Taken by Any Tracks You Followed (Free Text)
	Why Did You Discontinue Following These Tracks (Free Text)
	Attachments
### Individual Track Sketches Attached
### Track Trap Summary Sketches Attached
o	Hasty Search Supplement
	Visibility During Search (Day/Dusk/Night/Other) (Free Text)
	Describe Your Efforts to Attract a Responsive Subject (Free Text)
	Describe Ability to Hear a Response (Background Noise) (Free Text)
	Describe the Trail Conditions (Free Text)
	Describe the Off-Trail Conditions (Free Text)
	Does the Map Accurately Reflect the Trails (Free Text)
	Did You Locate Features That Would Likely Contain the Subject (Free Text)
	How Are the Tracking Conditions (Free Text)
	Describe any Hazards or Attractions You Found (Free Text)
o	Air (General)
	Flight Plan Closed (Boolean Yes/No)
	ATD
	ATA
	Hobbs Start
	Hobbs End
	Hobbs To/From
	Hobbs in Area
	Hobbs Total
	Tach Start
	Tach End
	Fuel Used (Gal)
	Oil Used (Qt)
	Fuel & Oil Cost
	Receipt #
	Summary (Free Text)
	Results/Deliverables (Free Text)
	Weather Conditions (Free Text)
	Remarks (Free Text)
	Sortie Effectiveness
### Successful/Marginal/Unsuccessful/Not Flown/Not Required
	Reason (if not successful)
### Weather/Crew Unavailable/Aircraft Maintenance/Customer Cancellation/Equipment Failure/Other
	Attachments/Documentation
### CAPF 104A SAR
### CAPF 104B Recon Summary
### ICS 214 Unit Log
### Receipts
### AIF ORM Matrix
o	Air (SAR Worksheet)
	Search Area
### Name
### Grid
### NW Corner (Lat/Long)
### NE Corner (Lat/Long)
### SW Corner (Lat/Long)
### SE Corner (Lat/Long)
	Sortie Search Actual
### Search Pattern
### Search Visibility (NM)
### Search Altitude (AGL)
### Search Speed (Knots)
### Track Spacing (NM)
### Terrain
### Flat/Rolling Hills/Rugged Hills/Mountainous
### Cover
### Open/Moderate/Heavy/Light Snow/Heavy Snow
### Turbulence
### Light/Moderate/Heavy
### Probability of Detection
### Time to Search Area
### Time Started Search
### Time Ended Search
### Time in Search Area
### Time from Search Area
### Time From Search Area
### Total Sortie Time
	Crew Remarks and Notes
### Effectiveness
### Excellent/Good/Fair/Poor
### Visibility
### Excellent/Good/Fair/Poor
### Log
System audit trail, sortable table with columns:
o	Timestamp
o	Field Changed
o	Old Value
o	New Value
o	Changed By
Features: Filtering by date/field; Export CSV; Keyword search.
### Attachments/Forms
Table with columns:
o	Filename
o	Type
o	Uploaded By
o	Timestamp
o	Size
Actions: Upload File, Download/Preview, Annotate.
Features: Version control; File size warnings.
Forms Generation: Generate Forms button for CAPF 109, SAR 104, ICS 204, etc.
### Planning
o	Purpose: Link task to strategic goals; provide checklist for planning items.
o	Fields: TBD.
Close/Minimize Controls: Standard window chrome for hiding or closing the window.:** Standard window chrome for hiding or closing the window.
6. API Endpoints
```
### Tasks
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings	List tasks (filtering, paging, sorting)	Query params: status, priority, assigned_to, date_from, date_to, page, page_size, sort_by	{ tasks: Task[], total: number, page, page_size }
POST	/api/operations/taskings	Create a new task	{ title, description, category_id, task_type_id, priority, assigned_to, due_time?, task_id? }	{ id: UUID, ...full Task }
GET	/api/operations/taskings/{taskId}	Retrieve a single task (with nested sub-resources)	—	{ ...full Task, narrative:[], teams:[], ... }
PUT	/api/operations/taskings/{taskId}	Update all metadata on a task	{ title?, description?, category_id?, task_type_id?, priority?, assigned_to?, due_time?, task_id?, ics_form_link? }	{ ...updated Task }
PATCH	/api/operations/taskings/{taskId}/status	Update only the task’s status	`{ status: Draft	Planned
DELETE	/api/operations/taskings/{taskId}	Archive/delete a task	—	204 No Content
```
### Narrative Entries
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/narrative	List narrative log entries	Query params: sort_by, order, page, page_size	{ entries: NarrativeEntry[], total }
POST	/api/operations/taskings/{taskId}/narrative	Append a new narrative entry	{ entry_text, entered_by, team_number?, critical_flag? }	{ id: number, timestamp, ... }
PATCH	/api/operations/taskings/{taskId}/narrative/{entryId}	Update critical flag (any user)	{ critical_flag: boolean }	{ id, critical_flag, timestamp }
### Team Assignments
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/teams	List teams on a task	—	{ teams: TaskTeam[] }
POST	/api/operations/taskings/{taskId}/teams	Assign a new team	{ team_id, sortie_number? }	{ id: number, assigned_ts }
PATCH	/api/operations/taskings/{taskId}/teams/{ttId}	Change team status (auto-stamp)	{ status: string }	{ id, status, updated_ts }
DELETE	/api/operations/taskings/{taskId}/teams/{ttId}	Remove a team assignment	—	204 No Content
### Personnel
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/personnel	List personnel on a task	—	{ personnel: TaskPersonnel[] }
POST	/api/operations/taskings/{taskId}/personnel	Add a person	{ personnel_id, role, organization, time_assigned? }	{ id, time_assigned }
PATCH	/api/operations/taskings/{taskId}/personnel/{pId}	Update time assigned	{ time_assigned: ISODateTime }	{ id, time_assigned }
DELETE	/api/operations/taskings/{taskId}/personnel/{pId}	Remove from task	—	204 No Content
### Vehicles
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/vehicles	List vehicles on a task	—	{ vehicles: TaskVehicle[] }
POST	/api/operations/taskings/{taskId}/vehicles	Assign a vehicle	{ vehicle_id }	{ id, task_id, vehicle_id }
PATCH	/api/operations/taskings/{taskId}/vehicles/{vId}	Reassign to a different team	{ team_assignment: string }	{ id, team_assignment }
DELETE	/api/operations/taskings/{taskId}/vehicles/{vId}	Remove a vehicle	—	204 No Content
### Assignment Details
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/assignment	Fetch both ground & air details	—	{ ground: {...}, air: {...} }
PUT	/api/operations/taskings/{taskId}/assignment/ground	Update ground information	{ prev_search_efforts, time_allocated, size, expected_pod_responsive, expected_pod_unresponsive, expected_pod_clues, dropoff_instructions, pickup_instructions }	{ ground: {...} }
PUT	/api/operations/taskings/{taskId}/assignment/air	Update air information	{ wmirs_area, dep_airport, dest_airport, etd, ete, /* all other air fields */ }	{ air: {...} }
### Communications
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/communications	List radio channels for task	—	{ channels: RadioChannel[] }
POST	/api/operations/taskings/{taskId}/communications	Add a radio channel	{ channel_name, function }	{ id, channel_name, function }
PATCH	/api/operations/taskings/{taskId}/communications/{cId}	Update function for a channel	{ function: string }	{ id, function }
DELETE	/api/operations/taskings/{taskId}/communications/{cId}	Remove a radio channel	—	204 No Content
### Debriefing
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/debriefs	List debrief records	—	{ debriefs: Debrief[] }
POST	/api/operations/taskings/{taskId}/debriefs	Create new debrief	{ sortie_number, debriefer_id, debrief_type, /* additional fields per type */ }	{ id, created_at }
PUT	/api/operations/taskings/{taskId}/debriefs/{dId}	Update an existing debrief	{ /* fields as above, per debrief type */ }	{ id, updated_at }
DELETE	/api/operations/taskings/{taskId}/debriefs/{dId}	Delete a debrief record	—	204 No Content
### Audit Logs
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/logs	Fetch the change history	Query params: field?, date_from?, date_to?	{ logs: AuditLog[] }
### Attachments/Forms
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/attachments	List all attachments and forms	—	{ attachments: Attachment[] }
POST	/api/operations/taskings/{taskId}/attachments	Upload a file or form template	multipart/form-data: file, type, generate_forms?	{ id, filename, url }
DELETE	/api/operations/taskings/{taskId}/attachments/{aId}	Remove an attachment	—	204 No Content
### Planning Links
Method	Path	Description	Request Body	Response
GET	/api/operations/taskings/{taskId}/planning	Fetch linked strategic goals	—	{ links: PlanningLink[] }
POST	/api/operations/taskings/{taskId}/planning	Link a new strategic goal	{ goal_id, checklist_data (JSON) }	{ id, goal_id, checklist_data }
DELETE	/api/operations/taskings/{taskId}/planning/{linkId}	Unlink a strategic goal	—	204 No Content
 All endpoints use the incident-specific database connection and emit real-time notifications via the Communications WebSocket.

7. Database Tables
```

```
8. Inter-Module Connections
Communications
  - Send/receive real-time notifications and alerts when tasks are created, updated, or completed
  - Populate the “Communications” tab’s radio channels data from the ICS 205 channel definitions
  - Use the IM/213 messaging system for cross-team alerts
  - Planning
  - Ingest reflex taskings and strategic task requests from the Planning (Strategic Tasks) module
  - Link tasks to strategic goals via the Planning tab (and push debrief outcomes back into Planning’s reviews)
  - Personnel & Role Management
  - Lookup and validate personnel IDs for “Created By,” “Entered By,” Debriefer, etc.
  - Auto-populate the Personnel tab when assigning teams
  - Enforce Role-Based Access (e.g., only Officers can create/delete tasks)
  - ICS Forms & Documentation
  - Retrieve form templates (ICS 204, ICS 213, CAPF 109, SAR 104, etc.)
  - Generate and store completed forms via the Attachments/Forms tab’s “Generate Forms” action
  - Log/Audit Trail
  - Hook into the global Audit Logs system to record every CRUD operation on tasks, narrative entries, team assignments, debriefs, etc.
  - Surface filtered log views in the Log tab
  - Status Boards
  - Optionally publish high-level task summaries to any Status Boards (e.g., overall Progress board)
  - Reference Library
  - Provide lookup help text or reference links for form instructions, radio channel standards, debrief checklists, etc.
  - Data Persistence/Core
  - Use the incident-specific database in core/data/ for storing all tasking tables and relationships
  - Integrate with any shared “master” lookup tables (e.g., ICS 205 channels, personnel directory, vehicle inventory)
  - Strategic Tasks (Planning Submodule)
  - Accept “tasking” requests from the Strategic Tasks module and allow planners to mark items as “reflex taskings” back into Operations

9. Special Features / Notes

 
## Module 4: Logistics
1. Module Name & Description
The Logistics Module manages all resource, supply, and equipment operations for an incident. It supports the entire lifecycle of resource requests—from creation and approval to assignment and fulfillment—while maintaining accurate real-time inventory of equipment, supplies, vehicles, and personnel-related logistical support. This module provides transparent workflows, audit trails, and critical support for both field and command personnel.
2. Primary Functions
  - Resource Request Management: Submit, track, approve, and fulfill requests for personnel, equipment, and supplies.
  - Inventory Tracking: Manage inventory levels, check-in/check-out equipment, and maintain up-to-date availability.
  - Assignment Workflow: Assign resources and equipment to incidents, teams, or individuals; track status and location.
  - Fulfillment & Delivery Tracking: Coordinate delivery teams, monitor fulfillment progress, and provide real-time status updates.
  - Integration with Forms: Auto-generate and populate ICS forms (e.g., 213-RR, 204, 211, 218, 220) using logistics data.
  - Notifications & Alerts: Automated notifications for status changes, overdue equipment, or request fulfillment.
  - Audit & Change Log: Maintain a full history of requests, assignments, and inventory actions for transparency and accountability.
3. Submodules / Tools
  - Resource Request Submodule: Handles creation, approval, assignment, and fulfillment of resource requests.
  - Equipment Submodule: Tracks non-vehicle equipment inventory, check-in/check-out status, and assignment.
  - Bulk Import/Export Tool: For onboarding large inventories or generating reports via CSV.
  - Assignment Dashboard: Visual overview of resource assignments and status.
  - Notification Center: Manages in-app, email, and SMS alerts for key logistics events.
4. Key Data Modules
  - ResourceRequest: id, incident_id, requestor_id, timestamp, item_code, quantity, priority, justification, status, due_datetime, notes
  - ApprovalRecord: id, request_id, approver_id, action, timestamp, comments
  - AssignmentRecord: id, request_id, resource_id, assigned_to_id, assigned_datetime, eta, status
  - ResourceItem: item_code, description, unit, available_quantity, location
  - EquipmentItem: id, name, type_id, serial_number, status, location, current_holder_id, tags, created_at, updated_at
  - CheckTransaction: id, equipment_id, actor_id (user or team), incident_id, action (check_out/check_in), timestamp, notes
5. UI Components
  - Resource Request Status Board: Table view with search, filters, color-coded status, and bulk actions.
  - Resource Request Detail Window: Modal for viewing/editing requests, with tabs for Order, Approval, Attachments, Supplier.
  - Equipment Inventory Table: Sortable/filterable view of all equipment items and status.
  - Check-In/Out Wizard: Guided UI for equipment assignment and return.
  - Assignment Dashboard: Overview panel for all ongoing assignments.
  - Bulk Import/Export Interface: Stepper for mapping/importing CSV files.
6. API Endpoints
```
  - /api/logistics/requests (GET, POST): List, create resource requests
  - /api/logistics/requests/{id} (GET, PUT): Retrieve/update specific request
  - /api/logistics/requests/{id}/approvals (GET, POST): Approval workflow
  - /api/logistics/requests/{id}/assign (POST): Assign resources
  - /api/logistics/equipment (GET, POST): List/create equipment items
  - /api/logistics/equipment/{id} (GET, PUT, DELETE): Manage equipment item
  - /api/logistics/equipment/{id}/checkout (POST): Assign equipment
  - /api/logistics/equipment/{id}/checkin (POST): Return equipment
  - /api/logistics/items (GET): List available inventory items
  - /api/logistics/notifications (GET): Fetch logistics-related notifications
```
7. Database Tables
```
  - logistics_resource_requests
  - logistics_request_approvals
  - logistics_request_assignments
  - logistics_resource_items
  - equipment_items
  - check_transactions
  - logistics_notifications
```
8. Inter-Module Connections
  - Planning: Shares resource requirements and receives forecasts for planning.
  - Operations: Notifies field teams, updates status on completion of tasks.
  - Finance/Admin: Tracks expenditures and cost approvals.
  - Personnel & Role Management: Lookup users for assignments and delivery.
  - Forms & Documentation: Generates and auto-populates relevant ICS forms.
  - Status Boards: Displays logistics statuses, overdue returns, and request tracking.
9. Special Features / Notes
  - State Locking & Reactivation: Requests that are complete, cancelled, or denied are locked; denied/cancelled requests can be reactivated.
  - Offline Support: Mobile/offline data entry with sync upon reconnect.
  - Bulk Actions: Multi-select and bulk update for requests or equipment.
  - Attachment Support: Add photos, spec sheets, quotes to requests.
  - Customizable Priority Levels: Routine, Urgent, Emergency.
  - Audit Trail: Full change history on all records.
  - Role-Based Access Control: Restricts critical actions to authorized users.
  - Integration with Mobile App: Supports mobile subincidents and updates.
## Module 4-1: Resource Request 
Resource Request Module Design Document
1. Module Name & Description
**Logistics Resource Request** is the submodule within the Logistics section that enables personnel to create, track, manage, and fulfill requests for resources (personnel, equipment, supplies) during an incident. It streamlines the request-to-delivery workflow, ensuring timely provisioning and transparent status updates.

2. Primary Functions
  - **Request Creation:** Capture details for new resource requests, including item, quantity, priority, justification, and required delivery time.
  - **Approval Workflow:** Route requests through one or more approvers with options to **Approve**, **Deny**, or **Return for Information**.
  - **Assignment & Fulfillment:** Allocate available resources, assign delivery teams, and track fulfillment status.
  - **Status Tracking:** Provide real-time dashboards showing pending, approved, in-progress, and completed requests.
  - **Notifications & Alerts:** Notify stakeholders of status changes, upcoming delivery windows, or issues.
  - **Form Integration:** Automatically generate and print ICS 213-RR forms based on request data.
  - **Request Deletion:** Enable users to delete resource requests from the system.
  - **Request Reactivation:** Allow cancelled or denied requests to be reactivated, resetting their status to Submitted.

3. Submodules/Tools
  - **Request Form Builder:** Guided UI for entering request details.
  - **Approval Panel:** View, comment on, and action pending requests.
  - **Assignment Dashboard:** Visual interface (list/map) for allocating resources and scheduling deliveries.
  - **Fulfillment Tracker:** Timeline view showing each step from approval to delivery.
  - **Notification Center:** Configurable alerts via in-app, email, or SMS.
  - **Report Generator:** Export request logs or summaries in PDF/Excel.

### Key Data Models
  - **ResourceRequest** (id, incident_id, requestor_id, timestamp, item_code, quantity, priority, justification, status, due_datetime, notes)
    - **status (enum):** Submitted, In Progress, Approved, Ordered, Fulfilled, Complete, Cancelled, Denied
  - **ApprovalRecord** (id, request_id, approver_id, action, timestamp, comments)
  - **AssignmentRecord** (id, request_id, resource_id, assigned_to_id, assigned_datetime, eta, status)
  - **ResourceItem** (item_code, description, unit, available_quantity, location)
  - **Notification** (id, request_id, recipient_id, type, sent_timestamp, read_flag)

5. UI Components
  - **Global Search Box:** An input field above the status board to quickly search requests by Request ID or keywords.
  - **Resource Requests Status Board:** Full-width table where each row represents a resource request.
    - **Configurable Columns & Saved Views:** Users can hide/show columns, reorder them, and save custom board views (e.g., "My Pending", "Urgent Only").
    - **Default Column Visibility:** A sensible set of columns is shown by default; users may customize visibility via a column manager.
    - **Sorting & Filtering:** Clickable column headers support ascending/descending sort; header dropdowns allow per-column filter criteria.
    - **Color-Coded Status Badges:** Status values are displayed as colored badges (e.g., green for Complete, red for Denied/Cancelled, blue for In Progress) for quick scanning.
    - **Row Lock & Grey-Out:** Rows with status **Complete**, **Cancelled**, or **Denied** are greyed out and locked, disabling selection and inline actions.
  - **New Request Button:** Above the status board; opens the Resource Request Detail Window in modal or modeless mode.
  - **Inline Filters Bar:** Quick-access buttons above the table for common filters (e.g., Emergency, Pending).
  - **Bulk Action Toolbar:** Appears when rows are selected; actions include bulk approve, bulk assign, delete requests, or reactivate cancelled/denied requests. Each destructive action prompts a confirmation dialog to prevent accidental operations.
  - **Resource Request Detail Window:**
    - **State Locking & Reactivation:**
      - If status is **Complete**, window is fully read-only: fields disabled and action toolbar hidden.
      - If status is **Cancelled** or **Denied**, show a **Reactivate** button to reset status to Submitted.
    - **Overview Panel (Top):** Read-only display of core fields, including multi-role approval timestamps:
      - Request Number
      - Requestor
      - Date/Time Submitted
      - Category
      - Priority
      - Current Status
      - Due Date/Time
      - Section Chief/Command Staff Approval: Approver Name, Date/Time
      - RESL Approval: Approver Name, Date/Time
      - Logistics Approval: Approver Name, Date/Time
      - Finance Section Approval: Approver Name, Date/Time
    - **Action Toolbar: Buttons for **Edit Request**, **Print ICS 213-RR**, **Add Attachment** (hidden when locked).
    - **Tabbed Content (Bottom): Four tabs with conditional read-only behavior:
    1. Order: A table with columns for Quantity, Kind, Type, Priority, Detailed Item Description, Requested Reporting Location, Date/Time, Order Number, ETA, and Cost. Read-only when status is ≥ Approved.
    2. Approval: Chronological approval history with approver name, action (Approve/Deny/Return for Information), timestamp, and comments. Logistics approval can include Requisition/Purchase Order Number. Sequential rule: logistics and finance cannot approve until section chief approval.
    3. Attachments: File upload gallery and notes area for spec sheets, photos, or quotes. Always editable unless request is Complete.
    4. Supplier: A table listing supplier contacts with columns Name, Phone, Email, and Fax. Read-only when status is ≥ Fulfilled.

6. API Endpoints
```
| Method | Endpoint                                | Description                                         |
| ------ | --------------------------------------- | --------------------------------------------------- |
| GET    | `/api/logistics/requests`               | List all resource requests                          |
| POST   | `/api/logistics/requests`               | Create a new request                                |
| GET    | `/api/logistics/requests/{id}`          | Retrieve details for a single request               |
| PUT    | `/api/logistics/requests/{id}`          | Update request (status, notes)                      |
| GET    | `/api/logistics/requests/{id}/approvals`| Get approval history for a request                  |
| POST   | `/api/logistics/requests/{id}/approve`  | Submit an approval action                           |
| POST   | `/api/logistics/requests/{id}/assign`   | Assign resources to a request                       |
| GET    | `/api/logistics/items`                  | List available resource items                       |
| GET    | `/api/logistics/notifications`          | Fetch user notifications                            |
| GET    | `/api/logistics/requests/stream`        | Stream real-time request updates via Server-Sent Events |
```
7. Database Tables
```
  - logistics_resource_requests
  - logistics_request_approvals
  - logistics_request_assignments
  - logistics_resource_items
  - logistics_notifications
```
8. Inter-Module Connections
  - Planning: Share resource requirements for forecasting.
  - Operations: Notify field teams about deliveries; update status on completion.
  - Finance/Admin: Send cost estimates; track expenditures per request.
  - Personnel & Role Management: Lookup users (requestors, approvers, delivery teams).
  - Forms & Documentation: Auto-populate ICS forms (213-RR, 220) from request data.

9. Special Features/Notes
  - Configurable Priority Levels: e.g., Routine, Urgent, Emergency.
  - Audit Trail: Full change log for each request, approval, and assignment; drill-down links show before/after data.
  - Attachment Support: Upload photos, spec sheets, vendor quotes.
  - Offline Mode: Mobile devices can sync offline and update when online.
  - External API Integration: Optional connectors to inventory systems.
  - Quick-Add Templates: Save common request profiles for reuse.
  - Keyboard Shortcuts Ctrl+N for New Request, Ctrl+P for Print ICS form, etc.
  - Validation Flows: Before moving to Ordered, system validates that Section Chief, RESL, Logistics, and Finance approvals are present; missing approvals trigger an error dialog listing required steps.
  - Column Views & Persistence:** Saved board views persist per-user and across sessions.

 
## Module 5: Communications 

1. Module Name & Description
The Communications Module manages all inbound, outbound, and internal messaging across the incident. It includes informal chat, structured message logging (ICS 213), and broadcast tools for alerts and status changes. It links directly with the Communications Unit Leader’s responsibilities and supports message traceability.
2. Primary Functions
  - - Facilitate unit-to-unit and user-to-user communications
  - - Log formal messages via ICS 213
  - - Manage communication assets (e.g., radio frequencies)
  - - Broadcast incident-critical alerts
  - - Track communications activity and message acknowledgments
3. Submodules / Tools
  - Chat Interface: Informal IM-style messaging between users or teams; includes timestamps and read status
  - General Message 213 System: Structured message subincident with support for replies, approvals, attachments, and priority flags
  - Notification Dispatcher: Sends broadcast alerts, task change updates, and critical system messages
  - Comms Log Viewer: Displays chronological feed of communications logs, filterable by user, time, priority, or type
  - Incident Communications Plan (ICS-205): Track assigned frequencies, channel names, mode, usage, and assignments
  - Communications Resource Availability Worksheet (ICS-217):  Saves a prebuilt list of radio channels for use in creating the ICS-205
4. Key Data Modules
  - - Message
  - - id, sender_id, receiver_id/group_id, content, timestamp, read[], priority, ref_num, attachments[]
  - - ICS213Message
  - - id, subject, originator, approved_by, replied_by, sent_time, message_text, reply_text, attachments[]
  - - AlertNotification
  - - id, type, content, timestamp, recipients[]
  - - RadioChannel
  - - id, alpha_tag, function, system, mode, line_a, line_c
5. UI Components
  - - Multi-user chat interface
  - - ICS 213 form generator/editor
  - - Notification panel with filtering and history
  - - Frequency/channel planner table
  - - Read receipts and threaded replies for structured messages
6. API Endpoints
```
  - - GET /api/comms/messages
  - - POST /api/comms/messages
  - - GET /api/comms/213
  - - POST /api/comms/213
  - - GET /api/comms/alerts
  - - POST /api/comms/alerts
  - - GET /api/comms/radio
  - - POST /api/comms/radio
```
7. Database Tables
```
  - - messages
  - - ics_213_messages
  - - alerts
  - - radio_channels
```
8. Inter-Module Connections
  - - Operations Module: Message routing tied to task status changes
  - - Planning Module: Critical task updates trigger alert messages
  - - Personnel Module: User presence/status and group targeting
  - - Forms Module: ICS 213 and 217 integration
9. Special Features / Notes
  - - ICS 213 messages support message chain threading and read receipts
  - - All communications are time-synced to incident clock or GPS/NTP
  - - High-priority alerts override mute or standby settings
  - - Channels can be filtered by group, location, or operational period
  - - Supports optional encryption for sensitive messages
 
## Module 6: Medical and Safety 
1. Module Name & Description
This module consolidates all health, injury, responder safety, and medical support tracking. It enables on-site triage tracking, responder health logs, safety briefings, and medical plan management. It serves both Medical Unit Leaders and Safety Officers.
2. Primary Functions
  - - Create and manage the Medical Plan (ICS 206)
  - - Track personnel injuries or exposures
  - - Log responder safety observations or concerns
  - - Manage field medical unit location and availability
  - - Log patient treatment and triage (optional submodule)
  - - Display hazard zones or restricted areas
3. Submodules / Tools
  - - CAP ORM Form Generator: Supports creation of Civil Air Patrol-specific ORM (Operational Risk Management) safety forms in compliance with CAP regulations. Auto-fills available incident, activity, and personnel data where possible
  - - Medical Plan Builder (ICS 206): Auto-populates known hospitals, contact info, med evac, and personnel data
  - - Responder Injury/Exposure Log: Tracks medical incidents tied to personnel, location, and treatment history
  - - Safety Observation Reporter: Input system for logging safety issues, with flagging system for high-risk findings
  - - Hazard Mapping Panel: Display and update unsafe zones with notes, linked to GIS overlay if available
  - - Triage Record Tracker (Optional): Tracks patients encountered by field teams, their triage category, treatment, and disposition
  - - Safety Briefing Scheduler: Tool to schedule and distribute safety messages per period/team
4. Key Data Modules
  - - MedicalIncident
  - - id, person_id, type, time, description, treatment_given, evac_required, reported_by
  - - SafetyReport
  - - id, time, location, severity, notes, flagged, reported_by
  - - TriageEntry
  - - id, patient_tag, location, triage_level, time_found, treated_by, notes, disposition
  - - HazardZone
  - - id, name, coordinates[], severity, description
5. UI Components
  - - CAP ORM form generator/editor with pre-fill from incident context
  - - ICS 206 form generator
  - - Safety log with filtering and severity flags
  - - Injury reporting form linked to personnel
  - - Patient triage input sheet
  - - GIS-linked hazard zone editor
  - - Safety message timeline view
6. API Endpoints
```
  - - GET /api/safety/caporm
  - - POST /api/safety/caporm
  - - GET /api/medical/incidents
  - - POST /api/medical/incidents
  - - GET /api/medical/triage
  - - POST /api/medical/triage
  - - GET /api/safety/reports
  - - POST /api/safety/reports
  - - GET /api/safety/zones
  - - POST /api/safety/zones
```
7. Database Tables
```
  - - cap_orm_forms
  - - medical_incidents
  - - safety_reports
  - - triage_entries
  - - hazard_zones
```
8. Inter-Module Connections
  - - Forms Module: ICS 206 and CAPF 160 form generation
  - - Personnel Module: Injury logs tied to individual responders
  - - Operations Module: Hazard zones and incidents affect task status or safety flags; allows injection of safety notes into task briefings
  - - Planning Module: Safety messages integrated into IAP
9. Special Features / Notes
  - - CAP ORM generator allows units operating under Civil Air Patrol protocols to generate and archive official safety forms
  - - All injury and exposure events generate audit trail entries
  - - Safety issues marked “flagged” appear in real-time alerts
  - - Triage entries can optionally use barcode/NFC wristbands for field input
  - - Medical plan pulls preloaded hospital and resource info
  - - Works offline and syncs when connectivity is restored

## Module 6-1: Civil Air Patrol Operational Risk Management
1. Module Name & Description
Creates, manages, and archives CAPF 160 (Deliberate), CAPF 160S (Real-Time), and CAPF 160HL (Hazard Listing) risk assessments, aligned to CAPR 160-1 guidance and the CAP risk matrix. Supports deliberate planning, quick real-time assessments, and supplemental hazard pages, and integrates with incident data, audit logs, and PDF export. The overall Safety/Medical module already calls for a “CAP ORM Form Generator”; this submodule implements it.
Reference forms: CAPF 160S real-time worksheet (with approval section and risk matrix) and CAPF 160HL hazard listing supplement
2. Primary Functions
 - Form Creation & Editing — Create CAPF 160, 160S, and 160HL with incident/personal data prefill.
 - Risk Matrix Engine — Select severity/likelihood to compute risk level (L/M/H/EH) using the CAP matrix from CAPF 160S.
 - Hazard Management — Add multiple hazards to a form; attach 160HL pages as needed (supplement to 160/160S).
 - Approval Workflow (Policy-Locked) — Manage approvals with hard business rules (see §4). CAPF 160S shows an approval block and notes CAP/CC involvement for H/EH; our policy is stricter and blocks approval entirely until mitigated.
 - Archiving & Reporting — Version history, audit trail, PDF export in CAP layout.
3. Submodules / Tools
 - Form Wizard (New 160/160S/160HL)
 - Risk Matrix Panel (Interactive grid; live highest-residual chip)
 - Hazard Library (resusable hazard templates)
 - Approval Dashboard (queue, statuses, blockers)
4. Buisiness Rules (Safety Policy)
 - ORM-001 (Hard Stop): If the highest residual risk on a form (across all hazards) is H or EH, approval is blocked. No override, no admin bypass. Users must   add controls to reduce residual risk to M or L before approval becomes available.
    Rationale: CAPF 160S requires CAP/CC approval for H/EH; we encode stricter practice that such risks are returned for further mitigation rather than approved.
 - ORM-002: Highest Residual Risk is computed from all hazard rows’ residual risk (post-control).
 - ORM-003: Any edit to controls triggers recompute and re-evaluation of approval eligibility.
5. UI Components
 - Header Strip: Activity/incident context; status badge; Highest Residual Risk chip (L/M/H/EH).
 - Hazards Grid: Mirrors CAPF 160/160HL columns: Sub-Activity/Task/Source; Hazard/Outcome; Initial Risk; Control; How to Implement; Who; Residual Risk.
 - Risk Matrix Modal: Pick Likelihood × Severity; shows computed risk letter (L/M/H/EH) per CAP grid.
 - Approval Panel: Shows approval fields (name/rank/position/signature). If Highest Residual Risk is H/EH, the Approve button is disabled with banner:
      “Approval blocked: residual risk is High/Extremely High. Add/adjust controls until residual risk is Medium or Low.”
 - Export Button: Generates CAP-layout PDF (watermarks “NOT APPROVED — PENDING MITIGATION” while blocked).
6. Data Models (incident DB unless noted)
 - orm_forms
      id (PK), incident_id (FK), form_type (‘160’ | ‘160S’ | ‘160HL’), activity, prepared_by_id, prepared_by_text, date_iso, highest_residual_risk (‘L’|‘M’|‘H’|‘EH’),
      status (‘draft’|‘pending_mitigation’|‘pending_approval’|‘approved’|‘disapproved’),
      approval_blocked (BOOL), approval_block_reason (TEXT NULL), approved_by_id (NULL), approved_ts (NULL)
 - orm_hazards
      id (PK), form_id (FK), sub_activity, hazard_outcome, initial_risk (‘L’|‘M’|‘H’|‘EH’), control_text, implement_how, implement_who, residual_risk (‘L’|‘M’|‘H’|‘EH’)
 - hazard_templates (master.db)
      id, title, description, default_controls
7. API Endpoints
 - GET /modules/safety/orm/api — List/search ORM forms (filters: type, status, highest_residual_risk).
 - POST /modules/safety/orm/api — Create new (type=160|160S|160HL).
 - GET /modules/safety/orm/api{id} — Get form with hazards, computed highest residual.
 - PUT /modules/safety/orm/api{id} — Update header fields.
 - POST /modules/safety/orm/api{id}/hazards — Add hazard row.
 - PUT /modules/safety/orm/api{id}/hazards/{hid} — Edit hazard row (recompute on save).
 - DELETE /modules/safety/orm/api{id}/hazards/{hid} — Remove hazard row (recompute).
 - POST /modules/safety/orm/api{id}/approve — Attempts approval. Returns 422 when blocked by ORM-001 with body:
    {
      "error": "approval_blocked",
      "reason": "highest_residual_risk_h_or_eh",
      "highest_residual_risk": "H",
      "message": "Approval is blocked until highest residual risk is Medium or Low."
    }
 - POST /api/safety/orm/{id}/disapprove — Mark disapproved with note.
 - GET /api/safety/orm/{id}/export — PDF export (watermark if blocked).
 - GET /api/safety/hazard_templates & POST /api/safety/hazard_templates — Manage reusable hazards (master.db).
8. Workflow
 - Create 160/160S → fill header (activity; prepared by).
 - Enter Hazards → for each: set Initial Risk (matrix), define Controls, set Residual Risk (matrix).
 - Compute Highest Residual Risk → live chip updates.
 - If H/EH → status auto-sets pending_mitigation, approval disabled.
 - Mitigate until highest residual = M/L.
 - Approval unlocked → record approver metadata/signature (as applicable on 160S form).
 - Export & Archive → PDF + version/audit trail.
9. Inter-Module Connections
 - Module 11 (Forms & Docs): Store/export CAPF 160/160S/160HL alongside ICS forms.
 - Personnel: Prefill “Prepared By” / approver fields.
 - Planning: Flagged hazards may inform IAP safety messages.
 - Operations: Publish critical hazards to task briefings/status boards.
 - Audit Trail: Every change logged with user/time.
10. Permissions & Audit
 - Roles: Safety staff can create/edit; designated approvers can approve (when eligible).
 - Audit entries on: hazard edits, risk recompute, approval attempts (including blocked), exports.
11. Reports & Exports
 - ORM Summary Report (by incident/OP): counts by risk band; list of blocked forms and reasons.
 - PDF Fidelity: Matches official CAP layouts (160/160S/160HL), including the risk matrix and approval sections from 160S.
12. Edge Cases
 - No hazards entered: approval disabled until ≥1 hazard row exists.
 - Mixed residuals: highest value governs (EH > H > M > L).
 - 160HL pages: unlimited; each row treated as a hazard item under the parent form.
13. Future Enhancements (Nice-to-Have)
 - Hazard taxonomy & tags; cross-incident analytics on recurring hazards.
 - Inline guidance snippets from CAPR 160-1 to assist control selection (stored locally).
 - One-click “copy hazards from template.”
14. Implementation notes (service-layer behavior)
 - On any hazard create/update/delete:
 - Recalculate highest_residual_risk.
 - If result is H/EH → set status='pending_mitigation', approval_blocked=true, approval_block_reason='highest_residual_risk_h_or_eh'.
 - If M/L and form previously blocked → approval_blocked=false; if submitted for approval, allow transition to pending_approval.
 - The 160S approval block UI mirrors the approval area shown on the form itself, but disables interaction until mitigated; 160HL is treated strictly as a supplemental sheet attached to the parent form.
## Module 7: Intel
1. Module Name & Description
Intel Module — Core hub for clue management and collection, analysis, and dissemination of intelligence to staff and teams. It captures subject intel, normalizes form aligned data, links clues to tasks/subjects/locations, and exports official SAR & CAP forms.
2. Primary Functions
### Clue Management – Create, categorize, geotag, score, and link clues; maintain lifecycle & audit.
### Subject Intel – Tabbed subject profiles (identity, LKP/PLS & plans, clothing, experience, health, behaviors, contacts, events timeline).
### Environmental Intel – Weather snapshots, hazards, terrain, area notes.
### Form Center – Store all fields needed to export: SAR 134, SAR 135, SAR 301, SAR 307, SAR 306, SAR 305, SAR 132, CAPF 105, CAPF 106; inject mission header at export.
### Intel Dissemination – Build sharable intel reports/briefs; push summaries to Operations/Planning, status boards, and comms.
3. Submodules / Tools
  - Intel Dashboard – Overview of open clues, critical subjects, recent interviews, debrief flags.
  - Clue Manager – Table + detail pane; linking to tasks, subjects, locations; attachments.
  - Subject Editor (Tabbed) – Unified window for missing-person records and supplemental questionnaires.
  - Environmental Panel – Weather/hazard snapshots tied to OP period.
  - Form Center – Data entry/editors for each supported form; PDF export.
  - Intel Reports – Composer to assemble printable/shareable intel packets.
4. Key Data Modules
Mission DB tables (see §7 for schemas):
  - Core: intel_clues, intel_reports, intel_env_data.
  - Subject set: intel_subjects, intel_subject_events, intel_subject_plans, intel_subject_clothing, intel_subject_experience, intel_subject_health, intel_subject_behaviors, intel_subject_contacts.
  - Form aligned: intel_form_sar134, intel_form_sar134_entry, intel_form_sar135, intel_form_sar135_segment_prob, intel_form_sar301, intel_form_sar307, intel_form_sar306, intel_form_sar305, intel_form_sar132, intel_form_sar132_entry, intel_form_capf105, intel_form_capf106, intel_form_capf106_entry.
Shared export header (injected at print time from mission context): incident_name, incident_number, operational_period, prepared_by, prepared_by_id, date, time, page, page_total.
5. UI Components
5.1 QML Windows (files under modules/intel/qml/)
  - IntelDashboard.qml
  - ClueListPanel.qml, ClueDetailDialog.qml
  - SubjectEditorWindow.qml (tabbed)
  - EnvIntelPanel.qml
  - Form editors: FormSAR134.qml, FormSAR135.qml, FormSAR301.qml, FormSAR307.qml, FormSAR306.qml, FormSAR305.qml, FormSAR132.qml, FormCAPF105.qml, FormCAPF106.qml
  - IntelReportComposer.qml
5.2 ASCII Wireframes
Intel Dashboard
+--------------------------------------------------------------+
| Intel Dashboard      [Mission X | OP 3 | Role: Intel]        |
+--------------------+----------------------+------------------+
| Open Clues (list)  | Critical Subjects    | Recent Interviews|
| #  Time  Type  Loc | [⚠ Doe, J | LPB:W]  | 2025-08-24 19:10 |
| 14  18:42 Track ...| [   Smith, A | ASD] | RP: Neighbor ... |
| ...                | ...                  | ...              |
+--------------------+----------------------+------------------+
| Env Snapshot: Weather, Hazards | Quick Actions: [New Clue]   |
+--------------------------------------------------------------+
Clue Detail Dialog
+--------------------- Clue #014 -------------------------------+
| Type: Footprint  Score: Likely  Linked: [Task-32] [Subject-1] |
| Time: 18:42  Team: G-3   Entered By: P123                     |
| Location: UTM 17T 345000 4655000  [Show on Map]               |
| Description: ...                                              |
| Attachments: [photo.jpg] [audio.m4a]                           |
| [Save] [Link...] [Export SAR 135] [Close]                     |
+---------------------------------------------------------------+
Subject Editor (Tabbed)
+-------------------- Subject: DOE, JANE (LPB: Wilderness) -------------------+
| DOB  Sex  Race  Ht/Wt  Eyes/Hair  Nickname  Photo [Upload]                 |
+----------------------------------------------------------------------------+
| [Plans/LKP] [Clothing] [Experience] [Health] [Behaviors] [Contacts] [Events]|
| Plans/LKP:                                                                  |
|  LKP Time: ____  Place: __________ [Pick Map]  Intended Route: ________     |
|  PLS: _________  Dest: _________  Expected Return: ________                 |
+----------------------------------------------------------------------------+
| [Save] [Create Report] [Open Forms]                                         |
+----------------------------------------------------------------------------+
CAPF 106 – Interview Entry
+------------------ CAPF 106 — Ground Interrogation ------------------+
| Interviewer: _____ Unit: ____  Date: ____  Time: ____               |
| Entries:                                                    [Add+] |
| ------------------------------------------------------------------ |
| Name       | Contact      | Address          | Location | Confidence|
| John Smith | 555-0101     | 12 Pine Rd       | Trailhead|  High     |
| Statement: "Saw a woman fitting desc at 18:30 heading N."          |
| Follow-up Required: [x]  Notes: ________  Links: [Clue][Task][Subj] |
| ------------------------------------------------------------------ |
| [Save] [Export PDF] [Close]                                         |
+---------------------------------------------------------------------+
SAR 134 – Clue Log
+------------------------- SAR 134 — Clue Log -------------------------+
| # | Time  | Resource | Location/UTM         | Disposition | Link     |
| 1 | 18:42 | G-3      | 17T 345000 4655000   | Held        | [Clue#14]|
+---------------------------------------------------------------------+
6. API Endpoints
```
All endpoints use the active mission DB connection and write audit logs.
6.1 Clues
  - GET /api/intel/clues — list/filter clues
  - POST /api/intel/clues — create
  - GET /api/intel/clues/{id} — retrieve (with links, attachments)
  - PUT /api/intel/clues/{id} — update
  - POST /api/intel/clues/{id}/link — link to subject/task/form
  - POST /api/intel/clues/{id}/export/sar135 — generate SAR 135 PDF
6.2 Subjects
  - GET /api/intel/subjects
  - POST /api/intel/subjects
  - GET /api/intel/subjects/{id} (expand tabs)
  - PUT /api/intel/subjects/{id}
  - POST /api/intel/subjects/{id}/event — append to timeline
6.3 Environmental
  - GET /api/intel/env
  - POST /api/intel/env
6.4 Forms
  - GET /api/intel/forms/{type} — list instances (type ∈ sar134|sar135|sar301|sar307|sar306|sar305|sar132|capf105|capf106)
  - POST /api/intel/forms/{type} — create instance
  - GET /api/intel/forms/{type}/{id} — retrieve
  - PUT /api/intel/forms/{type}/{id} — update
  - POST /api/intel/forms/{type}/{id}/export — render PDF with injected header
6.5 Reports
  - GET /api/intel/reports | POST /api/intel/reports | PUT /api/intel/reports/{id} | POST /api/intel/reports/{id}/export
```
7. Database Tables
```
Below are the key fields; actual DDL created via Alembic migrations.
7.1 Core
  - intel_clues: id, mission_id, type, score, at_time, geom(WKT), location_text, entered_by, team_text, description, attachments_json, linked_subject_id?, linked_task_id?, created_at, updated_at.
  - intel_reports: id, mission_id, title, body_md, audience, linked_subject_id?, linked_task_id?, created_at.
  - intel_env_data: id, mission_id, op_period, weather_json, hazards_json, terrain_json, notes.
7.2 Subject Set (tabbed editor support)
  - intel_subjects: identity & LPB fields (name parts, sex, dob, race, height_cm, weight_kg, eyes, hair, build, lpb_category_code, lpb_notes, photo_url).
  - intel_subject_events: subject_id, at_time, type, location_text, geom, entered_by, notes.
  - intel_subject_plans: subject_id, lkp_time, lkp_place_text, lkp_geom, pls_text, pls_geom, intended_route, destination, expected_return, transport_json, vehicle_json.
  - intel_subject_clothing: subject_id, snapshot_time, headwear, outerwear, midlayer, base_layer, hands, legs, feet, colors_json, notes.
  - intel_subject_experience: subject_id, navigation, overnight, terrain, medical_training, notes.
  - intel_subject_health: subject_id, conditions_json, meds_text, impairments_json, physician_contact.
  - intel_subject_behaviors: subject_id, habits_json, triggers_json, favorite_locations_text, critical_attractions_text, risk_notes.
  - intel_subject_contacts: subject_id, name, relationship, phone, notes, notify_on_found.
7.3 Form Aligned Storage
SAR 134
  - intel_form_sar134 (parent), intel_form_sar134_entry (rows: clue_number, time_local, resource_text, location_text, utm_text, clue_disposition_text, linked_clue_id?).
SAR 135
  - intel_form_sar135: fields for clue details, urgency, probabilities; child intel_form_sar135_segment_prob (tier, segment_code).
SAR 301
  - intel_form_sar301: RP interview & subject questionnaire fields (see JSON groups in §4).
SAR 307
  - intel_form_sar307: wanderer sheet (identity/desc, accessories, clothing, health, dementia Qs, habits, past incidents, links).
SAR 306
  - intel_form_sar306: Blessed Dementia Scale (parts I–II) + derived totals/bands.
SAR 305
  - intel_form_sar305: autism spectrum questionnaire sections.
SAR 132
  - intel_form_sar132 (parent), intel_form_sar132_entry (rows per address).
CAPF 105
  - intel_form_capf105: radio message (standard or coded groups variant) with attachments and cross links.
CAPF 106
  - intel_form_capf106 (parent), intel_form_capf106_entry (rowed interview statements; links to clue/subject/task).
```
8. Inter-Module Connections
  - Operations: Link clues/subjects to tasks; push summaries to task briefings and 214 logs.
  - Planning: Feed intel into SITREPs and strategic tasks; debrief flags for review.
  - Communications: Export CAPF 105; send alerts for high confidence leads; radio channel lookups for interviews if needed.
  - Forms & Documentation: Export all supported forms with mission header injected.
  - Status Boards: Publish high level intel cards (critical clue, last sighting, interview count).
  - Mapping/GIS: All features with geom renderable on map layers.
9. Special Features / Notes
  - Role based UI & audit trail on every write.
  - Offline first; sync when LAN/WebSocket available.
  - Mission scoped storage for forms; master lookups for personnel/vehicles.
  - Derived fields (e.g., 306 score bands) recalculated on save.
  - PDF exports maintain agency layout; header auto injected from mission context.
  - No evidence chain of custody in this module (clue handling only, per project scope).
  - Shared sample data at data/sample_data.py for UI prototypes.

 
## Module 8: Liaison
1. Module Name & Description
The Liaison Module manages relationships with assisting and cooperating agencies, external stakeholders, and mutual aid partners. It documents contacts, tracks agency-specific requests, and logs correspondence throughout the incident.
2. Primary Functions
  - - Maintain contact list of supporting agencies and representatives
  - - Log meetings, correspondence, and agreements
  - - Track special considerations or operational caveats from partner agencies
  - - Serve as intake for external resource offers, strategic goals, or external priorities
3. Submodules / Tools
  - - Agency Directory: List of agencies, points of contact, and response roles with tags for coordination type
  - - Interaction Log: Timestamped log of calls, emails, meetings, and briefings with agency reps
  - - Request Tracker: Focused on capturing strategic goals and external priorities from outside organizations; requests are routed to appropriate modules for evaluation and tasking
4. Key Data Modules
  - - Agency
  - - id, name, type, jurisdiction, contact_info[], notes
  - - Interaction
  - - id, agency_id, time, type, summary, logged_by
  - - AgencyRequest
  - - id, agency_id, type, details, status, assigned_to, resolution_notes
5. UI Components
  - - Agency contact browser with filtering
  - - Interaction log entry form and timeline viewer
  - - Request and offer queue dashboard
6. API Endpoints
```
  - - GET /api/liaison/agencies
  - - POST /api/liaison/agencies
  - - GET /api/liaison/interactions
  - - POST /api/liaison/interactions
  - - GET /api/liaison/requests
  - - POST /api/liaison/requests
```
7. Database Tables
```
  - - agencies
  - - agency_interactions
  - - agency_requests
```
8. Inter-Module Connections
  - - Planning Module: Linked through strategic task intake and agency goals
  - - Operations Module: Offers and coordination affect tasking and resource movement
  - - Personnel Module: Contact info tied to credentialed liaison staff or agency reps
9. Special Features / Notes
  - - External agency offers can auto-generate planning tasks for evaluation
  - - All logs are time-synced and audit-tracked
  - - Designed to be usable in both real-world incidents and tabletop exercises
 
## Module 9: Personnel and Role Management
1. Module Name & Description
This module centralizes personnel tracking, assignment management, credential verification, and ICS role allocation. It maintains personnel records, manages organizational hierarchy, and provides dynamic assignment tools to support field and command operations.
2. Primary Functions
  - - Sync ICS role assignments with system access perincidents
  - - Support hot-swap of assignments while preserving audit trail
  - - Enable alerting when critical roles are unfilled or undermanned
  - - Maintain personnel database with contact, credential, and status info
  - - Assign personnel to ICS roles or custom positions
  - - Display org charts with drag-and-drop role assignment
  - - Track current duty status (on/off shift, deployed, available, unavailable)
  - - Store training records and certifications
  - - Allow bulk import of personnel and unit structure from CSV
3. Submodules / Tools
  - - Hot-Swap Assignment Tool: Quickly reassign personnel while maintaining continuity and tracking changes
  - - Role Alert Monitor: Flags when vital ICS roles are unstaffed or fall below minimum requirements
  - - Personnel Roster: Searchable, filterable list of all personnel with status, rank, and assignment
  - - Status Dashboard: At-a-glance view of all personnel availability and current assignment
  - - Assignment Pool Filter: Tool to filter by qualification, availability, and org level for staffing tasks (shared with Planning module)
  - - Import/Export Manager: Supports structured import and export of unit-level rosters
4. Key Data Modules
  - - Person
  - - id, name, callsign, rank, contact_info, org_unit_id, photo_url
  - - Assignment
  - - id, person_id, role, start_time, end_time, location, status
  - - Credential
  - - id, person_id, name, category, issue_date, expiration, is_trainer, is_evaluator
  - - OrgUnit
  - - id, name, parent_unit_id, type, region
5. UI Components
  - - Personnel profile editor
  - - Interactive org chart with editable roles
  - - Shift/duty tracker panel
  - - CSV importer with mapping and preview
6. API Endpoints
```
  - - GET /api/personnel
  - - POST /api/personnel
  - - GET /api/assignments
  - - POST /api/assignments
  - - GET /api/orgunits
  - - POST /api/orgunits
```
7. Database Tables
```
  - personnel
  - Certificationtype
  - Personnelcertification
  - assignments
  - org_units
```
8. Inter-Module Connections
  - - Operations Module: Assignment data drives tasking and field tracking
  - - Medical Module: Injury/exposure reports are tied to personnel
  - - Communications Module: Shows available contacts by role
  - - Planning Module: Personnel pool filters used in IAP and strategic tasking
9. Special Features / Notes
  - - Supports nested organizational structures with unlimited depth
  - - Configurable role templates per incident type
  - - Includes audit trail for role assignment changes
  - - Supports training incidents with optional credential masking
  - - Allows designation of units as inactive or virtual
 
## Module 9-1: Personnel Certifications
1. Module Name & Description
The Certifications Module manages all professional credentials, trainings, and certifications for personnel within the ICS Command Assistant. It tracks certification levels and progression chains, and provides reporting for compliance and readiness.
2. Primary Functions
  - Catalog Management: Define and maintain a library of certification types (e.g., ICS-100, First Aid, GTM1, GTM2) and their progression chains.
  - Assignment & Tracking: Link certifications to personnel, including certification level (0–3) and associated documentation.
  - Level Management: Support four discrete levels for each certification:
  - 0: No Rating
  - 1: Trainee
  - 2: Qualified
  - 3: Evaluator
  - Reporting & Compliance: Generate reports on personnel certification levels and chain progression for audits and incident planning.
  - When printing certifications to forms or status boards:
  - Level 0: Not shown
  - Level 1: <CODE>-T
  - Level 2: <CODE>
  - Level 3: <CODE>-SET
3. Submodules / Tools
  - Certification Library: CRUD operations for certification definitions, including parent–child chain relationships.
  - Personnel Certification: Interface to assign, view, and update a personnel’s certification level.
  - Reporting Dashboard: Pre-built filters and export options (PDF/CSV) focused on certification levels and chain progression.
4. Key Data Modules
CertificationType:
{
  id,
  code,
  name,
  description,
  category,
  issuing_organization,
  parent_certification_id (nullable)
}

personnelCertification
{
  id,
  personnel_id,
  certification_type_id,
  level (0–3),
  attachment_url
}
5. UI Components
  - Certification Library View: Table listing certification types, showing chain relationships and allowing edits.
  - Certification Detail Form: Modal to add or edit certification types and set chain links.
  - Personnel Certification Dashboard: Grid showing each person’s certification levels with clear indicators:
  - Blank: No Rating
  - T: Trainee
  - Q: Qualified
  - E: Evaluator
  - Certification Assignment Panel: Form within a personnel profile to set or update a certification level.
  - Form & Status Board Rendering: When certifications are displayed outside the dashboard (e.g. printed forms, status boards):
  - Level 0: Not shown
  - Level 1: <CODE>-T
  - Level 2: <CODE>
  - Level 3: <CODE>-SET
6. API Endpoints
```
GET /api/certifications
POST /api/certifications
PUT /api/certifications/{id}
DELETE /api/certifications/{id}
GET /api/personnel/{pid}/certifications
POST /api/personnel/{pid}/certifications
DELETE /api/personnel/{pid}/certifications/{cid}
```
7. Database Tables
```
  - certification_types:
  - id (PK)
  - code
  - name
  - description
  - category
  - issuing_organization
  - parent_certification_id (FK, nullable)
  - personnel_certifications:
  - id (PK)
  - personnel_id (FK)
  - certification_type_id (FK)
  - level (INT, 0-3)
  - attachment_url
```
8. Inter-Module Connections
  - Personnel & Role Management: Display certification status next to roles and profiles to inform assignments.
  - Operations & Planning: Filter or group personnel by certification level for tasking.
  - Reference Library: Link to certification chain documentation and level definitions.
9. Special Features / Notes
  - Bulk Import/Export: CSV support for certification types (including chains) and personnel levels.
  - Role-Based Access Control: Admins manage certification definitions; supervisors can assign levels and view reports.

 
## Module 10: Reference Library
1. Module Name & Description
This module serves as a centralized repository for doctrine, guides, agency policies, mutual aid agreements, jurisdictional maps, SOPs, and other reference materials. It allows teams to quickly locate, search, and share incident-critical documents from within the system.
2. Primary Functions
  - - Upload, categorize, and tag reference documents
  - - Store internal SOPs, ICS references, job aids, and training handouts
  - - Enable full-text search and filtering by topic or agency
  - - Organize documents by custom collections or folders
  - - Provide access controls per document or collection
3. Submodules / Tools
  - - Document Uploader: Drag-and-drop or browse to upload documents with category, keywords, and perincidents
  - - Reference Browser: Interface to search, filter, preview, and download documents
  - - Collections Manager: Create and maintain sets of related documents by topic, agency, or function
  - - External Link Register: Store and access bookmarked online resources or interagency sites
4. Key Data Modules
  - - Document
  - - id, title, filename, type, uploaded_by, tags[], access_level, agency, category, created_at
  - - Collection
  - - id, name, description, document_ids[], created_by
  - - ExternalLink
  - - id, title, url, description, added_by
5. UI Components
  - - Document upload and tagging form
  - - Searchable and filterable document list
  - - Collection view with folder-style UI
  - - Quick preview modal or inline reader
6. API Endpoints
```
  - - GET /api/library/documents
  - - POST /api/library/documents
  - - GET /api/library/collections
  - - POST /api/library/collections
  - - GET /api/library/links
  - - POST /api/library/links
```
7. Database Tables
```
  - - documents
  - - collections
  - - external_links
```
8. Inter-Module Connections
  - - Forms Module: May cross-reference job aids or SOPs related to specific ICS forms
  - - Planning Module: Reference materials can be embedded in planning packets
  - - Liaison Module: External agreements and policies stored for agency access
  - - Training Mode / Sandbox: Pulls content from this library to guide simulations
9. Special Features / Notes
  - - Supports upload of PDFs, DOCX, images, and video content
  - - Full-text document indexing for fast searching
  - - Optional annotation system to allow shared highlights/notes
  - - Version control and document history supported
  - - Offline access for pre-synced document bundles
 
## Module 11: ICS Forms and Documentation
1. Module Name & Description
This module provides a centralized location to view, fill, manage, and archive ICS forms and custom documentation. It supports digital form filling, version control, cross-module data integration, and export to PDF/print formats. The system also allows uploading custom agency forms and automatically converting them into fillable digital templates.
2. Primary Functions
  - - Browse and search standardized ICS forms (U.S., Canadian, Coast Guard, and other designated formats)
  - - Upload custom forms and convert them into digital templates
  - - Auto-fill fields from related modules (e.g., personnel, planning, comms)
  - - Allow real-time collaborative editing of forms
  - - Track form history and versions with audit trail
  - - Export to PDF, print, or attach to IAP packet
  - - Group similar form types to allow users to choose preferred print/output format (e.g., communications log to ICS 309 or CAPF 110)
3. Submodules / Tools
  - - Form Type Selector: Filter forms by system (U.S. ICS, Canadian IMS, Coast Guard, etc.)
  - - ICS Form Library: Catalog of standardized forms with metadata and instructions
  - - Form Builder: Used for converting uploaded forms into fillable digital templates
  - - Form Viewer/Editor: Interface for filling out, saving, and reviewing forms
  - - Version & Audit Log Viewer: Displays edit history and change tracking
  - - Related Forms Linker: Allows cross-linking of related documents (e.g., ICS 213 linked to a task from ICS 204)
4. Key Data Modules
  - - FormTemplate
  - - id, name, type, source_file, fields[], version, created_by
  - - FormInstance
  - - id, template_id, filled_by, filled_data, status, revision_number, timestamps
  - - FormVersion
  - - id, instance_id, editor_id, timestamp, changeset, comments
  - - CustomUpload
  - - id, file_path, uploader, field_map, linked_template
5. UI Components
  - - Form browser with filtering by type or module
  - - Digital form editor with auto-fill and validation
  - - Version history side panel
  - - Upload wizard for custom form intake
  - - Cross-reference sidebar for linked forms
6. API Endpoints
```
  - - GET /api/forms/templates
  - - POST /api/forms/templates
  - - GET /api/forms/instances
  - - POST /api/forms/instances
  - - GET /api/forms/versions
  - - POST /api/forms/upload
```
7. Database Tables
```
  - - form_templates
  - - form_instances
  - - form_versions
  - - custom_uploads
```
8. Inter-Module Connections
  - - Planning Module: Pulls forms into IAP packets; receives auto-fill from strategy/task data
  - - Personnel Module: Provides names, IDs, roles for form population
  - - Operations Module: ICS 204, 215, 214 tie-in for tasking and logging
  - - Communications Module: Populates ICS 205, 210, 213
  - - Medical Module: Links to ICS 206, injury logs
  - - Liaison Module: Agency contacts and restrictions on forms like ICS 213
9. Special Features / Notes
  - - Every form field supports audit logging, auto-fill override, and manual locking
  - - Digitized templates retain formatting fidelity for print and export
  - - Form builder uses drag-and-drop interface for field mapping
  - - Supports offline form filling with sync upon reconnect
  - - All forms tied to incident context for sorting and archiving
 
## Module 12: Finance/Admin
1. Module Name & Description
This optional module supports incident-related financial tracking, administrative documentation, cost recovery, resource timekeeping, and expense forecasting. It can be enabled or disabled per incident and is structured to align with ICS finance unit responsibilities, with optional CAP or agency-specific workflows.
2. Primary Functions
  - - Record expenses and assign them to categories and funding sources
  - - Track time for personnel, equipment, and resources
  - - Generate cost summaries for operations, logistics, etc.
  - - Attach receipts, approvals, and justification documents
  - - Export financial summaries and logs to PDF or Excel
  - - Manage reimbursements, invoices, or funding requests
3. Submodules / Tools
  - - Time Tracking Register: Logs person/equipment hours
  - - Expense Entry Tool: Input field expenditures, equipment rentals, fuel, meals, etc.
  - - Funding Source Manager: Assign costs to budgets, grants, or reimbursement tracks
  - - Cost Summary Dashboard: Visual reporting of total and projected costs
  - - Document Attachments Panel: Upload receipts or authorizations
  - - ICS Form Generator: Supports ICS 214 (activity log), 213RR, 219, 211, and CAPF financial forms
4. Key Data Modules
  - - Expense
  - - id, description, category, amount, date, resource_id, approver, funding_source_id
  - - TimeEntry
  - - id, person_id, hours, task_id, date, role, notes
  - - FundingSource
  - - id, name, code, type, balance, agency
5. UI Components
  - - Financial entry forms with auto-categorization
  - - Tables for time logs and expense history
  - - Cost summary report cards with export options
  - - Form print panel (ICS/CAP/Agency-specific)
6. API Endpoints
```
  - - GET /api/finance/expenses
  - - POST /api/finance/expenses
  - - GET /api/finance/time
  - - POST /api/finance/time
  - - GET /api/finance/funding
  - - POST /api/finance/funding
```
7. Database Tables
```
  - - expenses
  - - time_entries
  - - funding_sources
```
8. Inter-Module Connections
  - - Personnel Module: Ties to pay/time records
  - - Logistics Module: Tracks supply/resource spending
  - - Operations Module: Relates costs to specific tasks/incidents
  - - Forms Module: Supports auto-filling of cost and time forms
  - - Command Module: Optional view-only dashboard for leadership
9. Special Features / Notes
  - - Supports custom cost categories per agency
  - - CAP-specific forms supported where applicable (CAPF series)
  - - Digital signature for cost approval routing
  - - Role-based finance access
  - - Printable financial reports and audit logs
 
## Module 13: Status Boards
1. Module Name & Description
This module provides dynamic, incident-specific status boards for real-time situational awareness across all ICS sections. Status boards are configurable and tailored to specific needs such as task status, personnel availability, communications readiness, logistics supply levels, and more. This module does not generate or store new data. Instead, it presents information produced and maintained by other modules in a visual format.
2. Primary Functions
  - - Choose from predefined status board templates for common use cases (e.g., Air Ops, Task Tracking, Staging, Logistics)
  - - Create and manage multiple custom status boards
  - - Display real-time updates from other modules (tasks, teams, resources, forms)
  - - Support manual and automated entry updates
  - - Enable filtered views by section, unit, or incident type
  - - Visual indicators for priority, readiness, and changes
3. Submodules / Tools
  - - Board Manager: Create, edit, archive, or clone boards
  - - Entry Panel: Add/update status entries with color, icons, and comments
  - - Board Display Grid: Interactive, tile-based real-time board UI
  - - Board Templates: Save reusable board layouts (e.g., Air Ops, SAR Tasking, Logistics Inventory)
  - - Filter/Sort Tool: Show by section, date, priority, or custom tag
4. Key Data Modules
  - - StatusBoard
  - - id, name, type, section, created_by, visibility_scope, template_id
  - - BoardEntry
  - - id, board_id, title, description, icon, color, last_updated_by, timestamp, linked_item (task_id, team_id, etc.)
5. UI Components
  - - Dashboard view for multiple boards
  - - Board entry cards with drag-and-drop reordering
  - - Quick filters for time, section, keyword
  - - Board creation and layout editor
6. API Endpoints
```
  - - GET /api/status_boards
  - - POST /api/status_boards
  - - GET /api/status_entries
  - - POST /api/status_entries
  - - PUT /api/status_entries/{id}
```
7. Database Tables
```
  - - status_boards
  - - status_entries
```
8. Inter-Module Connections
  - - Operations Module: Link entries to tasking and 214 logs
  - - Personnel Module: Show status of individuals or teams
  - - Logistics Module: Track inventory and requests
  - - Communications Module: Show radio status, frequency availability, etc.
  - - Command Module: Present board views to leadership as dashboards
9. Special Features / Notes
  - - Status change notifications: Send alerts (in-app, email, or SMS) for critical updates or flagged board entries
  - - Template-specific color and icon sets: Maintain consistent visual language across boards (e.g., Air Ops, Logistics, Comms)
  - - Offline board mode: Boards can be cached for disconnected operation and synced when reconnected
  - - Board templates for standardized incidents (e.g., Search & Rescue, Public Event)
  - - Reusable across incidents
  - - Display on dedicated monitors or screens for command posts
  - - Export snapshots or history logs to PDF or image
  - - Optional refresh rates or live sync settings for LAN deployments
 
## Module 14: Public Information
1. Module Name & Description
This module enables authorized personnel (e.g., PIOs) to create, manage, and publish information for internal staff, partner agencies, and the public. It supports message review workflows, media coordination, and internal press log tracking.
2. Primary Functions
  - - Draft and review press releases, situation updates, and advisories
  - - Manage a log of all outgoing public communications
  - - Enable approvals and revision tracking for all messages
  - - Provide exportable briefings and public update summaries
3. Submodules / Tools
  - - Message Composer: Draft, edit, preview messages
  - - Approval Workflow: Assign reviewers/approvers with status tracking
  - - Media Log: Record of posted or distributed content
  - - Press Summary Builder: Compile briefings for agency/public release
4. Key Data Modules
  - - Message
  - - id, title, body, type, audience, created_by, approved_by, timestamp, status
5. UI Components
  - - Message queue with status badges
  - - Inline message editor and formatting panel
  - - Revision history viewer
  - - Publish/export toolbar
6. API Endpoints
```
  - - GET /api/public_info/messages
  - - POST /api/public_info/messages
```
7. Database Tables
```
  - - public_info_messages
```
8. Inter-Module Connections
  - - Command Module: Coordinate approved updates or briefings
  - - Communications Module: Broadcasts internal PIO alerts or notifications
  - - Planning Module: Sync with ongoing situation reports or ICS 209 summaries
  - - Forms Module: Support ICS 213 and ICS 209 formatting where applicable
9. Special Features / Notes
  - - Message tagging by audience: Public, Agency, Internal
  - - Role-based publishing controls (e.g., only lead PIOs can finalize)
  - - Public briefing export to PDF, print, or email
  - - Offline message drafting support with queued sync
 
## Module 15: Mobile App Integration
1. Module Name & Description
This module enables seamless interaction between the desktop ICS Command Assistant and a separately designed mobile application. This module serves as the bridge for real-time data syncing and workflow continuity between the two systems. It provides real-time data syncing, tailored mobile interfaces, and role-based mobile access for field personnel.
2. Primary Functions
  - - Sync incident data between Windows and mobile apps
  - - Support offline mobile use with automatic re-sync on reconnect
  - - Display mobile-tailored views of tasks, assignments, and messages
  - - Allow mobile personnel to submit ICS 214 entries and task updates
  - - Enable mobile alerts, tasking, and status notifications
3. Submodules / Tools
  - - Sync Engine: Ensures secure bidirectional data exchange
  - - Mobile UI Configurator: Define what data is accessible to different user roles in the mobile app
  - - Mobile Perincidents Panel: Grant/limit access based on assignment or role
  - - Mobile Activity Feed: Show incoming tasks, messages, or alerts
4. Key Data Modules
  - - MobileSession
  - - id, user_id, device_id, session_token, last_sync_time
  - - MobileAccessRule
  - - id, role_id, module_access, view_config
5. UI Components (Windows-Side)
  - - Sync settings page (schedule, conflict resolution)
  - - Device management panel
  - - Role-based visibility matrix
6. API Endpoints
```
  - - GET /api/mobile/sync
  - - POST /api/mobile/push
  - - POST /api/mobile/pull
  - - GET /api/mobile/perincidents
```
7. Database Tables
```
  - - mobile_sessions
  - - mobile_access_rules
```
8. Inter-Module Connections
  - - Operations Module: Pulls tasking data and logs 214 entries
  - - Personnel Module: Grants mobile access per person/role
  - - Communications Module: Pushes alerts, receives mobile messages
  - - Forms Module: Enables 214 creation from mobile
9. Special Features / Notes
  - - Field entries marked as mobile-sourced in audit logs
  - - Optional incident QR code or link-based mobile app onboarding
  - - Configurable field perincidents and lockdowns
  - - Offline-first design for austere environments
 
## Module 16: Training/Sandbox Mode
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes

 

## Module 17: Search and Rescue Toolkit
1. Module Name & Description
A specialized suite of planning tools designed to support Search and Rescue (SAR) operations. This module provides structured utilities and calculations to assist planning personnel in defining search areas, understanding behavioral profiles, and coordinating data relevant to locating missing persons.
2. Primary Functions
  - Provide additional SAR specific tools and modules to assist in planning search and rescue tasks
  - Provide preconfigured task fields like LKP, PLS, and POD
  - Simplify UI and data flows for SAR planning incidents
3. Submodules / Tools
### Missing Person Toolkit
### Lost Person Behavior Calculator
### POD Calculator
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes

 
## Module 18: Disaster Response Toolkit
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes

 
## Module 19: Planned Event Toolkit
1. Module Name & Description	
  Planned Events Toolkit: A suite of standalone modules, activated only for planned incidents (e.g., festivals, parades, marathons). Provides event-specific planning, public safety, and streamlined tasking—independent of core ICS features.
2. Primary Functions
  - Loads dynamically when incident type is planned
  - Unloads automatically upon planned event demobilization
3. Submodules / Tools
### Event Promotion and Communication
a.	Purpose: Engage attendees and stakeholders with timely, targeted messaging.
b.	Key Features:
i.	Multi channel campaign builder (email, SMS, push, social).
ii.	Scheduled & trigger based sends (e.g., event countdown, weather alerts).
iii.	Geo fenced notifications for location specific updates.
iv.	Subscriber management: opt in/out, segmentation by role or interest.
v.	Analytics: delivery rates, open/click metrics.
c.	UI Components:
i.	Campaign Dashboard (list, status, next send time, basic stats).
ii.	Message Composer (WYSIWYG with template gallery).
iii.	Geo Map Selector (draw and save zones for targeting).
iv.	Subscriber List (filter by tags, engagement).
### Vendor & Permitting Coordination
a.	Purpose: Onboard vendors and manage permit compliance efficiently.
b.	Key Features:
i.	 Vendor Registry: profiles, document uploads (insurance, licenses).
ii.	Status workflow: Pending → Approved → Active → Suspended → Revoked.
iii.	Map based booth assignment.
iv.	Permit issuance via customizable templates.
v.	Bulk import/export and compliance reporting.
c.	UI Components:
i.	Vendor Table (searchable, sortable, status badges).
ii.	Profile Detail Form (Contact / Documents / Location / History tabs).
iii.	Permit Dashboard (tiles for Active, Expiring Soon, Expired).
iv.	Bulk Import Wizard (CSV upload, validation, field mapping).
### Public Safety & Incident Management
a.	Purpose: Enable on-site teams to monitor safety, report incidents, and dispatch responders.
b.	Key Features:
i.	Security Patrol Manager: zone definitions, real time coverage map.
ii.	Mobile Incident Logger: report events with photos/videos.
iii.	Automated Dispatch: route reports, track acknowledgments.
iv.	Incident categorization (medical, security, lost child, etc.).
v.	Escalation and on call rotation rules.
c.	UI Components:
i.	Patrol Map (live locations, zone overlays).
ii.	Incident Feed (filter by type, status).
iii.	Dispatch Board (Unassigned / En Route /Arrival / Complete).
iv.	Report Form (quick entry, media attach).
### Mini-Tasking Module
a.	 Purpose: Provide a lightweight tasking interface for minor event duties
b.	Key Features:
i.	 Quick Task Creator: title, assignee, due time, status.
ii.	Nested checklists for multi-step tasks.
iii.	Recurring templates (e.g., hourly safety checks).
iv.	Reminders & notifications for due/overdue tasks.
v.	Filtering by assignee, status, priority.
c.	UI Components:
i.	Quick Task Sidebar (create/view tasks, progress bars).
ii.	Checklist Popup (view/edit sub items).
iii.	Task Calendar (due dates, recurring schedules).
iv.	Notification Center (task alerts).
### Public Health & Sanitation Oversight
a.	Purpose: Maintain hygiene and health standards throughout the event.
b.	Key Features:
i.	 Health Inspection Forms: vendor booths, facilities.
ii.	Sanitation Issue Tracker (waste overflow, supply shortages).
iii.	Crew Assignment & follow up verification.
iv.	Instant alerts for critical violations.
c.	UI Components:
i.	Inspection Form (customizable checklist, photo capture).
ii.	Issue Dashboard (map + table of sanitation reports).
iii.	Crew Scheduler (drag and drop assignments).
iv.	Follow Up Tracker (resolution status, timestamps).
4. Key Data Modules
  - PromotionCampaign: id, name, channels[], schedule, content
  - Vendor: id, name, type, contactInfo, status, permitIds[]
  - Permit: id, vendorId, type, issueDate, expiryDate
  - SecurityPatrol: id, zoneId, personnelIds[], startTime, endTime
  - IncidentReport: id, type, description, location, timestamp, reporterId
  - DispatchRequest: id, incidentReportId, responderIds[], status
  - QuickTask: id, title, assignedTo, dueTime, status
  - TaskChecklistItem: id, taskId, description, completed
  - Reminder: id, taskId, remindAt, sent
  - InspectionRecord: id, inspectionType, targetId, findings, date
5. UI Components
  - Toolkit Launcher (side panel menu for all planned modules)
  - Dashboard Widgets (campaign summary, vendor status, task overview, incident feed)
  - Notification Center (alerts across modules)
6. API Endpoints
```
  - Promotions: GET /planned/promotions/campaigns, POST /planned/promotions/campaigns, POST /planned/promotions/campaigns/:id/send, GET /planned/promotions/metrics/:id
  - Vendors & Permits: GET /planned/vendors, POST /planned/vendors, PUT /planned/vendors/:id, DELETE /planned/vendors/:id, GET /planned/permits, POST /planned/permits
  - Public Safety: GET /planned/security/patrols, POST /planned/security/patrols, GET /planned/incidents, POST /planned/incidents, POST /planned/dispatches, PUT /planned/dispatches/:id
  - Tasks: GET /planned/tasks, POST /planned/tasks, GET /planned/tasks/:id/checklist, POST /planned/tasks/:id/checklist, POST /planned/tasks/:id/reminders
  - Health & Sanitation: POST /planned/inspections/health, GET /planned/sanitation/issues, POST /planned/sanitation/issues
```
7. Database Tables
```
  - planned_promotions
  - planned_vendors
  - planned_permits
  - planned_security_patrols
  - planned_incident_reports
  - planned_dispatch_requests
  - planned_tasks
  - planned_task_checklist_items
  - planned_task_reminders
  - planned_inspection_records
```
8. Inter-Module Connections
  - Public alerts fed to Communications module
  - Vendor/permit statuses shared with Logistics & Personnel
  - Task assignments synced with Personnel & Role Management
  - Inspection data exported via Forms & Documentation (ICS 219)
9. Special Features / Notes
  - Fully independent: no overlap with core ICS modules
  - Real time updates via WebSocket for critical data
  - Role based perincidents via planned_event_roles
  - Offline support with automatic sync on reconnect

 
## Module 19-1: Event Promotions and Communications
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes
 
## Module 19-2: Vendor & Permitting Coordination
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes
 
## Module 19-3: Public Safety & Incident Management
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes
 
## Module 19-4: Mini Tasking Module
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes
 
## Module 19-5: Public Health & Sanitation Oversight
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes
 
## Module 20: Initial Response Toolkit
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes

 
## Module 21: UI Customization
1. Module Name & Description
2. Primary Functions
3. Submodules / Tools
4. Key Data Modules
5. UI Components
6. API Endpoints
```
7. Database Tables
```
```
```
8. Inter-Module Connections
9. Special Features / Notes

 
## Module XX: AI Integration (Wishlist Phase)
1. Module Name & Description
This forward-looking module explores integration of artificial intelligence to enhance decision support, situational analysis, and workload reduction throughout the ICS Command Assistant ecosystem. This phase remains conceptual until prioritized for development.
### Potential Functions
  - - Automated analysis of 214 logs to detect emerging trends, gaps, or coordination issues
  - - Task prediction and resource matching based on past data and current conditions
  - - Natural language queries across logs, forms, tasks, and messages
  - - Smart form autofill based on prior entries and contextual incident data
  - - AI-generated briefings or situation summaries
  - - Optical character recognition (OCR) and NLP for digitizing paper forms
  - - Incident risk forecasting based on operational plans, weather, and historical performance
  - - Auto-sort and prioritize task queues based on urgency and context
  - - Collaboration summarizer for chats, logs, and planning threads
  - - Smart alert filter to reduce information overload
  - - Post-incident summary generator using incident logs and task data
3. Submodules / Tools (Conceptual)
  - - AI Assistant Panel: Query interface and context-aware suggestions
  - - Form AutoComplete Engine: Fills and recommends form fields based on context
  - - Pattern Watcher: Monitors logs and tasks for trends, gaps, or repeated issues
  - - OCR Uploader: Import and convert handwritten or scanned documents
### Required Foundations
  - - Expanded metadata tagging across all modules
  - - Consistent use of audit logs and timestamps
  - - NLP libraries and OCR tools
  - - Opt-in privacy controls and usage tracking
### UI Concepts
  - - Inline smart hints while filling forms or reviewing tasks
  - - AI chat sidebar with search and recommendation abilities
  - - Visual indicators for detected anomalies or suggestions
### Dependencies
  - - Integration with incident database and form digitization systems
  - - Coordination with data governance and audit compliance
### Special Notes
  - - Not prioritized for early-phase implementation
  - - Will require regulatory review for sensitive data
  - - Designed for opt-in usage with explicit controls
  - - Intended to support, not replace, human decision-making
 