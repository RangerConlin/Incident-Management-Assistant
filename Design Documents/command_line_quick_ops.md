# Embedded Command Line Quick Operations Design

## Purpose

Design an in-program command line for Incident Management Assistant that lets an operator quickly perform common actions by typing short command codes.

This is not an external terminal CLI. It is a command entry surface built into the desktop application, intended for fast operational work such as:

- Creating a task.
- Creating a team.
- Assigning a team to a task.
- Changing team, resource, or task status.
- Adding short notes or log entries.
- Jumping to records or panels.

The feature should feel like a compact operator console: always available, fast to type into, forgiving enough to guide the user, and strict enough to avoid accidental writes.

## Working Names

- Command Line
- Quick Command
- Operator Command Bar
- Command Console

Examples in this document use "Command Line" for the UI and "quick command" for a typed instruction.

## Goals

- Let experienced users operate common workflows without navigating multiple panels.
- Support short coded commands for repeatable field operations.
- Provide previews and confirmations for write actions.
- Execute actions through the existing application/API architecture.
- Keep commands incident-scoped.
- Make commands discoverable with inline help and autocomplete.
- Preserve canonical domain language: use "incident", never "mission".

## Non-Goals

- Do not build an external shell command.
- Do not bypass the API layer.
- Do not wire MongoDB directly into UI code.
- Do not create fake/demo records.
- Do not invent legacy aliases or fallback data shapes.
- Do not make the command line the only way to perform these actions.

## User Experience

The command line should be available from the main desktop UI, likely as one or more of:

- A bottom command bar.
- A dockable command console.
- A global shortcut that opens a command overlay.

Recommended shortcut:

```text
Ctrl+K
```

The input should support:

- Autocomplete for command codes.
- Entity lookup by name, short code, or ID.
- Validation while typing.
- A preview of the action before execution.
- Keyboard-only operation.
- Recent command history.
- A help command.

Example interaction:

```text
> team.new Alpha search

Preview:
Create team "Alpha" with type "search" in current incident.

Enter to run, Esc to cancel.
```

## Command Code Style

Use short dotted command codes:

```text
entity.action arguments
```

Examples:

```text
team.new Alpha search
task.new "Check north trail" priority=high
team.status Alpha deployed
task.status T-104 complete
assign Alpha T-104
note "Command post established at main lot"
open tasks
```

The dotted form keeps related commands grouped and easy to autocomplete.

Common command families:

```text
team.*
task.*
resource.*
incident.*
note.*
open.*
assign
help
```

## Initial Command Set

### `help`

Show available commands, syntax, and examples.

Examples:

```text
help
help team
help task.status
```

### `team.new`

Create a team in the active incident.

Examples:

```text
team.new Alpha
team.new Alpha search
team.new "Team Alpha" type=search status=available
```

Expected behavior:

- Require an active incident.
- Resolve team type/status through canonical allowed values.
- Preview before creation.
- Return the created team name/code.

### `team.status`

Change a team's status.

Examples:

```text
team.status Alpha available
team.status Alpha deployed
team.status "Team Alpha" out-of-service
```

Expected behavior:

- Resolve the team by ID, short code, or unique name.
- Reject ambiguous names and show matching options.
- Use canonical status values from the app.
- Update through the API, not direct persistence.

### `task.new`

Create a task in the active incident.

Examples:

```text
task.new "Search north trail"
task.new "Evacuate campground" priority=high
task.new "Check bridge" location="River Road" priority=normal
```

Expected behavior:

- Require an active incident.
- Support quoted task names.
- Support optional key/value fields.
- Use API defaults for fields the user does not provide.

### `task.status`

Change a task's status.

Examples:

```text
task.status T-104 in-progress
task.status "Search north trail" complete
```

Expected behavior:

- Resolve task by ID, task number, short code, or unique title.
- Reject ambiguous titles.
- Use canonical task status values.

### `assign`

Assign a team or resource to a task.

Examples:

```text
assign Alpha T-104
assign team=Alpha task=T-104
assign resource=Medic-2 task="Medical standby"
```

Expected behavior:

- Resolve both sides before preview.
- Show exactly what will be assigned.
- Use the existing assignment API/service path.

### `note`

Add a quick note/log entry to the active incident.

Examples:

```text
note "Command post established."
note task=T-104 "Team Alpha reached trailhead."
note team=Alpha "Switching to radio channel 3."
```

Expected behavior:

- Require an active incident.
- Attach to incident by default.
- Optionally attach to task/team/resource if supported by existing APIs.

### `open`

Navigate to a panel or record.

Examples:

```text
open tasks
open teams
open task T-104
open team Alpha
```

Expected behavior:

- No database write.
- Use established panel factories and ADS docking behavior.
- If a record is specified, open the correct panel and select/focus that record where possible.

