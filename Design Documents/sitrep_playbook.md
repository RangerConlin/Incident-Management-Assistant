The SITREP submodule should be the incident’s running executive summary engine. It should not just be a place to type a narrative. It should pull key facts from the rest of SARApp, let staff verify/edit them, and generate clean situation reports for command staff, agency partners, briefings, and documentation.

Core purpose

The SITREP submodule should answer:

“What is the current situation, what has changed, what are we doing about it, and what needs attention?”

It should sit somewhere between the command dashboard, planning module, liaison module, and PIO module.

It should support:

Internal command updates.
Operational period summaries.
Agency partner updates.
Public-information-safe summaries.
End-of-period documentation.
Briefing prep.
A timeline of major changes.

The key is that the SITREP should be fast to produce, because nobody wants to write a full report every hour during an active incident.

SITREP submodule structure

I would build it around five main tabs:

Current SITREP
Changes / Significant Events
Operational Summary
Distribution / Versions
SITREP Archive

Optional later tab:

Templates / Settings
1. Current SITREP tab

This is the main working view.

It should be a structured report builder with auto-filled data on the left and editable narrative/report sections on the right.

Top status bar

At the top:

Field	Purpose
Incident Name	Pulled from incident info
SITREP #	Auto-numbered
Operational Period	Pulled from planning
Prepared By	Current user / selectable
Prepared Time	Auto timestamp
Status	Draft, Ready for Review, Approved, Distributed
Approved By	IC / delegated approver
Audience	Internal, Agency, Public-safe, Custom

This lets the same SITREP system generate different kinds of reports without mixing sensitive and public information.

Main sections

The current SITREP should have collapsible sections:

A. Situation Overview

A short executive summary.

Example fields:

Field	Type
Current Situation Summary	Narrative
Incident Type	Auto/manual
Area of Operations	Auto/manual
Current Priority	Select/text
Current Tempo	Stable, Escalating, De-escalating, Transitioning
Major Concern	Narrative
Next Decision Point	Narrative/date-time

This is the “tell me what is happening in one minute” section.

B. Subject / Incident Information

For SAR-specific work, this should adapt based on incident type.

For missing person:

Field	Source
Subject Name	Intel / Subjects
Age / Sex	Intel
Last Known Point	Intel / GIS
PLS / LKP Time	Intel
Description	Intel
Medical / Risk Factors	Intel
Search Urgency	Planning / Intel
POA/POD Status	Planning

For missing aircraft:

Field	Source
Aircraft Tail Number	Intel
Aircraft Type	Intel
Pilot / Occupants	Intel
Route of Flight	Intel
Last Contact	Intel
ELT Status	Intel
Search Area	GIS / Planning
Weather Factors	Weather module

For planned events:

Field	Source
Event Name	Incident info
Event Location	Incident info / GIS
Participant Estimate	Planning / Event profile
Operational Footprint	GIS
Current Event Status	Ops
Public Safety Concerns	Safety / Ops
C. Operational Status

This should auto-pull heavily from Operations.

Field	Source
Active Branches / Divisions / Groups	Operations
Teams Assigned	Teams board
Teams Available	Teams board
Teams Enroute / In Field / Returning	Team statuses
Active Tasks	Task board
Completed Tasks	Task board
Delayed / Blocked Tasks	Task board
Air Operations Status	Air / Ops
Comms Status	Communications
Logistics Status	Logistics
Planning Status	Planning

This section should not require someone to manually retype everything.

The user should be able to click Refresh From Modules, then manually edit the final wording.

D. Search / Response Progress

This is where the SITREP becomes more than a status board.

For SAR:

Field	Source
Areas Assigned	Planning / GIS
Areas Completed	Planning / GIS
Current POD / Coverage	Planning
Clues Found	Intel / Clues
Leads Pending	Intel
Leads Resolved	Intel
Notable Negative Searches	Tasks / Planning
Containment Status	Ops / Planning
Investigation Status	Intel / Liaison

For planned events:

Field	Source
Course / Venue Status	Ops
Traffic Status	Ops / Liaison
Medical Activity	Medical / Ops
Public Safety Issues	Safety
Crowd Status	Ops
Weather Impacts	Weather / Safety
Vendor / Agency Issues	Liaison
E. Safety / Hazards

Pulled from Safety, Weather, and field reports.

