# Incident Staff UI Handoff

## Backend behavior

Mobile identity remains profile-based and does not require a password. After
the profile is synchronized and `/api/auth/sessions` returns a
`person_record`, enter the selected incident with:

`POST /api/incidents/{incident_id}/mobile/entry`

Request:

```json
{
  "person_record": 142,
  "team_id": 12
}
```

`team_id` is optional. Omitting it enters the incident without changing an
existing team assignment. A first-time entrant is checked in automatically.

Response:

```json
{
  "person": {
    "person_record": 142,
    "name": "Jordan Smith"
  },
  "resource_status": {
    "status": "Checked In"
  },
  "team": {
    "team_id": 12,
    "team_name": "Ground Team 2",
    "team_role": "Ground Search",
    "is_leader": false
  },
  "staff_assignments": [
    {
      "position_id": 17,
      "title": "Communications Unit Leader",
      "classification": "unit",
      "assignment_type": "primary",
      "start_time": "2026-10-21T01:30:00+00:00"
    }
  ]
}
```

`team` is `null` when the person is not on a field team. All other keys remain
present; `staff_assignments` may be empty.

Refresh the same facts without changing incident state with:

`GET /api/incidents/{incident_id}/mobile/context/{person_record}`

## Client behavior

The server never selects a screen. The client applies the product rule:

- `team != null`: open Field MDT by default and allow switching to Incident Staff.
- `team == null`: open Incident Staff.

A staff assignment is context for notifications, messages, approvals, and
labels. It does not decide which experience opens. A person may have a team,
staff positions, both, or neither.

## States the design must cover

- New incident entrant with no team and no staff position.
- Base/incident staff member with one or more staff positions and no team.
- Field member with a team and no staff position.
- Person with both a team and staff position, including the experience switcher.
- Team assignment added or removed while the app is open.
- Incident entry or context refresh unavailable while offline.
- Profile identity ambiguous because more than one master record uses the same visible ID.

## Current placeholder

`IncidentStaffDashboardScreen` is intentionally a blank shell. It starts
presence, chat presence, and push registration, shows the active incident,
and provides a Switch Incident action. Its layout is not a design constraint.
