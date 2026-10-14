# Admin And Settings

## Purpose

Manage reusable master data, libraries, application preferences, mobile profile/settings, notifications, connections, and tracking controls.

Admin/Settings is a cross-cutting support area rather than one single product module.

## Users

- System administrators maintaining master libraries.
- Staff configuring resource types, hazard types, GAR templates, and capabilities.
- Mobile users managing profile, connection, notifications, text size, and location tracking.
- Developers/support staff reviewing diagnostics and app configuration.

## Current Features

- Desktop Resource Type Library with add, edit, duplicate, deactivate, filters, empty state, import, export, capability manager, and modeless library window behavior.
- Resource Type Editor and Resource Type Search Box are reusable by check-in, logistics, resource requests, and planning.
- Capability Manager with new/edit/deactivate/import/export.
- Hazard Type Library foundation with hazard type repository, editor, search box, default SPE values, and safety analysis template support.
- GAR Template repository/window foundation exists.
- Mobile Settings screen includes profile management, profile sync, connection management, notification history, notification category toggles, notification channel sound selection, text scaling/appearance, location tracking toggle, manual ping, sync pending, and tracking diagnostics.
- Mobile Connections screen supports server/router connection management.
- Mobile profile screen supports local profile creation/editing.
- Notification preferences and notification channel/sound services exist.
- Location tracking service supports diagnostics, start/stop, manual ping, pending sync, and resume behavior.

## Core Workflows

- Maintain resource type master library and capabilities.
- Import/export resource types and capabilities.
- Maintain hazard type library and safety templates.
- Configure GAR/safety template data.
- Edit mobile profile and sync it to the server.
- Manage mobile connection settings.
- Review notification history and configure notification preferences/sounds.
- Enable/disable mobile location tracking, send manual pings, and inspect diagnostics.

## Build Status

Partial but important.

The desktop admin libraries for resource types and hazard types are real, reusable foundations. Resource Type Library appears relatively mature; Hazard Type Library and GAR templates exist as foundations tied into safety but should be verified for full workflow readiness.

Mobile settings are substantial and user-facing. Profile, connection, notification, sound, tracking, and diagnostics controls are present. This is one of the more complete mobile support areas.

## Screens And UI Inventory

- Desktop: Resource Type Library window.
- Desktop: Resource Type Editor window.
- Desktop: Capability Manager window.
- Desktop: Resource Type Search Box.
- Desktop: Hazard Type Library window.
- Desktop: Hazard Type Editor window.
- Desktop: Hazard Type Search Box.
- Desktop: GAR Template Manager window.
- Mobile: Settings screen.
- Mobile: Profile screen.
- Mobile: Connections screen.
- Mobile: Notification Center screen.
- Mobile: tracking diagnostics panel.

## Links To Other Modules

- Logistics/Resource Requests/Check-In: resource type library and capabilities.
- Safety: hazard types, safety templates, GAR/SPE foundations.
- Personnel/Teams: mobile profile and team session settings.
- GIS/Maps: location tracking settings and diagnostics.
- Notifications/Messages: notification preferences, history, and sounds.
- Mobile app shell: connection management, profile sync, text scale, and app version display.

## Desktop Experience

Desktop admin is library-management oriented.

The Resource Type Library is the strongest example: table, filters, actions, import/export, capability management, and editor dialogs. Hazard Type and GAR template areas appear to follow a similar reusable-library pattern.

## Mobile Experience

Mobile settings are practical and broad.

The Settings screen lets users manage identity, server connections, notification behavior, notification sounds, location tracking, and tracking diagnostics. This is field-user configuration rather than admin master-data management.

## Current Gaps

- No single desktop Admin/Settings home was identified tying all libraries together.
- Hazard Type Library and GAR Template workflows need full build-state verification.
- Desktop resource/hazard library styling should be checked against shared no-hardcoded-color rules over time.
- Relationship between master libraries and incident-specific overrides needs customer-level design.
- Mobile settings are strong, but admin master-library editing is desktop-only.

## Design Questions

- Which libraries are global master data versus incident-specific configuration?
- Who can edit resource types, hazard types, GAR templates, and capabilities?
- How should imports/exports be audited and reviewed before replacing master data?
- Should mobile users ever manage admin libraries, or only their own settings?
- How should profile identity relate to personnel records and check-in records?
- What settings must be surfaced in desktop footer/status/version areas?

## Future Design Ideas

- Desktop Admin Home grouping resource types, hazard types, GAR templates, lookup values, connections, and diagnostics.
- Library change history and import preview/rollback.
- Role-based permissions for master-data editing.
- Incident-specific overrides layered on top of global libraries.
- Mobile diagnostics export/share for support.
- Unified profile/personnel identity reconciliation workflow.
