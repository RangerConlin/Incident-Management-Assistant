**************************************************************************************************************
[Command]
Incident Command Dashboard

Incident Overview 
   
Incident Organization

SITREP Window

- Command Dashboard redesign (modules/command/widgets/ic_overview_widget.py, 2026-07-21) has four
  panels still shipped as empty states because none of them have a backing data model yet. Each
  needs a real repository/schema/API route before it can show real data instead of a placeholder:
  - Pending Approvals panel — no approval/workflow data model exists (resource request approvals,
    task extension approvals, comms channel change requests, etc. aren't tracked as a queue
    anywhere). Needs a schema for an approvable "request" concept plus approve/deny actions wired
    to whatever module originated the request.
  - Section Health panel — no per-section (Operations/Planning/Logistics/Communications/Safety/
    Intel/Liaison/Finance) status tracking exists. Needs a data model for section-level status
    (e.g. good/caution/critical) plus a note field, and a way for each section lead to update it.
  - Operational Period Readiness panel — no ICS-form completion checklist (202/203/204/205/206,
    safety message, briefing packet, resource gaps review, etc.) is tracked anywhere. Needs a
    per-operational-period checklist model, likely derived from whether each ICS form/module has
    been completed for the current OP rather than a manually maintained list.
  - Recent Major Activity panel — no unified cross-module activity/audit feed exists to pull from.
    Needs either a dedicated incident-wide activity log collection that other modules write to, or
    an aggregation query across existing per-module logs.
  - The three KPI tiles for Personnel Checked In, Open Leads, and Safety Issues are placeholders
    for the same reason (no data source) and should be revisited alongside Section Health/Safety
    once those data models exist.

**************************************************************************************************************
[Planning]
Planning Dashboard

Operational Period Manager

Demobilization Planner

Meeting Planner

Individual Meeting Detail Windows

Situation Report
  - Move to under the command menu
  
Weather

**************************************************************************************************************
[Operations]
Operations Dashboard

Operations Section Organization

Team Status Board

Task Board
**************************************************************************************************************
[Team Detail Window]

**************************************************************************************************************
[Task Detail Window]
  - Communications channels need a selector for channel type (primary/alternate/etc)
  - 104/109 exports need to be tied to a specific team somehow

**************************************************************************************************************
[Logistics]
Logistics Dashboard

Check In ICS-211
    
Resource Status Board


Facilities Manager

- Dashboard redesign mockup (Design Documents artifact, 2026-07-20) replaced the old ad-hoc
    Supply & Comms Health badges (PPE/Medical/Water/Fuel/Comms Cache/Spare Radios) with the same
    panel unchanged, pending a real tracking system: today those levels aren't backed by any
    repository/collection, so before building this panel for real we need to decide how supply
    and comms-cache stock levels get recorded and updated (manual entry vs. derived from
    check-in/checkout and resource request activity) and what collection/schema should hold it.


**************************************************************************************************************
[Communications]
Communications Dashboard

Communications Plan ICS-205

Communications Log (ICS 309)

Log Entry

Quick Entry

Chat Messages

ICS-213 Messages

Notification Feed

Notification Settings
**************************************************************************************************************
[Intel]
Intel Dashboard

Subjects

Leads

Intel Items

Assessments

Intel Logs

Forms

- Weather module rebuild (modules/intel/weather/, 2026-07-22) — see modules/intel/weather/backlog.md
  for the module's own follow-ups: lightning data deferred (no reliable free API); runway crosswind
  data now comes from a live NOAA AWC airport lookup (services/runway_api.py) queried once at
  station-creation time and cached, no bundled CSV needed; NWS location-code hint caching
  (location_codes.py) isn't wired back into the new WeatherManager yet (forecast/HWO still work,
  just without the caching speedup).
**************************************************************************************************************
[Safety]
  - Integrate USCG GAR model on the task/assignment side (SPE hazard scoring is done — see Safety Risk Manager, modules/safety/orm/)
    -- New Safety tab in the task detail window?
  - Restore Safety Analysis Templates as reusable groupings of master hazard library entries for quick import into the tactics/planning workflow.
    -- Keep `hazard_types` as the single source of truth; templates only store grouped hazard selections, ordering, and any import-oriented metadata needed by planning/tactics.
