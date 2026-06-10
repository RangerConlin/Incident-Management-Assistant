# Incident storage refactor (developer note)

## Legacy layout
- Old incident storage mixed flat SQLite files (`<data_root>/incidents/<incident>.db`) with ad-hoc module subfolders.

## New layout
- Incident data is folder-scoped:
  - `<data_root>/master.db`
  - `<data_root>/incidents/<incident_folder>/incident.db`
  - `<data_root>/incidents/<incident_folder>/spatial.db`
  - `<data_root>/incidents/<incident_folder>/incident.json`
  - Standard subfolders for forms/files/reports/exports/logs/temp.

## Centralized path rules
- Use `utils.incident_storage` for all incident-rooted paths.
- Use `utils.incident_context` for active incident DB/spatial path resolution.
- Modules should not manually join `data/incidents` or `*.db` names.

## Migration behavior
- On storage initialization, `utils.incident_storage.migrate_legacy_incident_databases()` scans legacy flat DB files under `<data_root>/incidents/*.db` and moves each into a folder as `incident.db`.
- Migration also creates `spatial.db`, writes `incident.json`, and creates required subfolders.

## Operational DB vs spatial DB
- Operational/business tables remain in `incident.db`.
- Spatial schema is bootstrapped into `spatial.db` during incident DB ensure/create.
- Transitional code can still read operational data independently while spatial callers use dedicated sibling pathing.

## Incident-scoped files
- Forms: `forms/generated`, `forms/exports`, `forms/uploads`, `forms/drafts`
- Files: `files/attachments`, `files/media`, `files/imports`, `files/reference_docs`
- Outputs: `reports`, `exports`, plus `logs` and `temp`.
