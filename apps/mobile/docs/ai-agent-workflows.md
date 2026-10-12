# AI Agent Workflows

This guide expands the root `AGENTS.md` instructions with role-specific workflows for agents working on the mobile app.

## Mobile App Agent

Primary scope:

- `lib/`
- `test/`
- `pubspec.yaml`
- `analysis_options.yaml`

Workflow:

1. Read `AGENTS.md`, `Current Mobile API Contract.txt`, and the relevant Dart files before editing.
2. Keep network access inside `SarAppApiClient`.
3. Keep JSON normalization in models or utility functions.
4. Keep screens focused on orchestration and state.
5. Add or update widget/model tests for changed behavior.
6. Run `flutter analyze` and the smallest meaningful `flutter test` target available.

Watch for:

- phone-width layouts that accidentally pick up wide-only UI
- fabricated mock data in production widgets
- missing empty/error states
- disposing injected API clients that the caller owns
- endpoint ids mixing check-in `team_id` and operations `int_id`

## API Contract Agent

Primary scope:

- `Current Mobile API Contract.txt`
- `lib/config/app_config.dart`
- `lib/services/sarapp_api_client.dart`
- models that parse endpoint responses

Workflow:

1. Confirm whether an endpoint is documented as current or planned.
2. Verify the expected path after `AppConfig.sarAppBaseUrl`.
3. Capture the response shape: object, list, or object with `items`.
4. Update `SarAppApiClient` with a small method that returns decoded JSON.
5. Add parsing or widget tests using `MockClient`.
6. Document server-facing assumptions in comments only when they are non-obvious.

Do not use planned mobile endpoints until server routes are confirmed live:

- `POST /api/mobile/login`
- `POST /api/mobile/checkin`
- `POST /api/mobile/sync`
- `POST /api/mobile/location`
- `POST /api/mobile/push-token`
- `GET /api/mobile/permissions`

## UX/Test Agent

Primary scope:

- `lib/screens/`
- `lib/widgets/`
- `lib/theme/`
- `test/screens/`
- `test/widgets/`

Workflow:

1. Preserve the operational field-tool feel: dark, compact, readable, and action-oriented.
2. Test key responsive differences with explicit `tester.view.physicalSize`.
3. Prefer semantic widget tests over brittle full-screen snapshots.
4. Check loading, empty, error, and success states.
5. Keep app vocabulary aligned with SARApp and ICS terms. Use "incident", not "mission", for API and UI contract language.

## Local Agent Notes

The `.agents/` directory is ignored by Git and may contain local helper worktrees or scratch notes. If a local note becomes important for future contributors, move the durable part into this `docs/` file or `AGENTS.md`.
