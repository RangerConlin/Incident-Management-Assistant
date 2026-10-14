# Facilities

## Purpose

Track incident facilities and operational locations such as command posts, staging areas, supply points, check-in points, communications sites, delivery destinations, and other support locations used across logistics workflows.

## Users

- Logistics staff managing support locations.
- Planning and operations staff referencing incident facilities.
- Check-in/resource staff selecting reporting or destination locations.
- Resource request staff selecting delivery facilities.

## Current Features

- Working: Facilities Manager panel exists.
- Working: Facilities can be filtered by type, status, and text search.
- Working: Facilities can be created, saved, deleted, geocoded, and reverse-geocoded.
- Working: Facility details include name, type, status, primary-for-type flag, address/description, latitude, longitude, matched address, manager, contact name, contact phone, function tags, served sections, and notes.
- Working: Facilities can be marked primary for a type.
- Working: Facilities can select a manager from personnel.
- Working: FacilityPicker is used by Resource Status Board and Resource Request delivery facility fields.
- Partial: Facilities are currently a logistics-focused manager rather than a visible cross-module location hub.

## Core Workflows

- View and filter incident facilities.
- Search facilities by text, tags, sections, or notes.
- Create a new facility.
- Edit facility details and contact information.
- Assign a facility manager.
- Mark a facility as primary for its type.
- Add function tags and served sections.
- Geocode an address/description.
- Reverse-geocode coordinates.
- Delete a facility.
- Select a facility from another workflow, such as resource status or resource request delivery.

## Build Status

Working/partial. The manager panel is functional and integrated into logistics workflows through facility pickers. The broader design question is whether facilities should remain logistics-owned or become a shared incident location layer used by operations, planning, GIS, communications, and check-in.

## Screens And UI Inventory

- Facilities Manager panel.
- Incident/status header.
- Type filter.
- Status filter.
- Search field.
- Toolbar actions: Refresh, New Facility, Geocode, Reverse Geocode, Save, Delete.
- Facility list.
- Facility Details form.
- Cross-Module Use section.
- Personnel picker for facility manager.
- Facility picker widgets embedded in resource status and resource request workflows.

## Links To Other Modules

- Resource Status Board can associate resources with destination/check-in facilities.
- Resource Requests can select delivery facilities.
- Personnel can supply facility managers.
- Check-in/reporting location workflows should be able to reuse facilities.
- GIS/maps should eventually show facility locations.
- Communications and planning may use facilities as operational sites.

## Desktop Experience

Desktop has a direct Facilities Manager. It is a split-panel editor with filters/search on top, facility list on the left, and editable facility details on the right.

## Mobile Experience

No clear mobile facilities management workflow is visible. Mobile may indirectly see facility/location information through tasks, team resources, maps, or future request/check-in flows, but facilities are currently desktop-managed.

## Current Gaps

- Facilities are not yet positioned as the shared location model across the product.
- Facility type/status vocabularies need review against planning, logistics, communications, and GIS needs.
- The panel status text uses local styling that should be brought into shared UI/theme patterns.
- Geocoding exists in the manager, but facility display on a map appears to be future work.
- Mobile has no obvious facility browsing or selection flow.

## Design Questions

- Should facilities be a Logistics submodule or a shared Incident Locations module?
- Which facility types are needed for SAR, planned events, and disaster response?
- Which modules should create facilities versus only reference them?
- Should check-in reporting locations be free text, facility-based, or both?
- How should primary facilities be shown in dashboards and maps?
- Should mobile users see or navigate to facilities?

## Future Design Ideas

- Treat facilities as shared incident locations with logistics ownership for support-site details.
- Add map display and selection for facilities once GIS/map work matures.
- Use facilities consistently for delivery destinations, staging, check-in, communications sites, and resource locations.
- Add facility status indicators to Logistics Dashboard and future incident overview screens.
