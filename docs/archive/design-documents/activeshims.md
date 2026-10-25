# Active Compatibility Shims

This file tracks legacy-compatibility code that is **confirmed still in active use** —
real callers depend on it today, so it cannot be deleted yet. It exists to make sure
these shims aren't forgotten: each one has a known reason it still exists and a known
condition that would let it go away.

This is different from `legacycode.md`, which tracks **unverified candidates** —
code suspected of being dead or no-longer-needed that hasn't been confirmed either way.
Once a candidate there is confirmed to still have live callers, its entry moves here
instead of staying on the candidate list (a candidate list should only ever contain
things still waiting on investigation, not things we've already confirmed are in use).

## Lifecycle of an entry

1. **Added** when a shim is created on purpose (e.g. a compatibility fallback added
   during a migration) or when a `legacycode.md` candidate is investigated and found
   to still have live callers.
2. **Updated** whenever a known caller is migrated off the shim — note what changed
   and what callers remain.
3. **Removed outright** once the last caller is migrated and the shim is deleted.
   Do not leave a struck-through "DELETED" stub here — git history already records
   what was removed and when; see the same rule in `legacycode.md`.

## Entry Template

```md
### Short Name
- Added: YYYY-MM-DD (when known; omit if inherited from legacycode.md without a date)
- Location: `path/to/file.py`
- Purpose: why this shim exists and what it does
- Known Callers: every current caller, by file
- Removal Condition: exact condition that must be true before deletion is safe (usually "every known caller migrated to <canonical path>")
- Verification: command/search to confirm callers remain or are gone
```

## Inventory

### Forms Creator legacy template registry and renderer
- Location: `modules/forms_creator/templating.py`, `modules/forms_creator/render.py`, `data/templates/registry.json`, `data/templates/**`
- Purpose: the old registry-plus-YAML rendering path used before the current `forms/sets/<set_id>/<form_id>/template.pdf` plus `mapping.json` pipeline.
- Known Callers: `modules/forms_creator/api.py` (`export_form_unified()`'s fallback branch imports `resolve_template` as `legacy_resolve` and `render_form` as `legacy_render`).
- Removal Condition: no runtime or developer tooling calls `modules.forms_creator.templating.resolve_template()` or `modules.forms_creator.render.render_form()` — in practice, every caller of `export_form_unified()` (see "Unified form export bridge" below) must migrate first — and all old `data/templates` entries have either been migrated into `forms/sets/**` or intentionally discarded.
- Verification: `rg -n "modules\.forms_creator\.(templating|render)|resolve_template|render_form|data/templates" modules data tests` — confirmed 2026-10-21 that `api.py` is still the only production caller.

### Devtools Template Debug panel
- Location: `modules/devtools/panels/template_debug_panel.py`, `modules/devtools/services/template_registry.py`, `modules/devtools/services/renderer_bridge.py`
- Purpose: developer-only UI and services for inspecting the old `data/templates/registry.json` template system.
- Known Callers: `modules/devtools/dev_menu.py` registers a live "Template Debug Panel" menu action that imports and instantiates `TemplateDebugPanel`.
- Removal Condition: the Developer menu no longer exposes Template Debug, or the panel is rewritten to inspect the canonical `forms/sets/**/mapping.json` registry instead.
- Verification: `rg -n "TemplateDebugPanel|template_debug_panel|Template Debug|template_registry|renderer_bridge" modules main.py` — confirmed 2026-10-21 the menu registration in `dev_menu.py` is still live.

### Legacy data/forms catalog and map-generator assets
- Location: `data/forms/**`, `modules/devtools/services/form_catalog.py`, `modules/devtools/services/fema_fetch.py`, `modules/devtools/services/pdf_mapgen.py`, `modules/devtools/services/form_identify.py`
- Purpose: older developer/import tooling and PDF/map assets for a `data/forms/catalog.json` layout.
- Known Callers: only reachable through the Devtools Template Debug panel above (itself still live via `dev_menu.py`); no callers outside that cluster.
- Removal Condition: any useful ingestion/scanning functionality has been ported to write `forms/catalog.json`, `forms/sets/<set_id>/<form_id>/template.pdf`, and `mapping.json`; otherwise safe to delete once the Template Debug panel above is removed.
- Verification: `rg -n "data/forms|FormCatalog|fema_fetch|pdf_mapgen|form_identify" modules data tests` — confirmed 2026-10-21 no callers outside the Template Debug panel cluster.

### Profile-scoped form template pipeline
- Location: `modules/forms_creator/form_registry.py`, `modules/forms_creator/session.py`, `modules/forms_creator/export.py`, `modules/forms_creator/bindings.py`, `profiles/ics_base/templates/**`
- Purpose: deterministic profile template export pipeline using `profiles/<profile_id>/templates/**`, `FormRegistry`, `FormSession`, per-profile binding definitions (`bindings.render_values()`), and `ALLOWED_BINDING_SOURCES` validation.
- Known Callers: `modules/forms_creator/api.py` (`export_form_unified()`'s primary path imports and calls `FormRegistry`/`FormSession`); `export.py` calls `bindings.render_values()` directly at export time.
- Removal Condition: all production exports use `modules.forms_creator.engine.generate()` directly or `modules.forms_creator.exporting.ExportService`, and no active profile/template selection workflow depends on `profiles/<id>/templates/**` — in practice, every caller of `export_form_unified()` must migrate first.
- Verification: `rg -n "FormRegistry|FormSession|export_form\\(|profiles/.*/templates" modules profiles tests` — confirmed 2026-10-21 `api.py` is still the primary-path caller.

### Unified form export bridge
- Location: `modules/forms_creator/api.py`
- Purpose: compatibility export facade (`export_form_unified()`) that tries the profile-scoped pipeline first, then falls back to the legacy `data/templates` renderer. The shim all three entries above funnel through.
- Known Callers: `modules/command/widgets/objective_detail_dialog.py`, `modules/command/panels/incident_objectives_panel.py`, `modules/safety/print_ics_206.py`, `modules/operations/taskings/repository.py`.
- Removal Condition: every production caller of `export_form_unified()` is migrated to `modules.forms_creator.exporting.ExportService` or a direct `engine.generate()` call using `forms/sets/**/mapping.json`. Once that happens, this entry and the three above it can all be deleted together.
- Verification: `rg -n "export_form_unified" modules tests` — confirmed 2026-10-21 all four known callers above are still unmigrated.
- Update 2026-10-19: the incident-organization ICS 203 export uses the existing export service with shared-server rendering for FEMA/ICS Canada/USCG. It does not use this bridge or add a fallback to it. Local `engine.generate()` remains in Mapper Window for template-authoring previews; the bridge's remaining callers listed above still need migration before deletion.
- Update 2026-09-13: `modules/logistics/print_ics_213_rr.py` (a prior known caller, already dead — nothing imported it) was removed. ICS 213RR now exports via `modules.forms_creator.exporting.builders.resource_requests.ResourceRequestFormBuilder` / `modules.logistics.resource_requests.export_service.generate_ics213rr`, not this bridge.

### Forms Creator database template service
- Location: `modules/forms_creator/services/templates.py`, `modules/forms_creator/services/template_importer.py`, `modules/forms_creator/ui/dialogs/NewTemplateWizard.py`, `modules/forms_creator/ui/dialogs/BindingDialog.py`, `modules/forms_creator/scripts/dev_seed.py`, `server/sarapp_db/sarapp_db/api/routers/forms.py`
- Purpose: API-backed form template and instance workflow based on `FormService`, template configs, and instance export endpoints — separate from the current filesystem-backed `forms/sets/**/mapping.json` authoring and export pipeline.
- Known Callers: `modules/intel/tabs/forms_tab.py`, `modules/forms_creator/__init__.py`, `modules/forms_creator/services/__init__.py`.
- Removal Condition: user-visible forms workflows, especially Intel -> Forms, either migrate to the canonical form-set registry/export service or are intentionally retired.
- Verification: `rg -n "FormService|NewTemplateWizard|BindingDialog|template_importer|/api/forms|routers.forms" modules data tests` plus confirming `server/sarapp_db/sarapp_db/api/app.py` no longer includes the forms router.

### Legacy `personnel_certifications` collection read-fallback
- Location: `server/sarapp_db/sarapp_db/api/routers/certifications.py` (`LegacyPersonnelCertificationsRepository`, `_legacy_rows`, called from `list_personnel_certs`)
- Purpose: certifications are now stored embedded on each `personnel` document (`PersonnelDocument.certifications`, see `server/sarapp_db/sarapp_db/schemas/personnel_schema.py`). `list_personnel_certs` only reads the separate `personnel_certifications` collection when a person's embedded list is empty, and if it finds rows there, copies them into the embedded list and self-heals (never writes to the legacy collection again). `set_personnel_cert`/`delete_personnel_cert` never touch the legacy collection at all.
- Known Callers: `list_personnel_certs` itself, on every request for a person whose embedded list is still empty.
- Removal Condition: every personnel record with certification data has had its embedded `certifications` list backfilled (e.g. via a one-time migration script that runs the same copy-and-set logic for every person instead of lazily on first read), after which `LegacyPersonnelCertificationsRepository`/`_legacy_rows`/the fallback branch in `list_personnel_certs` can be deleted along with the `personnel_certifications` collection itself.
- Verification: `rg -n "personnel_certifications|LegacyPersonnelCertifications" server/sarapp_db/sarapp_db` shows no writers, only this read-fallback.

### Personnel legacy-id migration scripts
- Location: `server/sarapp_db/seed_loaders/seed_master_from_sqlite.py`, `server/sarapp_db/seed_loaders/seed_incidents_from_sqlite.py`, `server/sarapp_db/seed_loaders/rebuild_demo_personnel.py`
- Purpose: one-time SQLite-to-Mongo migration helpers that still write `personnel_id`, `badge_number`, and other old roster shapes during data conversion. Not called by app runtime — intentionally retained as manually-invoked offline tooling for migrating a SQLite-era install.
- Known Callers: none automatic; run manually by an operator migrating an old installation.
- Removal Condition: the repo no longer needs to migrate SQLite-era personnel data or remap demo incidents.
- Verification: `rg` for imports of these scripts from any runtime module or test shows none.
- Notes: keep only as offline scripts; do not add new runtime compatibility logic around them.

### Demo check-in seeder
- Location: `server/sarapp_db/seed_loaders/seed_demo_checkins.py`
- Purpose: one-off/demo-only Mongo seeder that backfills personnel check-ins and `resource_status` rows from existing incident team rosters. Not called by app runtime — intentionally retained as a manually-invoked offline utility.
- Known Callers: none automatic; run manually for demo/board validation.
- Removal Condition: demo incidents no longer need scripted backfill of check-ins/resource-status rows.
- Verification: the seeder is not imported by runtime code.

### Liaison runtime ID repair and parallel request models
- Location: `server/sarapp_db/sarapp_db/api/routers/liaison.py` (`_ensure_int_ids`), `liaison_requests.py`, and desktop Liaison repository/tests.
- Purpose: reads repair missing `int_id` values with raw collection writes, on every read. Older agency requests, resource offers and feedback records coexist with the current `liaison_requests` records and narrative thread; the request router explicitly retains the older API for existing desktop consumers.
- Known Callers: `_ensure_int_ids` runs on every `liaison.py` read/write path; desktop Liaison repository still calls the older agency-requests/resource-offers/feedback API.
- Web behavior: new requests use `liaison_requests` only. Agency detail displays existing older records separately without copying them or falling back to them for current requests.
- Removal Condition: perform and verify a one-time identifier/data conversion, update remaining desktop consumers and SQLite-era Liaison tests, then remove runtime repairs and retired APIs.

### Facilities field aliases retained on the shared API
- Location: `server/sarapp_db/sarapp_db/api/routers/facilities.py` (`_serialize`, create/PUT) and `apps/desktop/sarapp_desktop/modules/logistics/facilities/models.py` (`from_api`).
- Purpose: falls back from `function_tags` to `capabilities` and from `served_sections` to `served_modules`, and the server writes both shapes on every create/PUT today. The web Facilities UI reads/writes only canonical `function_tags`/`served_sections`; no new fallback is added there.
- Known Callers: `facilities.py`'s serialize/create/PUT paths (every facility write); desktop `from_api` (every facility read).
- Removal Condition: migrate existing facility documents once and update remaining consumers, then remove server alias reads/writes and desktop compatibility reads together.
