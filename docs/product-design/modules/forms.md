# Forms

## Purpose

Generate, fill, map, preview, and export incident forms and documentation products.

Forms is both a user-facing toolset and shared infrastructure used by other modules to produce ICS, SAR, communications, logistics, tasking, planning, intel, and safety outputs.

## Users

- Staff users generating incident forms.
- Module owners exporting their module-specific products.
- Administrators/mappers maintaining form templates and field mappings.
- Developers/advanced users validating PDF mappings and export builders.

## Current Features

- Form generation engine fills PDF forms from incident data.
- Form registry and form-set registry track templates, sets, catalog entries, coverage, and metadata.
- Unified export API supports v2 templates with fallback legacy behavior.
- Export service, export registry, export builders, prepared exports, and export requests exist.
- Builders exist for communications, ICS, intel, medical, resource requests, task assignments, and work assignments.
- PDF filler, mapping discovery, field binding, template importing, rasterization, OCR, preview, validation, and mapping tools exist.
- UI surfaces include Forms Creator Hub, Mapper Window, Manage Sets dialog, Array Catalog Editor, PDF Filler widget, Canvas View, Field Items, and multiple template/binding/version dialogs.
- Existing mappings include ICS-204, ICS-205, ICS-213, ICS-214, ICS-211/check-in, and other cataloged forms.
- Many modules call forms exports directly: communications ICS-205, objectives ICS-202, resource requests ICS-213RR, task forms, safety products, intel/SAR forms, and logs.
- Mobile Forms action currently opens a coming-soon path rather than a live forms workspace.

## Core Workflows

- Generate a form from module data.
- Select a form set/profile and form template.
- Resolve incident data into a form data context.
- Fill mapped PDF fields and export a PDF.
- Create/import/manage form sets and templates.
- Map PDF fields to data bindings.
- Validate mappings and preview output.
- Use module-specific export buttons instead of entering the forms tool directly.

## Build Status

Substantial infrastructure, uneven product surface.

Forms has a large amount of working infrastructure and many modules already depend on it. The export pipeline is a core shared capability. The mapping and template-management tools also exist, but they are more technical/admin-facing than customer-facing.

Mobile forms are not built as a usable field workflow. The field dashboard exposes Forms as coming soon.

## Screens And UI Inventory

- Desktop: Forms Creator Hub.
- Desktop: Mapper Window.
- Desktop: Manage Sets dialog.
- Desktop: Array Catalog Editor.
- Desktop: PDF Filler widget.
- Desktop: Canvas View.
- Desktop: New Template Wizard.
- Desktop: New Form Set dialog.
- Desktop: New Form dialog.
- Desktop: Binding dialog / New Binding dialog.
- Desktop: Array Source dialog.
- Desktop: Create Version dialog.
- Desktop: Preview and Validation dialogs.
- Desktop: Table Editor dialog.
- Mobile: Forms coming-soon action.

## Links To Other Modules

- Command: ICS-202, ICS-203, ICS-207, SITREP/ICS-209-style outputs, IAP packet concepts.
- Planning: IAP, work assignments, ICS-215/215A, meeting products.
- Tasking: ICS-204/task assignment forms and task logs.
- Logistics: ICS-213RR, ICS-211/check-in, resource request summaries, demob/resource products.
- Communications: ICS-205.
- Safety: ICS-206, ICS-208, ICS-215A, IWI/safety reports.
- Intel/Weather: SAR/intel forms and weather briefings.
- Reference Library: source PDFs/templates and documentation assets may overlap.

## Desktop Experience

Desktop is the authoring, mapping, and export environment.

Most normal users encounter forms through buttons inside other modules, not by opening Forms Creator directly. The direct forms UI is more like an admin/developer workbench for templates, bindings, mappings, validation, previews, and set management.

## Mobile Experience

Mobile forms are not implemented yet.

The mobile field dashboard has a Forms action, but it is marked coming soon. Mobile users may view products indirectly through other screens, but no dedicated mobile form filling/signing/export workflow was identified.

## Current Gaps

- Mobile form filling/export is not built.
- Customer-facing forms browser/workspace needs design separate from technical mapping tools.
- Some catalog entries and PDFs remain unmapped, non-fillable, partially mapped, or dependent on exact PDF field structure.
- Readiness status for each form should be visible to product users.
- Relationship between generated PDFs, saved document records, distribution, signatures, and approvals needs design.
- Forms packet/IAP packet workflows are not yet unified.

## Design Questions

- What forms are customer-critical for the first complete product milestone?
- Should users think in terms of forms, products, packets, or module exports?
- Which forms can be generated automatically and which require manual editing?
- Where are generated PDFs stored, versioned, approved, and distributed?
- What forms need mobile data entry or signature support?
- How should incomplete mappings be exposed without overwhelming users?

## Future Design Ideas

- Customer-facing Forms Center with ready/partial/not-ready status by form.
- Operational-period packet builder for IAP and command products.
- Mobile form viewer/filler for selected field forms.
- Signature/approval routing for generated forms.
- Export history with generated PDFs, versions, source data, and distribution records.
- Form readiness dashboard for administrators.
