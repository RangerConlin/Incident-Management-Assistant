# Web Client Development Status

Tracks module-by-module build status for `apps/web/` (the React/Vite browser
client — a full-CRUD clone of the desktop app, built one module at a time).
Source of truth for the module list and `live`/`planned` state is
[`apps/web/src/shell/moduleRegistry.ts`](../apps/web/src/shell/moduleRegistry.ts);
update that file first when a module ships, then update this doc.

Legend: ✅ Live · 🚧 In progress · ⬜ Planned (not started)

## Command

| Module | Status | Notes |
| --- | --- | --- |
| Command Dashboard | ⬜ Planned | |

## Planning

| Module | Status | Notes |
| --- | --- | --- |
| Planning Dashboard | ✅ Live | |
| Strategic Objectives | ✅ Live | |
| Operational Periods | ✅ Live | |
| Meetings | ✅ Live | |
| Situation Reports | ✅ Live | |
| Work Assignments | ✅ Live | |
| Approvals | ⬜ Planned | |
| Demobilization | ⬜ Planned | |

## Operations

| Module | Status | Notes |
| --- | --- | --- |
| Team Status Board | ✅ Live | |
| Task Status Board | ✅ Live | Task Detail's Planning tab links/unlinks Work Assignments; remaining tabs (Safety, Communications, Debriefing, Attachments, Intel, Log) wait on their modules |

## Logistics

| Module | Status | Notes |
| --- | --- | --- |
| Logistics Dashboard | ✅ Live | Live request/resource/facility totals, upcoming needs, and demobilization queue; stock levels remain unavailable |
| Resource Status Board | ✅ Live | All entity types (personnel/vehicle/aircraft/equipment) via the shared `resource_status` collection |
| Resource Requests | ✅ Live | Quick intake, header edits, items, approvals/status lifecycle, fulfillment, audit, printable summary and filled ICS-213RR PDF download |
| Check-In | ✅ Live | Personnel roster/search + vehicle/aircraft/equipment master-catalog search-and-check-in |
| Facilities | ✅ Live | Create/update/delete, primary-by-type, manager search, coordinates, functions and served sections |

## Communications

| Module | Status | Notes |
| --- | --- | --- |
| Communications Plan (ICS-205) | ✅ Live | Channel library, op-period plan, assignment/priority/encryption/remarks, reorder, validate |
| Traffic Log | ✅ Live | Filterable log board, new-entry dialog, inline priority/disposition changes |

## Medical & Safety

| Module | Status | Notes |
| --- | --- | --- |
| Medical | ⬜ Planned | |
| Safety / CAP ORM | ⬜ Planned | |
| Weather | ⬜ Planned | |

## Intel

| Module | Status | Notes |
| --- | --- | --- |
| Intel | ⬜ Planned | |

## Liaison

| Module | Status | Notes |
| --- | --- | --- |
| Liaison | ✅ Live | Agency directory/detail and contact entry; interactions; request/offer CRUD, links, work creation and narrative; reporting-note creation, curation and readiness. Related agreements/restrictions remain read-only. |

## Personnel & Role Management

| Module | Status | Notes |
| --- | --- | --- |
| Personnel | ⬜ Planned | |
| Certifications | ⬜ Planned | |

## Reference Library

| Module | Status | Notes |
| --- | --- | --- |
| Reference Library | ⬜ Planned | |

## ICS Forms & Documentation

| Module | Status | Notes |
| --- | --- | --- |
| Forms | ✅ Live | Shared downloadable ICS 202, 204, 209, 211, 213RR, 215, 215A and 230; explicit FEMA/ICS Canada template labels, saved sources, continuation pages |

## Finance/Admin

| Module | Status | Notes |
| --- | --- | --- |
| Finance/Admin | ⬜ Planned | |

## Public Information

| Module | Status | Notes |
| --- | --- | --- |
| Public Information | ✅ Live | PAO overview; release authoring, preview, lifecycle and history; media response drafts; talking points; misinformation timelines; templates; distribution records. Publication records status; external delivery is manual. |

## GIS

| Module | Status | Notes |
| --- | --- | --- |
| GIS | ⬜ Planned | |

## Toolkits

| Module | Status | Notes |
| --- | --- | --- |
| SAR Toolkit | ⬜ Planned | |
| Disaster Response Toolkit | ⬜ Planned | |
| Planned Event Toolkit | ⬜ Planned | |
| Initial Response Toolkit | ⬜ Planned | |

## Admin

| Module | Status | Notes |
| --- | --- | --- |
| Admin Catalogs | ⬜ Planned | |
| UI Customization | ⬜ Planned | |

## Cross-cutting / shell

| Item | Status | Notes |
| --- | --- | --- |
| Auth (login, account setup, change password) | ✅ Live | Server-side access control not yet enforced — JWT is accepted but no router checks it today (see `backlog.md`) |
| Connection settings (LAN / cloud router connect code) | ✅ Live | Doesn't yet solve the SPA bundle's own loading through a connect-code URL — see `apps/web/README.md` "Connection settings" |
| Incident selection | ✅ Live | |
| Real-time sync (WebSocket invalidation + polling floor) | ✅ Live | `src/realtime/IncidentSocketProvider.tsx` |
| Shared table UI (`DataTable`, `StatusPill`, `FilterBar`, etc.) | ✅ Live | `src/components/table/` |
