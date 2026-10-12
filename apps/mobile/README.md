📦 Arc-Horizon Mobile App – Full Release Phase Plan

## Platform Priority

- **Android** — primary target, actively developed and testable locally.
- **Web** — secondary target, already buildable via the Flutter web toolchain.
- **iOS** — deprioritized indefinitely. Building/signing an iOS app requires a
  macOS + Xcode environment, which is not currently available. Revisit only if
  a Mac or cloud-Mac CI path (e.g. Codemagic, MacStadium) becomes available.

## Basic SARApp Cloud MVP

The current app scaffold supports a basic cloud-connected flow:

- Connect to a SARApp FastAPI server
- Verify server health
- Fetch active incidents
- Store a responder profile on the device
- Submit a personnel check-in record for an incident, including profile, vehicle, and equipment details

The MVP currently hardcodes the SARApp cloud server address used by the SARApp desktop repo:

```text
http://srv1707346.hstgr.cloud:8765
```

Expected API shape:

- `GET /health`
- `GET /api/incidents`
- `PUT /api/incidents/:incidentId/checkin/:personId`

The current SARApp cloud server does not expose a mobile auth/token endpoint yet,
so the MVP uses a successful health check as its connection/session gate.

Backlog note: add a production login splash/connect screen that prompts field
users for the SARApp connect code before continuing to health check, incident
selection, or saved-session restoration.

Responder profiles are stored locally on the mobile device using `shared_preferences`.
During check-in, the app sends a `mobile_profile_snapshot` plus vehicle and
equipment arrays into the incident check-in document.

Phase	Title	Summary
Phase 1	Initial Access & Status Updates	Login, incident selection, role/team check-in, basic status advancement
Phase 2	Tasking, Logs & Comms Plan Access	Active911-style tasking, ICS 214 logging, ICS 205/206 viewing
Phase 3	Offline Mode, Sync & Location Sharing	Offline support, GPS sync, team status view, push notifications
Phase 3.5	Field Tools & SAR Enhancements	SAR search tools, clue markers, hazard reports, nav tools, QR scanning
Phase 4	Command Visibility Tools	Command map dashboard, live task board, personnel view, messaging
Phase 5	Forms & Incident Documentation	Fillable ICS/custom forms, broadcast alerts, AARs, reference viewer
Phase 6	Analytics, Auditing, Exports, Interop API	Dashboards, logs, incident export/archive, role controls, CAD/EOC API
Phase 7	Inter-Agency Coordination	Multi-agency incidents, shared feeds, secure messaging, role mapping
Phase 8	AI Assistance & Smart Automation	Auto-fill for forms, predictive routing, task alerts, AI help assistant
