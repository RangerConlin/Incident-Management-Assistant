# Mongo Cutover Status

Snapshot date: 2026-06-27

This file tracks the current migration snapshot. Treat it as reference material, not timeless policy. Re-run the checks before relying on it for new work.

## Two Separate Migration Axes
- **Axis 1**: client-side SQLite file -> HTTP API. This asks whether the UI module stopped opening a local `.db` file and switched to an `Api*Repository` that calls `utils/api_client.py`.
- **Axis 2**: server-side raw PyMongo -> `BaseRepository`. This asks whether the FastAPI router stopped writing through a raw collection and now uses a `BaseRepository` subclass for timestamping and change broadcast behavior.
- A module can be complete on one axis and incomplete on the other. Do not infer one from the other.

## Axis 1 Status

| Module | Submodule | Status |
|---|---|---|
| `modules/admin` | `hazard_types` | Done |
| `modules/admin` | `resource_types` | Done |
| `modules/command` | `incident_organization` | Done |
| `modules/command` | (rest of module) | Done |
| `modules/common` | - | Done |
| `modules/communications` | `traffic_log` | Done |
| `modules/communications` | (rest of module) | Done |
| `modules/facilities` | - | Done |
| `modules/statusboards` | - | Done |
| `modules/personnel` | `units_organizations` | Done |
| `modules/personnel` | (rest of module) | Done |
| `modules/forms_creator` | - | Done |
| `modules/gis` | - | Done |
| `modules/logistics` | - | Done |
| `modules/operations` | - | Done |
| `modules/planning` | - | Done |
| `modules/finance` | - | Done |
| `modules/referencelibrary` | - | Done |

Every directory under `modules/` was swept with `sqlite|\\.execute\\(\\s*[\"']` across `.py` files, tests excluded, as of 2026-06-27. Modules not listed in the table had zero hits and were presumed clean at that time. No reliable "next in queue" ordering exists because multiple agents may work the repo concurrently.

## Axis 2 Status
- On `BaseRepository`: `hazard_types.py`, `incident_org.py`, `communications.py`, `objectives.py`, `operations.py`, `aircraft.py`, `approvals.py`, `canned_comm_entries.py`, `certifications.py`, `checkin.py`, `equipment.py`, `facilities.py`, `forms.py`, `finance.py`, `gis.py`, `hospitals.py`, `ic_overview.py`, `ics214.py`, `incident_resources.py`, `initialresponse.py`, `intel.py`, `liaison.py`, `logistics_resource_requests.py`, `logistics_resource_status.py`, `lookup_types.py`, `medical.py`, `meetings.py`, `organizations.py`, `safety.py`, `safety_templates.py`, `weather.py`
- Still on raw writes: `objective_templates.py`, `operational_periods.py`, `personnel.py`, `resource_types.py`, `strategy_templates.py`, `vehicles.py`, `work_assignments.py`, `auth_sessions.py`, `plannedtoolkit.py`, `public_information.py`, `reference_library.py`
- Not applicable (no writes): `geocoding.py`, `incident_stream.py`

Re-run before trusting. Example snapshot command:

```bash
cd data/db/sarapp_db/api/routers
for f in *.py; do grep -q "(BaseRepository)" "$f" && echo "BaseRepository: $f" || grep -qE "insert_one|update_one|delete_one" "$f" && echo "raw write: $f"; done
```
