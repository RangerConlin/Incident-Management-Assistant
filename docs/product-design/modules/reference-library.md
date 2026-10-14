# Reference Library

## Purpose

Store, search, preview, and open incident-support reference documents.

The Reference Library is meant to give staff and field users quick access to SOPs, maps, guides, forms, training material, and other reusable documents.

## Users

- Field teams looking up SOPs, maps, and guides.
- Staff users importing and organizing reference files.
- Planning/safety/logistics users attaching reference material to incident workflows.
- Administrators curating reusable documents.

## Current Features

- Desktop Reference Library window with filters, results, and preview pane.
- Add Document dialog with file browse, category, tags, and import action.
- Public API layer for searching reference documents.
- Storage/ingest/thumbnail services exist.
- UI widgets exist for filters, results, item cards, and preview.
- Mobile Reference Library screen exists, but it uses preview/sample documents and is not connected to live reference library data.

## Core Workflows

- Open Reference Library.
- Search/filter reference documents.
- Preview selected material.
- Import a new document with category and tags.
- Open or use a reference item from the library.
- On mobile, view the scaffolded reference list.

## Build Status

Early/partial.

Desktop has the foundation of a real reference library: window, filters, results, preview, add/import dialog, API, storage, ingest, and thumbnails. The degree of end-to-end production readiness still needs verification.

Mobile is scaffold-only. It shows sample reference documents and explicitly says it is not connected to the reference library; opening documents is unavailable.

## Screens And UI Inventory

- Desktop: Reference Library window.
- Desktop: Add/Edit Document dialog.
- Desktop: Filters widget.
- Desktop: Results widget.
- Desktop: Item card widget.
- Desktop: Preview widget.
- Mobile: Reference Library screen scaffold.

## Links To Other Modules

- Forms: reference documents and form templates may overlap.
- Safety: hazard guides, safety SOPs, and training documents belong here.
- Communications: radio protocols and communication guides belong here.
- GIS/Maps: map PDFs and incident-area reference maps belong here.
- Admin/Settings: administrators curate categories/tags and library content.

## Desktop Experience

Desktop is the curation and richer browsing surface.

The main window follows a library layout: filters and results with a preview area. The Add Document dialog is the core authoring/import workflow.

## Mobile Experience

Mobile is not connected yet.

The mobile Reference Library screen displays preview data and a banner explaining that it is not connected. Attempts to open documents show an unavailable message.

## Current Gaps

- Mobile live library access is not implemented.
- Opening/rendering reference documents on mobile is not implemented.
- Category/tag taxonomy needs product design.
- Permissions, offline availability, and versioning are not yet described.
- Relationship between reference-library documents and forms/templates is unclear.

## Design Questions

- Is the Reference Library global, incident-specific, or both?
- Which documents should be cached offline on mobile?
- Who can import, edit, retire, or delete reference documents?
- How should categories, tags, favorites, and recently used items work?
- Should reference documents be attachable to tasks, plans, safety products, or comms plans?

## Future Design Ideas

- Mobile offline reference library with sync status.
- Favorites and recently opened documents.
- Incident-specific document packs.
- Role/category filters for field, planning, safety, logistics, communications, and command.
- Document version history and retire/archive workflow.
