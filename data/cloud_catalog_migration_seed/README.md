# Cloud catalog migration seed

Real data exported from this installation's local catalog (`sarapp_master`)
on 2026-10-07, via `scripts/export_master_catalog_seed_csvs.py`. Use these
to seed the central catalog (`sarapp_central_master`, inside `cloud_router`)
once it's created — this is this installation's actual roster/equipment/etc.,
not generic defaults.

Do not confuse this with `data/master_catalog_seed/` — that directory holds
generic starter templates for a brand-new agency with no data yet (e.g.
"Fire Department (Standard)" rank structures). This directory is this one
installation's real data for migration, kept separate so neither ever
overwrites the other.

Regenerate at any time with:

```
python scripts/export_master_catalog_seed_csvs.py
```

## Curated files (match an existing import/export column format)

These eight already round-trip through either the dashboard's own CSV
import (`cloud_router/master_db/webgui.py`) or the same column convention
`data/master_catalog_seed/`'s templates use:

- `personnel.csv`, `equipment.csv` — exact columns the dashboard's
  Personnel/Equipment CSV import already expects.
- `vehicles.csv`, `aircraft.csv` — columns match each collection's create
  request body (`VehicleBody`/`AircraftBody`); no dashboard import exists
  for these yet, so this is the data, format-ready for whenever one is built.
- `organization_types.csv`, `rank_structures.csv`, `ranks.csv`,
  `organizations.csv` — same human-readable headers as the generic seed
  templates, but this installation's real rows.

## Generic raw-dump files (no established format yet)

Every other non-empty master collection, one column per field actually
present across that collection's documents. Nested/list values (e.g.
`resource_types.components`, `fema_mappings`) are JSON-encoded into the
cell rather than dropped, so nothing is lost even though it isn't
flattened prettily — a future import feature can parse the JSON back out.
Purely local sequential ids (`int_id`, any `*_record`/`*_record_master`
field) are dropped; a fresh central catalog mints its own.

`agency_directory.csv`, `certification_tags.csv`, `certification_types.csv`,
`form_families.csv`, `form_templates.csv`, `form_template_versions.csv`,
`gar_templates.csv`, `hospitals.csv`, `meeting_templates.csv`,
`nearby_facility_exclusions.csv`, `radio_channels.csv`,
`resource_capabilities.csv`, `resource_types.csv`, `task_types.csv`,
`team_types.csv`.

**One caveat worth reading before importing `hospital_directory.csv`:**
per its own collection comment in `collection_names.py`, this is "cached
CMS emergency-department hospitals with coordinates" — a refreshable
external cache (ICS-206 "Find Nearby"), not agency-authored catalog data.
Seeding central with today's stale local copy works, but it'll drift from
CMS immediately; central's own refresh job (if/when one exists) should
probably take over rather than relying on this file being kept current by
hand.

## Not exported (by design)

- `users`, `user_sessions`, `client_connections`, `push_tokens` — local-
  catalog-only session/device state, never agency catalog data.
- `organization_audit_log`, `rank_structure_audit_log` — historical change
  logs; a fresh central catalog shouldn't inherit another server's audit
  trail.
- `personnel_certifications` — legacy, empty on a cut-over install (see
  `Design Documents/legacycode.md`).
- Collections that were empty on this server at export time: `hazard_types`,
  `canned_comm_entries`, `ems_agencies`, `safety_analysis_templates`,
  `organization_rank_structure_overrides`.
