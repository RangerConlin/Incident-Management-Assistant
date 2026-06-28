**************************************************************************************************************
[Command]
Incident Command Dashboard
    - Needs to be redone.  UI style no longer fits with the program.  Redesign with larger card like structure for at-a-glance situational awarness
    - The communications card shows the wrong info - would do better to be either a most recent comms log or show priority entries.
    - Logistics card is ok if not as easy to read as I would like
    - Teams card is nice having the numbers at the top but quickly looses usage by only displaying status of three teams.  
    - Need to brainstorm what info is of most use on this window
Incident Overview 
   
Incident Organization
    - Window needs a complete redesign - the triple pane is clunky and outdated.
    - Flow for assigning someone to the chart is not obvious
        -- should allow for selection of someone checked in, anyone in the db (check in to incident and assign to position), and creation of a new record.
    - Position deputies are currently listed as a separate subordinate position, the should be listed under the branch director position as deputy position.  This method also allows for acting or trainee positions.
SITREP Window
    - Not yet built, still complete placeholder
Set ICP Location
    - Redundent now due to the facilites submodule
**************************************************************************************************************
[Planning]
Planning Dashboard
    - Poss needs a full redesign - some of the cards dont make any sense
    - Document health cycle cards are nice - expand on those poss into its own dashboard as well?
Operational Period Manager
    - Shows at the top no active OP however OP1 is clearly listed in the table as active.
    - Operational notes are unclear - poss reframe that section as the other fields needed for the 202 (command emphasis and sitrep)?  I like the safety and weather notes though.
    - Ensure unique OP # are enforced
    - Modify OP table to have standard colors and actions (selection borders, resizeable columns etc)
    - Double check that linked records numbers are pulling correctly
Demobilization Planner
    - Needs to have colors set to the correct light/dark palette.
    - Not able to tell anything beyond that due to colors, but demob module is still heavily scaffold
Meeting Planner
Individual Meeting Detail Windows
    - UI is a mess.  Table entries should all be capitalized, columns are the wrong width leading to data being hidden by default, tables are too small
Situation Report
    - Poss old code that can be removed (placeholder)
Tactics and Resource Planner
Weather
    - Not pulling any weather data - poss an API issue?
**************************************************************************************************************
[Operations]
Operations Dashboard
    - Data not filling correctly
        -- Available teams showing 17, not the correct number of "available" teams
    - Lots of fields in various places about task due dates, but no where is there a place to actually set a due date for a task
Operations Section Organization
    - Does not have a way to display or link branch directors and associates
    - Should not be displaying the service or support branches - this is the *Operations* section oragnization, not logistics
Team Assignments
    - Check prior documentation to see if we can figure out what this was supposed to be
Team Status Board
    - Expand columns available to display, allowing for more customized dashboards
    - Situational color assignment for the team type field vs the rest of the row is awkward - try to figure out a better way to display it
    - Expand/reformat the right click context menu
    - AOL currently displaying as Aol, should be spelled out
    - Need clearer distinction between ground and aerial assets on the board
    - When a team has a timer going off and the needs assistance flag I want them both to display at once, right now the needs assistance is overriding the timer.
Task Board
    - Expand columns available to display, allowing for more customized dashboards
**************************************************************************************************************
[Team Detail Window]

**************************************************************************************************************
[Task Detail Window]
Narrative Tab
    - Critical field still showing as 0/1 - should be displaying yes/no
    - for date/time can we stack date/time vertically to save horizontal space
    - Assignment tab is clunky and needs rework
    - Communications tab showing the channel picker drowpdown but selection isnt working or saving
    - On the debrief tab there needs to be a way to see who has reviewed the debrief
    - On the attachments tab instead of the type box showing doc/pfs/xls whatever, I want it to be a dropdown that lets me select things like maps/log/safety/etc
    - Log tab still not recording everything for audit
    - Planning tab was instructed not to have objectives link there - should only be links to strategies
    - Consider a locations tab - would be useful for things like ELT hits, witness addresses, etc
    - Need to have a way to view linked clues as well
    - Consider two row button bar for the tabs
**************************************************************************************************************
[Logistics]
Logistics Dashboard
    - "Open Full Dashboard" button in the bottom corner just opens the same window thats already open
    - Supply_comms health - what is that supposed to show/where is it supposed to get its info from
    - What is a "Top Logistic Action"
    - Consider redesigning dashboard from the ground up
    - What is a 218 thats missing a serial number?
Check In ICS-211
    - Quick check in dialog does not work
        -- Add additional method for check in similar to SAR Command Assist for total of
            --- Quick search by ID
            --- Create new record
            --- Select record filtered by organization
        -- Window is clunky to use, change ui to three sections - entry by id at top, two dropdowns in the middle with organization and people, then a button to add a new record at the bottom which opens up a modal
        -- Need to capture LDW info
        -- Format can remain similar for all types, add tabbed window at the top for each type defaulting to personnel
    - Need to have a way to list assets as pending/enroute/etc, all the non checked-in statuses to help with planning
    - Resource table does not conform with current ui standards
    - Resource table colors need to be darker, also include a legend at the bottom
Resource Status Board
    - Resource table does not conform with current ui standards
    - Resource table colors need to be darker, also include a legend at the bottom
    - Need to introduce tabs for different asset types
Resource Requests (ICS-214RR)
    - Default size needs to change - doesnt fit on window
        -- Window cant be shrunk to fit - must be maximised
    - If this feeds from tactics and resource planning doesnt need much work other than some UI refinement
    - What do the buttons on the top row do?
    - This module should be able to track everything required on the 213RR and should be able to cross populate needed info with finance
Facilities Manager
    - Everything being all lowercase needs to change

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
    - Somewhere on the intel dashboard I want to track team debriefs so intel can review them
Subjects
    - Table does not conform to UI standards
    - Subjects is still a shell for missing persons.  Need to expand the data to incorporate everything from the various data collection forms
        -- Do want a rapid missing person entry for small things like a missing child at a fair, something that doesnt need a full planning suite
Leads
    - Ensure leads can have a geocoded location referenced to them
    - Table does not conform to UI standards
Intel Items
    - Ensure intel items can have a geocoded location attached to them
    - Table does not conform to UI standards
Assessments
    - Have some kind of blurb at the top of the window about the function and purpose of the assessments
    - Detailed assessment window lists linked subjects and intel items but lists them by their private mongodb id.  Needs to be human readable title for them, also needs to open each record by clicking on them.  Also make sure this tab can reference leads as well.
    - Detailed Assessment window tabs can probably be combined into one window, with a split top area left for overview, right for linked intel items, and a bottom half/two thirds for the findings and recommendations
    - Need to figure out a format for these to print out in.  Find or create a standard form.
    - Table does not conform to UI standards
Intel Logs
    - Table does not conform to UI standards
Forms
    - Reduce down to only forms that touch or are touched by the intel unit.
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
[SAR Toolkit]

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