Safety Message ICS 208

Incident Safety Analysis ICS 215A

CAP Operational Risk Management CAPF160

Incident Report (IWI)

**************************************************************************************************************
[Medical]
Medical Plan ICS 206

**************************************************************************************************************
[Liaison]
Redesigned around the LOFR's actual job — controlling what information flows between incident
staff and external customers — not generic agency CRUD. Dashboard (modules/liaison/liaison_window.py)
follows the Public Information module's structure (button bar + overview + linked windows), now
bold/saturated-colored via new LIAISON_AGENCY_STATUS/LIAISON_PRIORITY/LIAISON_REPORT_STATE
palettes in styles/profiles/{dark,light}.py. Three sections:
  - Agency Directory — unchanged CRUD board, re-themed.
  - Reporting Board (modules/liaison/panels/reporting_board.py, new liaison_reporting_digests
    collection) — LOFR pulls a live Objective/Task status, curates a customer-facing summary,
    gates it behind a Ready to Report toggle before it's shareable.
  - Customer Requests & Feedback (modules/liaison/panels/customer_board.py) — incoming customer
    requests can be converted directly into a real Objective or Task (origin_module/origin_id
    back-link added to both schemas), plus Resource Offers and Feedback tabs.
  - Remaining gap: Agency Detail dialog's Contacts / Restrictions / Agreements tabs are
    read-only (backend supports Contacts CRUD; Restrictions/Agreements have no create UI at
    all) — add "add" dialogs for these if the LNO workflow needs them tracked.
**************************************************************************************************************
[PIO]
PIO Dashboard

Messages/Releases

Misinformation/Rumors

Media Log

Talking Points

Letterhead/Templates

Distribution Log

**************************************************************************************************************
[Finance]
Finance/Admin Dashboard

Time Tracking

Expenses & Procurement

Cost Summary

**************************************************************************************************************
[Personnel Edit Window]


**************************************************************************************************************
[Disaster Response Toolkit]

**************************************************************************************************************
[Planned Event Toolkit]

**************************************************************************************************************
[Initial Response]

**************************************************************************************************************
[Reference Library]

**************************************************************************************************************
[Dockable Widgets]

**************************************************************************************************************
[Tech Debt / Infrastructure]
    - Optimization follow-up: profile Edit-menu windows and the task detail window to identify why modest datasets
      are not opening faster; tie this to any decision about reusing/caching Edit windows.
    - Sidebar: revisit large Edit-menu CSV import/export workflows with progress/cancel behavior and possible
      bulk API endpoints if large catalog imports prove slow or freeze the UI.
    - Incident Mongo schema cleanup: review and tighten per-incident collections before the DB
      grows further.
      - Liaison: leave liaison collections alone for now because the module still needs further
        product development.
      - Heavily in-development modules: leave the remaining collections alone for now except to
        avoid adding new duplicate collections or fields.
    - Cloud router (`cloud_server/router/`) forwards request/response and WebSocket bodies over the reverse tunnel as base64-in-JSON, capped at 10MB each direction (`SARAPP_ROUTER_MAX_BODY_BYTES`). Fine for typical form/photo sizes; revisit with a streaming transport if large file uploads/downloads through the router prove too slow. See `Design Documents/Instructions/cloud_router_architecture.md`.
    - Mobile photo upload isn't implemented yet (Report Hazard's "Attach Photo" is a placeholder button, no `image_picker` dependency). When it's built, submit one photo per request rather than batching several into one multipart body, to stay clear of the 10MB tunnel cap above.
    - During the start and login process, need to have a way to force a refresh to the server without closing and restarting

**************************************************************************************************************
[Logs]
  - Logs need to be able to write to multiple streams at once.  Would like to be able to generate a log for each individual person, but i dont think writing a separate stream is a good idea.  perhaps something that generates from a lookup of everything that person has done?