Field	Source
Current Hazards	Safety
Weather Concerns	Weather
Terrain / Environmental Concerns	GIS / Safety
Personnel Safety Issues	Safety / Ops
Operational Risk Level	Safety
Mitigations in Place	Safety
Stop / Hold Triggers	Safety

This is also where the system should flag obvious issues:

“Weather alert active.”

“Team overdue.”

“Aircraft status stale.”

“No Safety Officer assigned.”

“No comms check recorded in last X minutes.”

F. Resource Status

Pulled from Resource Planner and Logistics.

Field	Source
Personnel Checked In	Check-in
Personnel Assigned	Operations
Personnel Available	Operations
Vehicles Available	Resources
Aircraft Available	Resources
UAS Available	Resources
Critical Shortages	Logistics
Requested Resources	Logistics / Liaison
Incoming Resources	Logistics

This section should include both a summary and notable gaps.

G. Communications Status

This should pull from the comms module.

Field	Source
Primary Command Channel	Comms plan
Primary Tactical Channel	Comms plan
Repeater Status	Comms
Data / Tracking Status	Comms / Team tracking
Known Coverage Issues	Comms
ECC / RADO Status	Comms
Backup Plan	Comms

This is especially useful for partner agencies and command staff.

H. Liaison / Agency Coordination

Pulled from Liaison.

Field	Source
Agencies Involved	Liaison
Agency Status	Liaison board
Requests Sent	Liaison
Requests Received	Liaison
Pending External Decisions	Liaison
Political / Public Sensitivities	Liaison / PIO
Partner Concerns	Liaison feedback log

This should have visibility controls because not all liaison notes belong in every SITREP.

I. PIO / Public Information

This should not auto-publish anything. It should provide a clean public-info-safe block.

Field	Source
Public Statement Summary	PIO
Media Interest	PIO
Social Media Issues	PIO
Rumors / Misinformation	PIO
Approved Public Information	PIO
Information Not for Release	PIO / Intel

This is important because the same facts may be safe internally but not externally.

J. Needs / Issues / Command Decisions

This is one of the most important sections.

Field	Purpose
Immediate Needs	What command/logistics must solve
Resource Requests	What needs to be requested
Blockers	What is preventing progress
Decisions Needed	What IC/UC/agency lead needs to decide
Recommended Actions	Planning/Ops recommendations
Next Update Due	Time

This section turns the SITREP from passive reporting into an action tool.

2. Changes / Significant Events tab

This should be a timeline-focused tab.

Not everything belongs in the main report, but significant changes need to be tracked.

Significant event fields
Field	Type
Time	Timestamp
Event Type	Dropdown
Summary	Short text
Source	Team, agency, radio log, intel, command, weather
Impact	Low, Medium, High, Critical
Related Module	Task, Team, Clue, Lead, Resource, Weather, Agency
Include in SITREP	Checkbox
Include in 214	Checkbox
Public-safe	Checkbox
Reviewed By	User
Notes	Narrative
Event types

Suggested event types:

Type	Example
Command Decision	Search suspended, new objective set
Operational Change	New division opened, branch reorganized
Assignment Change	Team reassigned
Resource Change	Aircraft added, K9 unavailable
Safety Issue	Heat injury, lightning hold
Weather Change	Warning issued
Clue / Lead	Item found, witness report received
Subject Update	New subject info
Agency Coordination	Sheriff request, fire department support
Public Information	Press release issued
Communications	Repeater failure, channel change
Logistics	Fuel shortage, food delivered
Medical	Patient contact, aid station activity

This tab should feed both:

The SITREP narrative.
The incident timeline / ICS-214-style logs.
3. Operational Summary tab

This should be a more data-driven dashboard used to populate the report.

Think of this as the “facts before narrative” screen.

Suggested layout
Left column: Resource counts
Metric	Example
Total Checked In	47
Assigned	32
Available	8
Out of Service	2
Released	5
Teams Active	6
Teams Available	2
Aircraft Active	1
Vehicles Assigned	9
Middle column: Task status
Status	Count
Planned	4
Assigned	6
In Progress	5
Complete	11
Suspended	1
Blocked	2
Right column: Alerts
Alert	Source
Team overdue	Operations
Weather warning active	Weather
No comms check in 30 min	Comms
Resource request pending	Logistics
Unreviewed clue	Intel

