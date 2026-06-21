# Toolkit Design Overview

## Purpose
Toolkits are focused, incident-driven workspaces that bundle a small set of related tools around a specific operational mode. They should help the user move through a recognizable field workflow without hunting across unrelated modules.

This document is a design playbook only. It does not authorize code changes by itself.

## Current Repo Direction
- `modules/toolkits/sar` currently exposes placeholder panels for:
  - Missing Person Report
  - Probability of Detection
- `modules/toolkits/initial` currently exposes placeholder panels for:
  - Hasty Team Form
  - Reflex Tasking
- `modules/toolkits/disaster` currently exposes placeholder panels for:
  - Damage Assessment
  - Urban Interview
  - Disaster Photos
- `modules/plannedtoolkit` already has a stronger pattern with multiple tool definitions, shared records, and a home panel.

## Design Intent
Each toolkit should feel like a guided operational lane, not just a menu folder.

Good toolkit design should:
- open with a clear "what do I do first?" view
- surface only the tools relevant to that operational context
- show the current incident everywhere
- reduce duplicate data entry by reusing shared incident, team, assignment, and location context
- support both rapid field use and later command review
- make status visible at a glance

## Shared Toolkit Pattern
Every toolkit should eventually define the same high-level pieces:

1. Home view
- quick summary of toolkit status
- active work items
- recent updates
- shortcuts into the most common actions

2. Core tools
- a small set of tightly related operational panels
- each panel should have a single clear job

3. Shared records model
- common concepts across toolkits:
  - status
  - priority
  - assigned unit or person
  - location
  - time windows
  - notes
  - attachments or references

4. Workflow states
- draft or not started
- in progress
- complete
- needs follow-up
- canceled or no longer needed

5. Command visibility
- command staff should be able to understand progress without opening every record
- dashboards should summarize counts, blockers, overdue items, and hot spots

## Architectural Guardrails
- No direct MongoDB access from UI.
- UI should go through API-backed repositories.
- Incident routing should remain explicit and testable.
- Reuse admin and command catalogs where they already exist.
- New toolkit-specific data should be designed so it can fit the MongoDB cutover path cleanly.

## Recommended Toolkit Families
- SAR Toolkit
- Initial Response Toolkit
- Disaster Response Toolkit
- Planned Events Toolkit

Additional toolkit categories can be added later as user needs evolve, which already matches the note in `Design Documents/designplan.md`.

## Cross-Toolkit Questions To Settle
- When does a toolkit deserve its own repository model versus reusing an existing module?
- Which fields should be standardized across all toolkit records?
- Which toolkit actions should create or update command tasks automatically?
- Which toolkits need offline-first rapid entry versus more detailed review screens?
- Which artifacts should be printable or exportable first?

## Suggested Next Design Step
Design each toolkit in four passes:
- operational goals
- user roles
- tool list and workflow
- data model and integration points

The companion markdown playbooks in this folder follow that format.
