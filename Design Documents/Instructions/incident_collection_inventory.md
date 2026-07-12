# Incident Database Collection Inventory

This file lists the MongoDB collections that can currently be created inside a
per-incident database named `sarapp_incident_<incident_id>`.

Source of truth for names is `data/db/sarapp_db/mongo/collection_names.py`.
This inventory describes intended purpose, current canonical status where known,
and legacy/cleanup concerns. It does not describe `sarapp_system` or
`sarapp_master` collections.

## Canonical Notes

- `tasks` is the canonical task collection. `operations_tasks` is only a code
  constant alias that points to the same physical `tasks` collection.
- `resource_status` is intended to be the canonical resource state collection
  for incident personnel, vehicles, aircraft, and equipment. Older resource
  collections remain in code and should be cleaned up as tracked in `backlog.md`
  and `Design Documents/legacycode.md`.
- Several CAP ORM collections are retained for legacy CAPF-style form binding
  even though the canonical Safety Risk Manager writes to `hazards`.
- Some scaffold-heavy module collections can exist before the UI is complete.

## Incident Structure And Planning

| Collection | Purpose |
|---|---|
| `incident_profile` | One or more incident profile documents containing incident number, name, type, status, start/end times, ICP location, training flag, and related incident metadata. |
| `operational_periods` | Operational period records for planning, schedule boundaries, and period-specific form/report context. |
| `incident_objectives` | Incident objectives used by command/planning and linked to strategies or task work. |
| `strategies` | Strategy/work-strategy records, formerly named strategic objectives in earlier designs. |
| `work_assignments` | ICS-204/tactics work assignments. Current schema decisions treat these as strategy-side planning objects, not task duplicates. |
| `meetings` | Incident meeting records, including meeting details plus embedded attendees and checklist items. |
| `iap_packages` | IAP package records. Each package embeds its forms and related package data. |

## Teams And Tasks

| Collection | Purpose |
|---|---|
| `teams` | Incident-specific team records, including team identity, status, leader/contact data, member/resource composition, assignment state, and check-in/disband state. |
| `tasks` | Canonical operations task collection. Task documents hold task headers, status/priority, assignment information, embedded team assignments, audit/status arrays, communications, task narrative entries, and some task detail data. |
| `task_debriefs` | Task debrief records and embedded form payloads associated with completed or reviewed task work. |

## Incident Organization

| Collection | Purpose |
|---|---|
| `org_positions` | Flat CRUD collection for ICS-203/organization positions within an incident. |
| `org_assignments` | Flat CRUD collection for assigning people/resources to organization positions and tracking assignment start/end details. |
| `org_templates` | Incident-scoped organization templates or copied organizational structures. |

## Resource State And Logistics

| Collection | Purpose |
|---|---|
| `resource_status` | Intended canonical incident resource-state collection for personnel, vehicles, aircraft, and equipment. Tracks entity type, record ID, display name, current status, assignment, location, notes, check-in time, and status history. |
| `resource_requests` | Canonical Logistics Resource Request / ICS-213RR collection, including request headers, items, approval actions, fulfillment records, audit entries, and delivery location/facility references. |
| `logistics_resource_status_items` | Legacy logistics board status-copy collection. Superseded by `resource_status` and retained only until old readers/writers are removed. |
| `resources` | Older incident resource status/snapshot collection. Current cleanup work should resolve whether this remains needed or is fully superseded by `resource_status`. |
| `check_in_out` | Legacy check-in/out collection for non-personnel resources. Superseded by `resource_status`. |
| `checkins` | Legacy personnel check-in/detail collection. Superseded by `resource_status`. |
| `checkin_history` | Legacy check-in history/event collection. Some history reads remain, but canonical status history belongs in `resource_status.status_log`. |
| `incident_personnel` | Incident-scoped personnel roster/cache copied from master personnel for active incident use, joins, forms, and status board context. |
| `facilities` | Incident facilities such as ICP, staging areas, shelters, medical locations, or other operational facilities. |

## Communications And Logs

| Collection | Purpose |
|---|---|
| `communications_plan` | Per-operational-period communications plan record for general comms planning data. Currently stores ICS-205 special instructions and can also hold phone/contact blocks and broader communications notes. |
| `communications_log` | Incident communications log / ICS-309 style traffic entries, including simple create/update/delete metadata fields on each entry. |
| `incident_channels` | Incident-assigned radio/channel plan entries copied or derived from master radio channels, including ICS-205 inclusion and incident-specific overrides. |
| `ics_214_logs` | Canonical ICS-214 activity log collection. Each document is a stream for a unit, team, section, or entity, with entries embedded in `entries`. Desktop panels, mobile team logs, auto-generated status entries, exports, and form context all use this collection. |
| `notifications` | Incident-scoped alert/notification history. |

## Medical And ICS 206

| Collection | Purpose |
|---|---|
| `ics_206_aid_stations` | ICS-206 aid station entries for the medical plan. |
| `medical_plan` | Canonical per-operational-period medical plan / ICS-206 document. Embeds ambulance service references/details, hospital references/details, air ambulance references/details, medical communications rows, emergency procedures, and prepared/approved signature metadata. |
| `ics_206_builds` | Generated or staged ICS-206 build records. |
| `medical_incidents` | Medical incident records associated with safety/medical reporting. |
| `triage_entries` | Triage records for patient or medical-response tracking. |

## Safety