Below that, a section for auto-generated summary text:

“As of 1430, 6 teams are assigned, 5 tasks are in progress, and 11 tasks have been completed. Current operational concerns include one overdue team, a pending weather alert, and two unresolved high-priority leads.”

The user should be able to click:

Insert Into SITREP

4. Distribution / Versions tab

A good SITREP system needs version control.

Version types
Version	Purpose
Internal Command	Full operational summary
Agency Partner	Removes internal-only notes
Public-safe	Only approved public information
Planning Brief	Focused on next operational period
End-of-Period	Documentation-focused
Custom	User-selected sections
Distribution fields
Field	Purpose
Version Name	SITREP 004 - Agency
Audience	Internal / External / Public
Recipients	Agencies, roles, contacts
Delivery Method	Print, PDF, email, copied text
Approval Required	Yes/no
Approved By	IC / PIO / Liaison
Distribution Time	Timestamp
Distribution Notes	Optional
Important feature

Each SITREP version should have a redaction / visibility layer.

Every section or field should support a visibility label:

Visibility	Meaning
Internal	Command staff only
Agency	External partner safe
Public	Public release safe
Sensitive	Restricted / requires manual review

This is especially important for subject information, medical information, family contacts, law enforcement info, and investigation details.

5. SITREP Archive tab

This is the historical record.

It should list all generated SITREPs.

Archive columns
Column	Example
SITREP #	003
Time Prepared	2026-07-05 1415
Operational Period	OP 2
Prepared By	Planning Section
Status	Approved
Audience	Internal
Distributed	Yes
Approved By	IC
Summary	Search expanded north of LKP...

Actions:

Action	Purpose
View	Open read-only version
Duplicate	Start next SITREP from previous
Revise	Create new revision
Export PDF	Generate PDF
Export Text	Copy into email/chat
Compare	Show changes between reports
Lock	Prevent further editing
Recommended UI layout

For the main Current SITREP screen, I would use a three-pane layout.

+--------------------------------------------------------------------------------+
| SITREP #004 | OP 2 | Draft | Prepared 1430 | Audience: Internal | [Refresh]     |
+--------------------------------------------------------------------------------+
| LEFT NAV             | CENTER REPORT BUILDER              | RIGHT FACT PANEL    |
|----------------------|------------------------------------|---------------------|
| Situation Overview   | Situation Overview                 | Auto-pulled facts    |
| Subject Info         | [Narrative text box]               |                     |
| Operational Status   |                                    | Teams:              |
| Search Progress      | Current Priority: [dropdown]       | Active: 6           |
| Safety / Hazards     | Current Tempo: [dropdown]          | Available: 2        |
| Resources            |                                    | Overdue: 1          |
| Communications       | [Insert auto-summary]              |                     |
| Liaison              |                                    | Tasks:              |
| PIO/Public Info      | Operational Status                 | In Progress: 5      |
| Needs / Decisions    | [Structured fields + narrative]    | Complete: 11        |
|                      |                                    |                     |
|                      |                                    | Alerts:             |
|                      |                                    | ⚠ Weather alert     |
|                      |                                    | ⚠ Pending request   |
+--------------------------------------------------------------------------------+
| [Save Draft] [Ready for Review] [Approve] [Generate Version] [Export]           |
+--------------------------------------------------------------------------------+

This avoids the trap of making the SITREP feel like a giant form.

The right side should always show the current facts and alerts, so the person writing the report does not have to bounce around the application.

SITREP workflow

The workflow should be simple:

Draft flow
User opens SITREP.
SARApp creates next SITREP number.
System pulls current facts from modules.
User reviews auto-filled sections.
User adds narrative and command context.
User marks sections as internal / agency / public-safe.
User sends to review.
IC or delegated approver approves.
User generates/export version.
SITREP locks into archive.
Fast update flow

For high-tempo incidents, there should be a faster path:

Click New Quick SITREP.
Select audience.
System generates current status.
User fills only:
Situation summary
Major changes
Current needs
Next update time
Export/send.

This matters. In real use, nobody is going to fill out a massive report every 30–60 minutes.

Suggested data model

Rough conceptual model:

