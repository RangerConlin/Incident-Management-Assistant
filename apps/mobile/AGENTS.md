# Agent Instructions

This repository is the Flutter mobile client for ICS Command Assistant / SARApp field operations. Treat this file as the first stop for coding agents working in the repo.

## Project Snapshot

- App: Flutter mobile app in Dart.
- Package: `ics_mobile_app`.
- Primary target: Android.
- Secondary target: Web.
- iOS: deprioritized until a macOS/Xcode or cloud-Mac path exists.
- Backend: SARApp cloud/router API documented in `Current Mobile API Contract.txt`.
- Entry point: `lib/main.dart`.

## Repository Map

- `lib/config/`: environment and server URL construction.
- `lib/models/`: JSON parsing and domain models.
- `lib/services/`: API client and local session persistence.
- `lib/screens/`: route-level UI flows.
- `lib/widgets/`: reusable presentation widgets.
- `lib/theme/`: Material theme, status color vocabulary, and field UI constants.
- `lib/utils/`: formatting and parsing helpers.
- `test/`: widget and model tests using `flutter_test`.
- `docs/ai-agent-workflows.md`: tracked handoff guide for specialized agent workflows.
- `.agents/`: ignored local agent/tooling notes and clones.

## Current Product Behavior

- The app starts at `LoginScreen`.
- On startup it checks server health, loads any saved session from `shared_preferences`, then routes to `FieldDashboardScreen` when possible.
- Login mirrors the SARApp desktop convention: username is the operator/person id. The current mobile UI requires username and password to match because the server does not validate a real mobile password yet.
- Session data is persisted through `SessionStore`.
- The field dashboard is team-centric: current task, task narrative, team status, and compact field actions.
- Team status labels and colors should stay aligned with the SARApp desktop vocabulary in `lib/theme/app_theme.dart`.

## Backend/API Rules

- Use `Current Mobile API Contract.txt` as the local source of truth before adding or changing endpoints.
- Do not call planned mobile endpoints unless matching server routers exist. In particular, do not assume these are live:
  - `POST /api/mobile/login`
  - `POST /api/mobile/checkin`
  - `POST /api/mobile/sync`
  - `POST /api/mobile/location`
  - `POST /api/mobile/push-token`
  - `GET /api/mobile/permissions`
- The current cloud base URL is assembled in `AppConfig.sarAppBaseUrl` from the SARApp router base URL and connect code. Keep that routing model unless the server contract changes.
- The operations team `int_id` is the id used by status/task endpoints. The check-in `team_id` is a different value.
- Prefer extending `SarAppApiClient` with small typed methods instead of scattering raw HTTP calls across screens.

## Coding Conventions

- Follow the existing Flutter/Dart style and `flutter_lints`.
- Keep UI code Material 3 and dark-theme friendly. This app is an operational field tool, so prefer dense, legible, low-glare layouts over marketing-style screens.
- Keep phone-width behavior first-class. Existing tests check that wide-only panels do not appear on phone layouts.
- Preserve honest empty/error states. Do not fabricate tasks, narratives, incidents, or team records when the server returns none.
- Inject `SarAppApiClient` into screens/widgets that perform network work so tests can use `MockClient`.
- Dispose owned controllers and API clients. If a client is injected, do not dispose it unless ownership is explicit.
- Put parsing normalization in models or `lib/utils/`, not inside widget build methods.
- Use clear comments only where they document non-obvious server behavior or field-ops constraints.

## Testing And Validation

Run these from the repository root when Flutter is available:

```powershell
flutter pub get
flutter analyze
flutter test
```

For targeted work:

```powershell
flutter test test/models
flutter test test/widgets
flutter test test/screens/field_dashboard_screen_test.dart
```

Test guidance:

- Use `package:http/testing.dart` `MockClient` for API tests.
- Use `SharedPreferences.setMockInitialValues({})` when a widget startup path touches local session state.
- Add or update tests for changed parsing, endpoint behavior, empty states, and responsive layout rules.
- If a change affects the visual hierarchy of the field dashboard, test phone and wide constraints.

## Design Documents

Phase plans are stored as `Phase N Design Document.txt` files. They are useful planning context, but the API contract and current Dart implementation win when there is a conflict.

## Working Tree Safety

- Expect the worktree to contain user changes. Do not revert unrelated modifications.
- Keep changes scoped. This repo is small enough that broad refactors are easy to overdo.
- Before changing server-facing behavior, update or verify `Current Mobile API Contract.txt`.

## Agent Handoff Notes

- If backend behavior is unclear, inspect `docs/ai-agent-workflows.md` for the API-contract and server-context checklist.
- `.agents/` is ignored by Git. Use it for local notes or cloned helper worktrees, not as the only place for durable project instructions.
- Summarize endpoint changes in plain language when handing work back to a human.
- Mention any Flutter commands that could not be run locally.
- **Organization picker out of sync with desktop (found 2026-10-07):** `lib/models/organizations.dart`
  (`Organizations.bundled`) hardcodes the full CAP Great Lakes Region roster (MI/IL/IN/KY/OH/WI wings +
  squadrons) plus a handful of state-agency/civilian entries as the profile screen's offline-first fallback.
  Its docstring claims this mirrors an authoritative `Incident-Management-Assistant/data/db/sarapp_db/org_catalog.py`,
  but that file was never actually created in the desktop repo — the desktop app has no equivalent seeded
  organization list, and the central master catalog's `organizations` collection starts empty. A CSV derived
  from this Dart list now exists at `Incident-Management-Assistant/data/master_catalog_seed/organizations_glr_seed.csv`
  for uploading to the central catalog via its web GUI, but until someone uploads it and both apps are pointed
  at the synced catalog, this list and whatever desktop ends up with can drift apart again. See the matching
  backlog entry under `[Tech Debt / Infrastructure]` in the desktop repo's `backlog.md` for the open decisions
  (whether `org_catalog.py` gets created as a real shared source, or this bundled list becomes the one
  hand-maintained copy with desktop reading from the synced catalog only).
