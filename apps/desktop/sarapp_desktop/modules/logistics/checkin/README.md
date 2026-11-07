# Check-In Module

This module provides a minimal offline-first check-in workflow for
SARApp / ICS Command Assistant.  It follows the design document's
structure with a clean separation between models, repository, service
API, and a QML based user interface.

## Usage

* Persistent data is stored in `data/master.db`.
* Each incident has its own database under `data/incidents/<id>.db`.
* Activate an incident via `utils.incident_context.set_active_incident("INCIDENT_ID")`.
* Interact with the repository or API modules to lookup or check-in
  personnel and assets.  The `checkin_bridge` exposes these services to
  QML.

## Tests

Run the unit tests with:

```bash
pytest tests/test_checkin_repository.py tests/test_checkin_api.py
```

The tests create temporary databases and therefore do not interfere
with existing data files.

## Notes

The database schemas are placeholders and will be expanded in future
iterations.  Additional validation and error handling should be added
as the application evolves.

## QR check-in

Quick Check In still accepts the legacy identity-only QR format
`SARAPP:CHECKIN:v1:<person_id>`. The mobile app now generates a versioned
`SARAPP:PROFILE:v2:` payload carrying its canonical personnel identity fields.
Staff-side decoding, review, and check-in of that richer payload is the next
check-in-flow integration; do not treat the legacy parser as a decoder for the
new profile format.