Sitrep
- id
- incident_id
- sitrep_number
- operational_period_id
- created_at
- prepared_by
- status
- audience
- approved_by
- approved_at
- distributed_at
- summary
- current_priority
- current_tempo
- next_update_due
- sections[]
- linked_events[]
- linked_tasks[]
- linked_resources[]
- linked_agencies[]
- version_history[]
SitrepSection
- id
- sitrep_id
- section_type
- title
- source_module
- auto_generated_content
- edited_content
- visibility
- review_status
- include_in_export
- last_refreshed_at
SitrepEvent
- id
- incident_id
- timestamp
- event_type
- summary
- source
- impact
- visibility
- include_in_sitrep
- include_in_214
- linked_record_type
- linked_record_id
SitrepDistribution
- id
- sitrep_id
- version_name
- audience
- recipient_group
- delivery_method
- approved_by
- distributed_by
- distributed_at
- export_file_path
Statuses
SITREP status
Status	Meaning
Draft	Being written
Ready for Review	Waiting on approval
Needs Revision	Reviewer sent it back
Approved	Can be distributed
Distributed	Sent/exported
Archived	Locked historical record
Section review status
Status	Meaning
Auto-filled	Pulled from modules
Edited	User modified
Needs Review	Sensitive or stale data
Reviewed	Checked by user
Excluded	Not included in output
Important buttons/actions
Main actions
Button	Purpose
Refresh From Modules	Pull current facts again
Insert Auto Summary	Add generated text into a section
Mark Public-Safe	Set visibility
Flag Sensitive	Prevent accidental export
Ready for Review	Send to approver
Approve	Lock approved content
Generate Version	Create internal/agency/public version
Export PDF	Printable/report version
Copy Text	Paste into email/chat/radio log
Archive	Finalize record
Safety action

There should be a button or warning state:

Review Sensitive Fields

This catches:

Subject medical details.
Juvenile information.
Family contact info.
Law enforcement-sensitive info.
Unconfirmed leads.
Internal disagreements.
Personal responder information.
Anything marked “Sensitive.”
Auto-generated summary behavior

This is where the module can feel genuinely useful.

The system should generate a plain-language summary based on known data, but the user must approve/edit it.

Example:

As of 1430, operations remain active in the northern and eastern search areas. Six ground teams are currently assigned, with two teams available for reassignment. Eleven tasks have been completed during the current operational period, and five remain in progress.

The primary operational concern is the pending high-priority lead near the eastern trail system. Weather remains a concern due to increasing winds and an active thunderstorm watch. No injuries have been reported. The next major decision point is whether to expand the search area during the next operational period.

That kind of text is useful. A fully automated official report is risky. Auto-generated draft text with human approval is the right balance.

Integration with other modules
Operations

Pulls:

Team statuses.
Task statuses.
Branch/division/group structure.
Overdue teams.
Assignment changes.
Completed work.

Pushes:

Command decisions.
New issues requiring tasking.
Planning

Pulls:

Operational period.
Objectives.
Search areas.
POA/POD.
Completed assignments.
Next period planning issues.

Pushes:

End-of-period summary.
Unresolved planning questions.
Decision points.
Intel

Pulls:

Subject profile.
Clues.
Leads.
Witness/RP updates.
Investigation notes.

Pushes:

Significant updates.
Unresolved questions.
Liaison

Pulls:

Agency involvement.
Requests.
Partner feedback.
External support status.

Pushes:

Agency-safe SITREP versions.
Requests for update.
PIO

Pulls:

Approved public information.
Media status.
Rumor/misinformation notes.

Pushes:

Public-safe summary draft.
Items requiring PIO review.
Logistics

Pulls:

Resource shortages.
Incoming resources.
Facilities status.
Food/fuel/supply issues.

Pushes:

Needs and blockers.
Safety

Pulls:

Hazards.
Weather concerns.
Risk level.
Safety messages.
Stop/hold triggers.

Pushes:

Safety concerns for command attention.
Suggested MVP

Do not overbuild this first.

The MVP should include:

Current SITREP builder
Auto-numbered SITREPs
Manual sections with some auto-filled counts
Significant events list
Visibility labels: Internal / Agency / Public / Sensitive
Export to PDF/text
Archive previous SITREPs
Duplicate previous SITREP to create next one

That is enough to make it useful.

MVP sections

Start with these:

Situation Overview
Operational Status
Significant Changes
Safety / Hazards
Resource Status
Communications Status
Liaison / Agency Coordination
Needs / Decisions
Next Update

Subject-specific sections can come after.

Later enhancements

After the MVP works, add:

Auto-generated narrative summaries.
Compare SITREP versions.
Public-safe redaction preview.
Review/approval workflow.
Agency distribution lists.
Module-driven alert detection.
Operational-period closeout summary.
Map snapshot attachment.
Weather snapshot attachment.
ICS-209-style summary output if desired.
My recommended design direction

Build the SITREP submodule as a living report builder plus significant-events tracker.

Do not make it just a static form.

The strongest version is:

Auto-pulls current facts.
Lets staff edit and approve text.
Tracks significant changes.
Creates different report versions for different audiences.
Archives every report.
Feeds planning, liaison, PIO, and the incident record.

That gives SARApp something better than a document template: it becomes the place where the incident’s current story is maintained.

I would treat ICS-209 export as a first-class output type, not as an afterthought. The internal SARApp SITREP should be richer and more flexible than an ICS-209, then the export layer maps that internal data into ICS-209, agency-specific SITREPs, public-safe summaries, and custom local forms.

FEMA currently lists ICS Form 209, Incident Status Summary v3, in its ICS forms library, and FEMA describes the ICS-209 as summarizing incident information for staff and external parties while also supporting PIO media release preparation. So the SITREP module should basically become the source data engine for that form.

Design change: add an Export Profiles layer

Add a sixth major tab:

6. Form Exports

This tab would manage all formal outputs:

Export Type	Purpose
SARApp SITREP	Internal flexible report
ICS-209	Formal Incident Status Summary
Agency SITREP	Partner agency update
Public SITREP	Public-safe operational update
EOC Update	Short executive status report
Operational Period Summary	End-of-period command/planning summary
Custom Form	Local county/state/team template

The internal SITREP should not be shaped exactly like the ICS-209. That would make it clunky. Instead, SARApp should maintain a canonical SITREP data model, then map that data into different forms.

Key architecture: one SITREP record, many outputs

The internal record should be the master.

SARApp SITREP Record
        |
        +--> SARApp Internal SITREP PDF
        +--> ICS-209 PDF
        +--> Agency Partner SITREP
        +--> Public-safe SITREP
        +--> EOC Update
        +--> Plain-text email update
        +--> Custom local form

This means the user enters/reviews the information once, then exports it many ways.

The form export system should have:

Component	Purpose
Form Template	The blank official/custom form
Field Map	Which SARApp data goes into which form fields
Export Profile	Audience, redaction rules, included sections
Validation Rules	Required fields, length limits, missing-data warnings
Render Engine	PDF/text/docx/HTML output
Archive Copy	Locked copy of what was exported
ICS-209 as a mapped export

ICS-209 should be a guided export wizard because it has fields that may not perfectly match a SAR-specific SITREP.

ICS-209 Export Workflow
Open SITREP.
Click Generate Form Export.
Select ICS-209 Incident Status Summary.
SARApp pre-fills what it can.
User reviews unmapped or incomplete fields.
System flags missing required fields.
User chooses output:
Fillable PDF
Flattened PDF
Print packet
Archived PDF
Export is locked to SITREP version.

The review step matters. Auto-filling an ICS-209 blindly is a bad idea.

Suggested ICS-209 mapping approach

The exact PDF field mapping would need to be built against the actual fillable PDF fields, but conceptually:

ICS-209 Area	SARApp Source
Incident Name	Incident profile
Incident Number	Incident profile
Date/Time Prepared	SITREP metadata
Operational Period	Planning module
Incident Type	Incident profile
Location / Jurisdiction	Incident profile / GIS
Current Incident Size / Area	GIS / Planning
Current Situation	SITREP Situation Overview
Significant Events	Significant Events tab
Current Objectives	Planning objectives
Management Organization	Command/org module
Resource Summary	Check-in / resources / operations
Casualty / injury summary	Medical / safety / ops
Threat / hazard summary	Safety / weather
Weather concerns	Weather module
Projected Activity	Planning / next-period notes
Critical Resource Needs	Logistics / Needs & Decisions
Facilities	Logistics / incident facilities
Prepared By	SITREP metadata
Approved By	SITREP approval metadata

