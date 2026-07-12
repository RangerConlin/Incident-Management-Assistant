# Master Database Collection Inventory

This file lists the MongoDB collections that can currently be created inside
the shared master database named `sarapp_master`.

Source of truth for most names is `data/db/sarapp_db/mongo/collection_names.py`.
This inventory also includes live master collections referenced directly by
routers but not yet represented by a `MasterCollections` constant. It does not
describe `sarapp_system` or per-incident `sarapp_incident_<incident_id>`
collections.

## Canonical Notes

- Master data is agency-wide or application-wide reference/catalog data shared
  across incidents.
- The desktop UI must access master data through API/catalog-cache layers, not
  direct Mongo calls.
- `radio_channels` is the master communications catalog. Incident channel plans
  reference master channel records rather than copying frequency/tone identity.
- Reference Library currently uses direct collection names for
  `library_documents` and `library_collections`; these should eventually be
  represented in `MasterCollections` if they remain part of the product.

## Personnel, Certifications, And Organizations

| Collection | Purpose |
|---|---|
| `personnel` | Master personnel roster records. Stores agency-wide identity, person record IDs, names, roles/ranks, contact fields, qualifications/certifications, status, and other personnel metadata used across incidents. |
| `certification_types` | Certification/qualification type catalog records, such as credential names, categories, descriptions, and expiration rules. |
| `certification_tags` | Tags or labels used to organize certification and qualification types. |
| `personnel_certifications` | Separate personnel-certification link records where certifications are not embedded directly on personnel documents. |
| `organization_types` | Catalog of organization/unit types used for agencies, departments, teams, or partner entities. |
| `organizations` | Master organization, agency, unit, or partner records. Used for personnel affiliation, resource ownership, and forms/context. |
| `rank_structures` | Rank structure definitions for organizations or organization types. |
| `ranks` | Rank records associated with rank structures. |
| `organization_rank_structure_overrides` | Overrides that assign or customize rank structures for specific organizations. |
| `organization_audit_log` | Audit/change records for organization catalog changes. |
| `rank_structure_audit_log` | Audit/change records for rank structure and rank catalog changes. |

## Master Resources

| Collection | Purpose |
|---|---|
| `vehicles` | Master vehicle inventory records. Stores agency-wide vehicle IDs, record IDs, status/type references, ownership/organization fields, callsigns, and descriptive data. |
| `equipment` | Master equipment inventory records. Stores equipment IDs, record IDs, type/category data, ownership/agency fields, status, serial numbers, and descriptive data. |
| `aircraft` | Master aircraft inventory records. Stores aircraft record IDs, tail/callsign data, aircraft type, agency ownership, status, and related aviation metadata. |
| `resource_types` | Resource type catalog records used for typing teams, resources, requests, work assignments, and FEMA/NIMS-style resource descriptions. |
| `resource_capabilities` | Capability catalog records that can be attached to resource types. |
| `agency_directory` | Agency/partner directory records used as shared reference data across modules. |

## Communications

| Collection | Purpose |
|---|---|
| `radio_channels` | Master radio/channel catalog. Stores channel name, frequency, tone/NAC, system, mode, line flags, and notes. Incident channel plans reference these records by master ID. |
| `canned_comm_entries` | Reusable canned communications text entries or message snippets for quick entry workflows. |

## Safety And Hazards

| Collection | Purpose |
|---|---|
| `hazard_types` | Master hazard type library used by the Safety Risk Manager and hazard prefill workflows. |
| `safety_analysis_templates` | Reusable safety analysis templates, default hazard/control packages, or safety planning templates. |

## Medical Facilities And EMS

| Collection | Purpose |
|---|---|
| `hospitals` | Master hospital directory used by medical planning, ICS-206, and facility selection. |
| `ems_agencies` | Master EMS agency directory used by medical planning and ICS-206 ambulance/EMS references. |

## Incident And Planning Templates

| Collection | Purpose |
|---|---|
| `incident_types` | Master incident type lookup records. |
| `incident_templates` | Reusable incident templates for creating or initializing new incidents. |
| `meeting_templates` | Reusable meeting templates, agenda sections, prep checklists, and meeting defaults. |
| `task_types` | Master task type catalog used by operations/tasking workflows. |
| `team_types` | Master team type catalog used when creating or classifying incident teams. |
| `objective_templates` | Reusable objective templates used by planning/command objective workflows. |
| `strategy_templates` | Reusable strategy/work-assignment templates used by planning/tactics workflows. |

## Forms Catalog

| Collection | Purpose |
|---|---|
| `form_families` | Master form family records. A family usually represents an issuing agency or form set such as FEMA, CAP, SAR, ICS Canada, USCG, or Custom. |
| `form_templates` | Master form template records. A template represents one form within a family, such as an ICS 204. |
| `form_template_versions` | Version records for form templates, including layout, fields, bindings, validation, export profiles, effective dates, source asset references, and current-version state. |

## Reference Library

| Collection | Purpose |
|---|---|
| `library_documents` | Reference Library document records. Stores document title, category, tags, agency/jurisdiction, description, file path/hash/metadata, version, archived flag, and create/update metadata. |
| `library_collections` | Reference Library collection records. Stores named document groupings and the list of linked document IDs. |

## Users, Sessions, And Access

| Collection | Purpose |
|---|---|
| `users` | User/operator records. Stores user ID, username, display name, badge/person references, optional auth metadata, and update timestamps. |
| `user_sessions` | Active and historical user session/presence records. Stores session IDs, user/person references, status, incident context, device name, start/last-seen/end timestamps, and presence state. |
| `user_profiles` | User profile/preference records for desktop or operator-specific settings. |
| `role_templates` | Role/access template records for user roles, permissions, or future access-control presets. |

## Legacy Or Non-Canonical Master Collections Seen In Local Data

| Collection | Purpose |
|---|---|
| `teams` | Seen in local `sarapp_master` data but not represented by `MasterCollections`. Incident teams are currently incident-scoped in `sarapp_incident_<id>.teams`; this master collection should be treated as non-canonical until a live writer/reader is verified. |