| Collection | Purpose |
|---|---|
| `hazards` | Canonical Safety Risk Manager hazard register. Uses SPE scoring and links hazards to work assignments, teams, and tasks. |
| `safety_reports` | General incident safety report records. |
| `hazard_zones` | Mapped or named hazard zone records used for safety planning and forms. |
| `iwi_reports` | Safety incident / IWI reports. |
| `ics_208_instances` | ICS-208 Safety Message records, typically one per incident and operational period. |
| `cap_orm_forms` | Legacy CAP ORM form records retained for CAPF-style form export/binding. |
| `cap_orm_hazards` | Legacy CAP ORM hazard rows associated with CAP ORM forms. |
| `cap_orm_summaries` | Legacy CAP ORM summary records for form/export context. |
| `cap_orm_audit` | Legacy CAP ORM audit records. |

## Forms And Attachments

| Collection | Purpose |
|---|---|
| `forms` | Incident form instances with embedded field values. |
| `form_instance_revisions` | Revision history for incident form instances. |
| `form_instance_audit` | Audit/change events for form instances. |
| `form_instance_exports` | Export records for generated form files or export artifacts. |
| `form_instance_links` | Links between form instances and other incident entities. |
| `attachments` | Incident attachment metadata and file references. |

## Public Information

| Collection | Purpose |
|---|---|
| `pio_messages` | Public information messages, releases, or draft communications, with lifecycle approval history embedded in each message document. |
| `pio_message_revisions` | Revision history for PIO messages/releases. |
| `pio_media_log` | Media contact/activity log records. |
| `pio_misinformation_items` | Misinformation/rumor records tracked by PIO, with timeline events embedded in each item document. |
| `pio_talking_points` | Talking point records for briefings/releases. |
| `pio_templates` | Incident-scoped PIO template records. |
| `pio_template_versions` | Version records for PIO templates. |
| `pio_distribution_log` | Distribution log records for messages/releases. |
| `pio_generated_documents` | Generated PIO document metadata and references. |

## Liaison

| Collection | Purpose |
|---|---|
| `liaison_agencies` | External agency/partner records for liaison tracking. |
| `liaison_contacts` | Contacts associated with liaison agencies or partner organizations. |
| `liaison_interactions` | Interaction/contact log entries for liaison activity. |
| `liaison_agency_requests` | Requests from or to external agencies. |
| `liaison_resource_offers` | Resource offers from external agencies or partners. |
| `liaison_feedback` | Feedback records related to agency coordination. |
| `liaison_followup_actions` | Follow-up task/action records for liaison work. |
| `liaison_restrictions` | Restrictions, limitations, or special conditions associated with partner agencies/resources. |
| `liaison_agreements` | Agreement/MOU/coordination records for liaison partners. |

## Intel

| Collection | Purpose |
|---|---|
| `intel_subjects` | Canonical all-hazards intel subject records, such as missing persons, witnesses, reporting parties, or other human subjects. |
| `intel_leads` | Unverified tips, leads, and reports requiring triage or investigation. |
| `intel_items` | Verified intel items with embedded observations and links to subjects/tasks. |
| `intel_assessments` | Finished analytical products or assessments. |
| `intel_log` | Chronological intel activity log, similar in role to an ICS-214 stream for intel work. |
| `intel_reports` | Frozen/saved intel report snapshots. |

## GIS

| Collection | Purpose |
|---|---|
| `spatial_features` | Incident GIS feature records, such as mapped points, lines, polygons, search areas, or operational overlays. |
| `spatial_feature_links` | Links between GIS features and incident entities such as tasks, hazards, facilities, subjects, or work assignments. |

## Initial Response

| Collection | Purpose |
|---|---|
| `initial_response_overview` | Initial response overview and early incident planning record. |
| `initial_hasty_tasks` | Hasty task records created during initial response planning. |
| `initial_reflex_actions` | Reflex action checklist/status records for initial response. |

## Planned Event Toolkit

| Collection | Purpose |
|---|---|
| `planned_campaigns` | Planned event campaign records. |
| `planned_event_schedules` | Planned event schedule records. |
| `planned_vendors` | Planned event vendor records. |
| `planned_permits` | Planned event permit records. |
| `planned_safety_reports` | Planned event safety report records. |
| `planned_tasks` | Planned event task records. |
| `planned_quick_assignments` | Planned event quick assignment records. |
| `planned_health_inspections` | Planned event health inspection records. |
| `planned_schedule_triggers` | Planned schedule trigger records for event automation/workflows. |
| `planned_notifications` | Planned event notification records. |

## Approvals, Audit, Status Boards, And Supporting Data

| Collection | Purpose |
|---|---|
| `approval_instances` | Generic approval workflow instance per approvable entity. |
| `approval_records` | Append-only approval action/audit trail records. |
| `audit_logs` | Incident-scoped audit log records for user/system changes. |
| `status_board_snapshots` | Saved status board snapshots. |
| `weather_data` | Incident weather configuration/data, including presets and location-code data. |

## Finance/Admin

| Collection | Purpose |
|---|---|
| `finance_fuel_price_profiles` | Incident fuel price profile records. |
| `finance_forecasts` | Finance forecast records. |
| `finance_fuel_forecast_lines` | Fuel forecast line-item records. |
| `finance_funding_sources` | Incident funding source records. |
| `finance_expenses` | Expense/procurement records. |
| `finance_approvals` | Finance-specific approval records, intentionally separate from generic approvals per current schema notes. |
| `finance_attachments` | Finance attachment metadata and file references. |

## SITREP

| Collection | Purpose |
|---|---|
| `sitreps` | Situation report records. |
| `sitrep_events` | Significant events or reportable facts associated with SITREPs. |
| `sitrep_distributions` | Distribution records for SITREPs. |