For SAR specifically, some information will not have a clean home on ICS-209. That is fine. SARApp should use remarks / situation narrative / significant events intelligently, and avoid forcing bad data into the wrong boxes.

Add a “Form Readiness” panel

For formal exports, add a right-side readiness panel.

Example:

ICS-209 Readiness

Ready:
✓ Incident name
✓ Incident number
✓ Operational period
✓ Prepared by
✓ Current situation
✓ Resource summary
✓ Significant events

Needs review:
⚠ Incident size / affected area
⚠ Projected activity
⚠ Critical resource needs

Missing:
✕ Approval official
✕ Jurisdiction / agency

This would be extremely useful. It tells the user whether the report is ready without making them hunt through the form.

Add field confidence levels

Each exported field should have a confidence/source state:

State	Meaning
Verified	User reviewed it
Auto-filled	Pulled from another module
Edited	User changed it
Stale	Source data changed since review
Missing	Needs entry
Sensitive	Requires redaction review
Not Applicable	Intentionally blank

For ICS-209, the export wizard should not just show field values. It should show whether each value is reliable.

Example:

Current resource count: 42 personnel
Source: Check-in module
Status: Auto-filled
Last refreshed: 1427

If check-in changes after the SITREP was drafted, SARApp should warn:

Resource data changed since this SITREP section was reviewed.

That kind of warning is more valuable than fancy formatting.

Other SITREP form support

I would design “other SITREP forms” as template packs.

Template pack examples
Template Pack	Use
FEMA / ICS	ICS-209, ICS-214 excerpts, ICS-213 message summary
County EOC	Local EOC update form
State EM	State situation report format
SAR Team	Internal search status update
Law Enforcement Partner	LE-sensitive summary
Public Information	PIO-approved public update
Planned Event	Event status update
Aviation Search	Aircraft incident update
Missing Person Search	Subject/search progress update

This avoids hardcoding everything into the SITREP module.

Form Template Manager

Eventually, SARApp should have a small Form Template Manager that lets you define:

Setting	Example
Template Name	County EOC SITREP
Form Type	PDF / DOCX / HTML / plain text
Audience	Agency
Required Fields	Situation, resources, needs
Source Fields	SITREP, Ops, Logistics, Safety
Redaction Level	Agency-safe
Export Format	PDF
Default Approval	IC or Planning Section Chief

This should tie into the forms registry you already have planned.

The SITREP module should not own every possible form. It should call the forms/export system.

Recommended export types
1. Official PDF form export

For ICS-209 and any fillable PDF forms.

Output options:

Option	Purpose
Fillable PDF	User can still edit externally
Flattened PDF	Locked final copy
Print PDF	Clean paper version
Archive PDF	Stored in incident record
2. Plain text export

This is underrated and should absolutely exist.

Useful for:

Email updates.
Chat messages.
Radio-room logs.
Quick agency notifications.
Copy/paste into another system.

Example:

SITREP 004
Incident: Smith Search
Prepared: 1430
Operational Period: OP 2

Current Situation:
Search operations remain active in the northern and eastern sectors...

Significant Changes:
- 1320: High-priority lead received near east trailhead.
- 1355: Thunderstorm watch issued.
- 1410: Team 3 reassigned to containment.

Current Needs:
- Additional ground team for OP 3.
- Updated weather decision by 1600.
3. Executive brief export

Short version for command staff or agency leadership.

Sections:

Current situation.
Major changes.
Current risks.
Resource needs.
Decisions required.
Next update time.
4. Public-safe export

PIO-oriented.

Hard rules:

Only public-approved fields.
No subject medical details unless explicitly approved.
No home addresses unless approved.
No unconfirmed leads.
No responder personal details.
No internal disagreement or operational vulnerability.
5. End-of-period export

For Planning.

Sections:

Objectives status.
Assignments completed.
Work remaining.
Significant events.
Resource use.
Safety issues.
Recommendations for next OP.

This could later feed the next planning cycle.

Add “Export Preview with Redaction”

Before producing any agency or public version, show a preview:

Public-safe SITREP Preview

Included:
✓ General incident status
✓ Approved public summary
✓ Weather statement
✓ Next public update time

Excluded:
✕ Subject medical details
✕ Unconfirmed witness lead
✕ Team locations
✕ Internal resource shortage note
✕ Law enforcement-sensitive information

