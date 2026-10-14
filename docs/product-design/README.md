# Product Design And Build-State Documents

These documents describe the product as it exists today so we can understand the feature set, build status, module boundaries, UI state, and unfinished work before designing the next version.

They are not sales copy, API documentation, schema documentation, or deep implementation notes. They should be practical design records: enough detail to decide what to keep, fix, redesign, standardize, or remove.

## Goals

- Record what each module can do right now.
- Capture build status: working, partial, rough, broken, legacy, or planned.
- Identify unfinished work and design gaps without losing them in code comments.
- Make intermodule feature relationships visible.
- Separate desktop behavior from mobile behavior where they differ.
- Create a practical base for redesigning features and standardizing UI.

## Document Map

- [Product Overview](overview.md)
- [Desktop Experience](desktop-experience.md)
- [Mobile Experience](mobile-experience.md)
- [Module Template](module-template.md)
- [UI Standardization](ui-standardization.md)
- [Module Index](modules/README.md)

## Writing Style

Write for ourselves as product builders. Prefer direct, concrete notes over polished language:

- Use "incident", not "mission".
- Describe what exists before describing what should exist.
- Be clear about build status and confidence level.
- Name rough edges, dead ends, duplicated workflows, and confusing UI.
- Describe screens and controls as they exist today.
- Keep future ideas separate from current-state notes.
- Avoid endpoint names, database collections, internal class names, and implementation details unless they are necessary to explain a customer-visible limitation.
