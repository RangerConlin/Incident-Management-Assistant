# Design Docs

Index and quick navigation for all Design Documents.

## Usage

```
/design-docs
/design-docs --search=database
/design-docs --topic=architecture
/design-docs --open tabledesign.md
```

## Core Documents

**Architecture & System Design**
- `database_architecture.md` — MongoDB setup, incident context, connection patterns
- `ui_desktop_patterns.md` — PySide6 patterns, ADS docks, widget lifecycle
- `realtime_architecture_roadmap.md` — Planned WebSocket, IncidentCache, offline sync
- `product_structure.md` — Module inventory, code organization, product roadmap

**Data & Schemas**
- `mongodb_schema_decisions.md` — Collection schemas, field definitions, indexes
- `mongo_cutover_status.md` — Migration status, what's done/pending
- `text_encoding_hygiene.md` — UTF-8, character handling, international text

**Development Standards**
- `python_coding_standards.md` — PEP 8, type hints, naming, logging
- `api_router_rules.md` — FastAPI patterns, mirroring requirements, request/response
- `testing_and_qa.md` — pytest setup, QT_QPA_PLATFORM, test isolation
- `tabledesign.md` — Table UI standards, resizable columns, selection borders

**Product & Planning**
- `designplan.md` — Master product roadmap, features, timeline

## Search by Topic

| Topic | Document |
|-------|----------|
| Database | `database_architecture.md`, `mongodb_schema_decisions.md` |
| API | `api_router_rules.md`, `database_architecture.md` |
| UI | `ui_desktop_patterns.md`, `tabledesign.md` |
| Testing | `testing_and_qa.md`, `python_coding_standards.md` |
| Migration | `mongo_cutover_status.md`, `mongodb_schema_decisions.md` |
| Real-time | `realtime_architecture_roadmap.md` |

## Common References

**"How do I create a table?"**
→ See `tabledesign.md` for standards, examples

**"How do I set up MongoDB?"**
→ See `database_architecture.md` for connection patterns

**"What collections exist?"**
→ See `mongodb_schema_decisions.md` for all schemas

**"How do I write an API endpoint?"**
→ See `api_router_rules.md` for patterns and mirroring

**"What's the status of SQLite→MongoDB?"**
→ See `mongo_cutover_status.md` for completed/pending

**"Should I commit this file?"**
→ See `agents.md` for hard rules (this file is the entry point)

## Document Location

All in `Design Documents/Instructions/`

Quick access:
```
ls Design\ Documents/Instructions/
cat Design\ Documents/Instructions/tabledesign.md
```

## Related Skills

- `/repo-rules` — Quick reference of hard rules
- `/new-router` — See api_router_rules.md for patterns
- `/new-ui-panel` — See tabledesign.md and ui_desktop_patterns.md
- `/migration-checklist` — See mongo_cutover_status.md, mongodb_schema_decisions.md

## Keeping Docs Fresh

When architecture or patterns change:
1. Update the relevant `Design Documents/Instructions/` file
2. Update `agents.md` if it's a hard rule
3. Agents will see the changes immediately
