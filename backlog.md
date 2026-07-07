**************************************************************************************************************
[Command]
Incident Command Dashboard

Incident Overview 
   
Incident Organization

SITREP Window

**************************************************************************************************************
[Planning]
Planning Dashboard

Operational Period Manager

Demobilization Planner

Meeting Planner

Individual Meeting Detail Windows

Situation Report

Tactics and Resource Planner

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

**************************************************************************************************************
[Logistics]
Logistics Dashboard

Check In ICS-211
    
Resource Status Board
    - Status based colors need to be coded in the light/dark palette and for dark mode need to be darker.
Resource Requests (ICS-214RR)

Facilities Manager


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
**************************************************************************************************************
[Safety]
Safety Message ICS 208

Incident Safety Analysis ICS 215A

CAP Operational Risk Management CAPF160

Incident Report (IWI)

**************************************************************************************************************
[Medical]
Medical Plan ICS 206

**************************************************************************************************************
[Liaison]
Agency Directory

External Requests

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
    - Need to develop/expand the certification library and wire it into the personnel module

**************************************************************************************************************
[Dockable Widgets]
    - Button widget that can be customized to launch a specific screen

**************************************************************************************************************
[Tech Debt / Infrastructure]
    - Optimization follow-up: profile Edit-menu windows and the task detail window to identify why modest datasets
      are not opening faster; tie this to any decision about reusing/caching Edit windows.
    - Sidebar: revisit large Edit-menu CSV import/export workflows with progress/cancel behavior and possible
      bulk API endpoints if large catalog imports prove slow or freeze the UI.
    - Remove legacy checkins, check_in_out, checkin_history, and logistics_resource_status_items collections
      and their routers once resource_status is confirmed stable and all callers are migrated.
      See Design Documents/legacycode.md for removal conditions and verification steps.
    - ResourceStatusDesk._sync_org_assignments() is live (incident_org.py was already on BaseRepository).
      Follow-up: verify end_assignment correctly clears assigned_to/assignment_reference in resource_status
      when a person is removed from a position.
    - Remove CIStatus enum (modules/logistics/checkin/models.py) after all callers are confirmed
      migrated to RESOURCE_STATUSES from resource_status/models.py.
  - Personnel export currently exports deep into the temporary folders - needs to export to documents by default and have a selctable export location
    - Cloud router (`cloud_server/router/`) forwards request/response and WebSocket bodies over the reverse tunnel as base64-in-JSON. Fine for typical form/photo sizes; revisit with a streaming transport if large file uploads through the router prove too slow. See `Design Documents/Instructions/cloud_router_architecture.md`.
