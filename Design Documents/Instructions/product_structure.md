# Product Structure

## Module Inventory
The app is organized around ICS sections. Each module has its own panels, services, repository, and optional API router.

| # | Module | Description |
|---|--------|-------------|
| 1 | Command | Incident setup, objectives, status flags, operational periods, IAP builder |
| 2 | Planning | Strategic objectives, task tracking, IAP inputs, planning logs |
| 2-1 | Strategic Objectives | Objective lifecycle, approval workflow, audit trail, task linkage |
| 3 | Operations | Field execution, team assignments, real-time task status, ICS 214 logging |
| 3-1 | Taskings | Task creation/assignment, narrative log, debrief forms, ICS 204/CAPF 109 |
| 4 | Logistics | Resource requests, inventory, check-in/out, assignment workflow |
| 4-1 | Resource Request | ICS 213-RR workflow, approval chain, fulfillment tracking |
| 5 | Communications | Chat, ICS 213 messages, ICS 205 channel plan, comms log |
| 6 | Medical & Safety | Medical plans, safety messages, ICS 206, CAP ORM |
| 6-1 | CAP ORM | Operational Risk Management for CAP missions |
| 6-2 | Weather | NOAA/NWS weather panels, advisory/lightning tools |
| 7 | Intel | Data, clue management, intelligence dashboard |
| 8 | Liaison | Agency contacts, support requests, notifications |
| 9 | Personnel & Role Mgmt | Roster, org structure, assignments, qualifications, accountability |
| 9-1 | Personnel Certifications | Certification tracking per personnel record |
| 10 | Reference Library | ICS forms, agency docs, SOPs, guides |
| 11 | ICS Forms & Documentation | Fillable forms, auto-fill from live data, form versioning |
| 12 | Finance/Admin | Time tracking, expense reporting, procurement, reimbursement |
| 13 | Status Boards | Global and module-specific boards (teams, personnel, equipment, tasks, etc.) |
| 14 | Public Information | Press releases, briefing log, public info contacts |
| 15 | Mobile App Integration | Future: sync with field/mobile app |
| 16 | Training/Sandbox Mode | Simulated incidents, practice environment |
| 17 | SAR Toolkit | SAR-specific calculators, clue management, workflows |
| 18 | Disaster Response Toolkit | Floods, wildfires, hurricanes, etc. |
| 19 | Planned Event Toolkit | Event planning, vendor/permitting, public safety, promotions |
| 20 | Initial Response Toolkit | Hasty search, rapid tasking, initial response workflows |
| 21 | UI Customization | Template selector, custom theme editor, dashboard builder |
| XX | AI Integration | Future: assistant, automation, smart forms |
| XX | Advanced GIS | Future: external mapping platforms, AVL, drone feeds |

## Design Phases
1. Core System & User Foundation
2. Team Operations, Personnel, and Status Boards
3. Communications & Public Information
4. Forms, Documentation, & Reference Library
5. Logistics, Medical, & Safety
6. Intel & Mapping
7. Advanced Operations & Toolkits
8. UI Customization & Multi-Window UX
9. Status Boards, Automation, & Reporting
10. Finance/Admin & Incident Closeout
11. Mobile Integration & Future Systems
12. Special/Planned (AI & Advanced GIS)

Full phase and module detail: `Design Documents/designplan.md`