## Parsing Rules

The command parser should support:

- Dotted command code as the first token.
- Quoted strings for names and notes.
- Positional arguments for fast common cases.
- `key=value` arguments for explicit fields.
- Case-insensitive command codes.
- Case-insensitive status/type matching where domain values allow it.

Examples:

```text
team.new Alpha search
team.new name=Alpha type=search
task.new "Search north trail" priority=high
```

Invalid commands should produce helpful errors:

```text
Unknown status "busy".
Did you mean one of: available, deployed, out-of-service?
```

## Execution Model

The command line is UI, but it should not contain persistence logic.

```text
Command Line widget
  -> Command parser
  -> Command resolver/validator
  -> Preview model
  -> Existing API client / service layer
  -> FastAPI router
  -> Repository
  -> MongoDB
```

Rules:

- UI command code must not call MongoDB directly.
- Writes must go through existing API/server paths.
- If an API endpoint does not exist for a command, add the API/repository path first.
- Keep cloud router changes out of scope unless command behavior specifically involves reverse-tunnel routing.

## Preview And Confirmation

Write commands should produce a preview before execution unless the command is explicitly designed as low-risk and reversible.

Preview should show:

- Action.
- Target incident.
- Records to create/update.
- Old value and new value for status changes.
- Ambiguity warnings.

Example:

```text
Change team status
Team: Alpha
Current status: Available
New status: Deployed
Incident: County Fair 2026
```

Possible confirmation model:

- Press `Enter` once to preview.
- Press `Enter` again to execute.
- Press `Esc` to cancel.

Alternatively, show preview as the user types and execute on `Enter` when valid.

## Autocomplete

Autocomplete should cover:

- Command codes.
- Status values.
- Team names/codes.
- Task IDs/titles.
- Resource names/codes.
- Panel names for `open`.

Autocomplete sources should be incident-scoped where applicable.

## Error Handling

Common errors:

- No active incident.
- Unknown command.
- Missing required argument.
- Unknown status/type.
- Ambiguous team/task/resource name.
- API unavailable.
- Validation failure from API/domain layer.

Errors should be short and actionable. Avoid stack traces in the UI.

## Audit Trail

Commands that mutate incident data should be auditable through the same mechanisms used by normal UI edits.

The command line should record, where supported:

- Actor/operator.
- Timestamp trimmed to seconds for display.
- Original command text.
- Created/updated entity.
- Old and new values for updates.

## UI Placement Ideas

### Bottom Command Bar

A single-line input at the bottom of the main window with an expandable preview area.

Good for fast use and low visual footprint.

### Dockable Console

An ADS dock with command history, output, and help.

Good for power users and incident command staff who want persistent history.

### Overlay Command Palette

Opened with `Ctrl+K`, closes after execution.

Good for navigation and quick actions, but less useful for persistent operational logging.

Preferred first implementation: dockable console or bottom command bar, depending on existing main-window layout constraints.

## Implementation Notes

- Use PySide6 widgets only. Do not add QML.
- Keep parser logic separate from widgets so it can be unit tested.
- Keep command definitions declarative where practical.
- Use existing styles and theme accessors; do not hardcode colors.
- If the command output uses tables, follow table design requirements.
- User-facing timestamps should not display sub-second precision.
- Use existing `utils/api_client.py` or a thin service wrapper that follows app patterns.

Potential structure:

```text
modules/
  command_line/
    __init__.py
    command_bar.py
    parser.py
    registry.py
    resolver.py
    preview.py
    executor.py
    history.py
    tests/
      test_parser.py
      test_registry.py
      test_resolver.py
```

Final placement should follow nearby module/UI conventions discovered during implementation.

## Open Questions

- Should commands execute immediately or always require a preview confirmation?
- What are the canonical team, task, and resource status values?
- Which module currently owns task creation and assignment APIs?
- Should command history persist per incident, per user, or only per session?
- Should the original typed command be stored in the incident log for write actions?
- Should there be administrator-only commands later?

## Phased Plan

### Phase 1: Parser And Read-Only Navigation

- Build parser and command registry.
- Add `help`.
- Add `open` commands for existing panels.
- Add tests for command parsing.

### Phase 2: Status Updates

- Add resolver support for teams and tasks.
- Add `team.status`.
- Add `task.status`.
- Add preview/confirmation.
- Add mocked API tests.

### Phase 3: Creation Commands

- Add `team.new`.
- Add `task.new`.
- Add field validation and autocomplete.

### Phase 4: Assignment And Notes

- Add `assign`.
- Add `note`.
- Add audit/history integration if available.

### Phase 5: Polish

- Add richer autocomplete.
- Add command history search.
- Add inline examples.
- Add permission-aware command availability.
