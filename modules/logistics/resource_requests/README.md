# Logistics Resource Requests Module

This package implements the Logistics 4-1 Resource Request workflow for the SARApp / ICS Command Assistant desktop application.  The implementation is QtWidgets-only and stores incident data in SQLite databases found under `data/incidents/<incident_id>.db`.

## Features

- Full lifecycle management covering `DRAFT → SUBMITTED → REVIEWED → APPROVED → ASSIGNED → INTRANSIT → DELIVERED → CLOSED` with handling for `DENIED`, `CANCELLED`, and partial fulfilments.
- SQLite migrations (`data/migrations/0001_init.sql`) establishing all required tables plus indexes.
- Service layer (`api/service.py`) implementing CRUD operations, validations, audit logging, versioning, and fulfilment management.
- PDF generation helpers (`api/printers.py`) that export ICS-213 RR and summary sheets with optional training watermarks and QR codes.
- QtWidgets panels and widgets for list/detail views, approvals, fulfilment tracking, and audit history.
- Demo seed script (`data/seed_demo.py`) that populates the master supplier list and creates a training incident with example requests.

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Ensure an incident is active before instantiating the service.  The module
   reads the incident number from :class:`utils.state.AppState` when no explicit
   identifier is provided.
   ```python
   from modules.logistics.resource_requests import get_service
   from utils.state import AppState

   AppState.set_active_incident("SAR-EXAMPLE")
   service = get_service()
   ```
3. Populate demo data for exploration:
   ```bash
   python -m modules.logistics.resource_requests.data.seed_demo
   ```
4. Launch the desktop application.  The Logistics → Resource Requests menu will display the new list/detail panels.

## Tests

Run the module test suite with:

```bash
pytest modules/logistics/resource_requests/tests
```

The tests cover model round-trips, lifecycle validation, fulfilment flow, PDF rendering stubs, and QtWidgets sanity checks.

## PDF Output

Generated PDFs are written to `data/output/` by default.  The paths are returned by the printer helper functions for integration with higher level workflows.

## Future Enhancements

- Cost tracking across requests and fulfilments for integration with Finance.
- Inventory reservation tools to coordinate with Logistics caches and Operations tasking.
