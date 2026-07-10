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
  - Move to under the command menu
  
Tactics and Resource Planner
  - On the main table the objective isnt showing human readable
  - Need to create and tie into logistics requests
  - Expand assigned resources and tie into this and logistics requests in order to fill requests
  - Log doesnt seem to be logging anything
  - Theres a button for apply default hazards, but there doesnt seem to be a way to assign default hazards

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
  - Personnel and vehicles not populating from attached teams
  - SAR 104 export leads to attribute error 
  - Communications channels need a selector for channel type (primary/alternate/etc)
  - Forms that fail to generate still create a record in the attachments table leading to more errors
  - 104/109 exports need to be tied to a specific team somehow

**************************************************************************************************************
[Logistics]
Logistics Dashboard

Check In ICS-211
  - Change this from a quick checkin to the full checking
  - Create new quick checkin focused on scanning IDs and checking in rapidly - stripped down window with entry box, display box for record returns, and large buttons at the bottom for checkin status
    
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
  - Integrate USCG GAR model on the task/assignment side (SPE hazard scoring is done — see Safety Risk Manager, modules/safety/orm/)
    -- New Safety tab in the task detail window?
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
  - Mostly scaffold still, need to design further and expand into a workable module
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
    - Button widget that can be customized to launch a specific screen
    - Code for KPI display widget exists but isnt exposed anywhere

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

**************************************************************************************************************
[Logs]
  - Logs need to be able to write to multiple streams at once.  Would like to be able to generate a log for each individual person, but i dont think writing a separate stream is a good idea.  perhaps something that generates from a lookup of everything that person has done?
