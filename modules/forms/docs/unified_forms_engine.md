# Unified Forms Engine

The unified forms engine keeps reusable template data in `master.db` and stores filled records in the active incident database. Forms snapshot values from operational modules; they do not own task, personnel, communications, medical, logistics, planning, intel, liaison, or finance data.

## Core concepts

- `FormFamily` identifies a shared form concept such as ICS-206 or SAR-104.
- `FormTemplate` describes an agency or system layout for a family.
- `FormTemplateVersion` is an immutable version snapshot.
- `FormInstance` is a filled record tied to one incident and one exact template version.
- `FormFieldDefinition` uses stable canonical keys.
- `FormFieldValue` records value, source, lock, and override metadata.
- `Binding` resolves dotted keys through provider namespaces.

## Local-first storage

The schema installer creates missing tables without deleting legacy or live data. Reusable families, templates, assets, exports, and template audit rows live in `master.db`. Filled instances, values, revisions, audit rows, exports, and links live in the per-incident database.

## Version rules

Creating a template creates version 1. Editing a template creates a new version and marks it current. Existing instances keep their original `template_version_id`, so later template edits cannot silently alter printed or exported records.

## Binding rules

Bindings are resolved through providers. Providers return safe missing results until module-specific integrations are connected. Refresh updates only unlocked, non-overridden fields.

## Export rules

The renderer loads the exact template version linked to the instance, applies stored values, and writes an export record with path and checksum. If a background asset is available, richer overlay renderers can use it. Without an asset, the engine falls back to a clean generated layout.

## Upload intake

Uploaded source documents create draft template shells with source asset metadata. Field mapping remains manual in this rebuild; automatic extraction is intentionally deferred.

## Legacy handling

Legacy form modules are left in place. Migration service reports what can be reviewed or moved and never destroys existing data.
