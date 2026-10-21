# Mobile Experience

The mobile app is a companion surface for field users. This document should track what the mobile app can do now, what is only planned, and where it connects to desktop-created incident workflows.

## Intended Users

- Field personnel
- Team members
- Team leaders
- Responders checking in or out
- Users sharing location or status with command staff
- Incident and base staff who need incident awareness, notifications, and chat

## Current-State Review Areas

- What login, connection, and incident-selection flows exist?
- What check-in or identity workflows exist?
- What field status or location workflows exist?
- What assigned-work views exist?
- Which workflows are only planned or partially built?
- Which desktop modules does mobile depend on?

## Current Mobile Feature Areas

### Identity And Connection

The mobile profile is operational identity rather than an access-control
boundary. A profile may match an existing master personnel record or create
one when the person is new. People may enter an active incident without being
pre-rostered. The server creates their incident participation records on first
entry and returns their current status, optional team, and active staff
positions.

The server returns facts and never selects a client screen. Mobile uses two
experiences: Field MDT when the person is attached to a team, and Incident
Staff when no team is attached. A team member may also switch to Incident
Staff once that control is designed.

### Field Participation

Field MDT remains the existing team-centric workflow. Team membership is
owned by the team record. A person without a team remains a valid incident
participant and uses the Incident Staff experience.

### Field-To-Command Signal

Mobile incident entry creates or refreshes shared check-in state. Selecting a
team updates the shared team roster. Chat, presence, push registration, and
notification acknowledgement continue to use the shared incident services.

## Backend Contract For UI Design

`POST /api/incidents/{incident_id}/mobile/entry` accepts `person_record` and
an optional `team_id`. It returns:

- `person`: the incident personnel identity snapshot;
- `resource_status`: current check-in and operational status;
- `team`: `{team_id, team_name, team_role, is_leader}` or `null`;
- `staff_assignments`: zero or more active incident organization positions.

The client derives its initial experience from whether `team` is null. Staff
assignments support position-aware notifications, message groups, approvals,
and display context but do not select the client experience.

## Design Questions

- Which desktop workflows should have a mobile companion version?
- Which workflows should remain desktop-only?
- Should mobile focus on individuals, teams, or both?
- How much incident context should field users see?
- How should mobile users understand whether tracking, check-in, and assignment updates are active?