This is not optional. It prevents accidental oversharing.

Data model additions

Add these objects:

SitrepExportTemplate
- id
- name
- form_family
- form_version
- output_type
- file_template_path
- field_map_id
- default_audience
- default_visibility_rules
- validation_profile_id
- is_official_form
- enabled
SitrepFieldMap
- id
- template_id
- form_field_name
- sarapp_source_path
- transform_rule
- fallback_text
- max_length
- required
- visibility_required
SitrepExport
- id
- sitrep_id
- template_id
- export_name
- audience
- generated_at
- generated_by
- approval_status
- approved_by
- approved_at
- output_file_path
- flattened
- field_snapshot
- warnings
SitrepExportValidation
- id
- export_id
- field_name
- status
- message
- severity
- source_record_id

The important one is field_snapshot.

When you export an ICS-209, SARApp should save the exact values used at that moment. If the underlying team count changes later, the archived ICS-209 should not silently change.

Form mapping UI

The form mapping screen should look something like this:

+--------------------------------------------------------------------------------+
| Export Profile: ICS-209 Incident Status Summary v3                              |
+--------------------------------------------------------------------------------+
| Form Field                     | SARApp Source                 | Status          |
|--------------------------------|-------------------------------|-----------------|
| Incident Name                  | Incident.name                 | Verified        |
| Incident Number                | Incident.number               | Verified        |
| Date/Time Prepared             | SITREP.prepared_at            | Auto-filled     |
| Operational Period             | Planning.current_op_period    | Auto-filled     |
| Current Situation              | SITREP.situation_summary      | Needs Review    |
| Significant Events             | SITREP.significant_events     | Verified        |
| Resource Summary               | Resources.summary_counts      | Stale           |
| Critical Resource Needs         | Logistics.critical_needs      | Missing         |
+--------------------------------------------------------------------------------+
| [Refresh Sources] [Review Missing] [Preview Form] [Generate PDF]                |
+--------------------------------------------------------------------------------+

For MVP, this does not need to be a full drag-and-drop mapper. It can be a fixed internal mapping for ICS-209 and a small configuration file later.

MVP export support

For the first version, I would support:

SARApp Internal SITREP PDF
Plain-text SITREP
ICS-209 PDF export
Public-safe text export
Archive export history

Do not start by building a universal form designer. That will eat time.

MVP ICS-209 behavior

MVP should:

Load the official ICS-209 fillable PDF template.
Populate known fields.
Let the user review missing fields in SARApp.
Export a filled PDF.
Optionally flatten the PDF.
Save the exported copy to the incident record.
Save field snapshot and warnings.

That is plenty.

Later enhancement: custom form imports

Later, add:

Feature	Value
Import fillable PDF	User loads agency SITREP form
Detect PDF fields	SARApp lists field names
Map fields to SARApp data	User assigns source values
Save as template	Reuse for future incidents
Version template	Avoid breaking older exports
Organization profiles	County, CAP, state, team, agency-specific

This would make SARApp very powerful, but I would not make it MVP.

How it should connect to the forms registry

Since you already want a forms registry with profiles and binding dictionaries, SITREP should use that instead of creating a separate one-off export system.

Recommended structure:

/forms/
  /templates/
    /ics/
      ICS_209_v3.pdf
    /sarapp/
      internal_sitrep.html
    /local/
      county_eoc_sitrep.pdf

  /bindings/
    /ics/
      ICS_209_v3.binding.json
    /sarapp/
      internal_sitrep.binding.json
    /local/
      county_eoc_sitrep.binding.json

  /profiles/
    ics.profile.json
    county.profile.json
    sarapp.profile.json

The SITREP module should send a data package to the forms engine:

sitrep_export_package = {
  incident,
  sitrep,
  operational_period,
  command_staff,
  resources,
  teams,
  tasks,
  safety,
  weather,
  liaison,
  pio,
  significant_events
}

Then the forms engine maps it.

That keeps the design clean.

Strong recommendation

Build the SITREP submodule as:

SITREP + Export Center

Not just “SITREP.”

The module should have two responsibilities:

Maintain the current incident status narrative.
Generate official and audience-specific status outputs.

The key design principle:

SARApp’s internal SITREP is the source of truth. ICS-209 and other forms are outputs.

That gives you flexibility without making users fight the structure of a federal form during a live incident