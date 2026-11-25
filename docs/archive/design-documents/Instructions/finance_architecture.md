# Finance/Admin Architecture

## Canonical model

Three financial concepts only — do not add a separate allocation, forecast,
accrued-cost, or paid-cost record type:

1. **Budget** — the incident's authorized spending limit, with optional
   category lines. One document per incident in `FINANCE_BUDGETS`
   (singleton; no `int_id`). `GET/PUT /incidents/{id}/finance/budget`.
2. **Estimate** — a projected cost, manual or calculated from a Rate Table
   entry, in `FINANCE_ESTIMATES`. Status is `estimated` or `committed`.
   Closing an estimate without an actual cost requires a `closed_reason`
   from a fixed enum (see `CLOSE_REASONS` in `api/routers/finance.py`).
   Both statuses stay in projected-cost totals until `remaining_amount`
   reaches zero or the estimate is explicitly closed.
3. **Actual cost** — a document (receipt/invoice/payroll/etc.) in
   `FINANCE_ACTUAL_COST_DOCUMENTS` with one or more lines in
   `FINANCE_ACTUAL_COST_LINES`. A line may link to one or more estimates
   (and an estimate may be satisfied by lines from more than one document).
   Linking applies the linked amount to the estimate's `satisfied_amount`,
   reduces `remaining_amount`, and at zero marks the estimate
   `closed=True, closed_reason="Actual cost received"`.

```
projected_incident_cost = actual_cost + sum(remaining_amount of open estimates)
remaining_budget        = total_budget - projected_incident_cost
```

`FINANCE_RATE_TABLES` holds reusable/standard and incident-specific rate
entries (personnel, aircraft, vehicle, equipment, fuel, lodging, meals/per
diem, rentals/contracted services, other). Reusable standard rates live in
`MasterCollections.RATE_TABLE_TEMPLATES` (master catalog) and are copied
into an incident's `FINANCE_RATE_TABLES` via
`POST .../rate-tables/seed-from-template/{template_id}`, after which they
can be overridden per incident. A calculated Estimate snapshots the rate
(`rate_snapshot`) at creation time — a later edit to the Rate Table entry
never silently changes an existing Estimate's amount; use
`POST .../estimates/{id}/recalculate` to intentionally re-apply the
current quantity against the snapshotted rate.

`FINANCE_APPROVALS` (a module-specific approval/audit log) and
`FINANCE_ATTACHMENTS` (generic receipts/files by `record_type`/`record_id`)
are shared infrastructure for Estimates and Actual Cost Documents — they
predate and are intentionally separate from both the generic
`APPROVAL_INSTANCES`/`APPROVAL_RECORDS` system (`api/routers/approvals.py`)
and from Logistics' own `FINANCE_APPROVE`/`FINANCE_DENY` Resource Request
approval actions (`logistics_resource_requests.py`) — see "Resource Request
integration" below for how those connect.

## Debrief integration

Debrief data (hobbs/flight time, mileage, personnel hours, fuel usage —
currently captured as free-text fields in the Air General debrief form,
`apps/desktop/sarapp_desktop/modules/operations/taskings/task_detail_widget.py`
around line 5414) may **refine** an Estimate's quantity/amount, but can
never create an Actual Cost by itself — a refined Estimate still requires a
receipt/invoice/payroll record before it becomes an actual cost.

`POST /incidents/{id}/finance/estimates/debrief-refinement` is idempotent:
it upserts the one Estimate whose `source_type="debrief"` and
`source_id=<debrief_id>`, so saving the same debrief form repeatedly
updates that one record rather than creating duplicates. Reopening or
deleting a debrief should call
`POST .../estimates/debrief-refinement/{debrief_id}/flag-for-review`
instead of silently reversing the estimate — this appends an audit-history
entry for Finance to review rather than guessing at a reversal.

As of this writing, the debrief form in `task_detail_widget.py` does not
yet call either endpoint — that wiring is tracked in `backlog.md` under
`[Finance]`.

## Resource Request integration

Resource Requests (`modules/logistics/resource_requests/`,
`api/routers/logistics_resource_requests.py`) are not duplicated into
Finance — they are linked. An Estimate may carry a
`resource_request_id`/`resource_request_item_id`, and a `RequestItem` is
expected to eventually carry `estimated_quantity`/`estimated_unit_cost`/
`estimated_total_cost` plus an `estimate_id` back-link, so Finance's
existing `FINANCE_APPROVE`/`FINANCE_DENY` actions on a request can
create/commit the linked Estimate as part of that cost sign-off. That
field addition and the `FINANCE_APPROVE` wiring are tracked in `backlog.md`
under `[Finance]` — not yet implemented.

## Task Detail Finance tab

`GET /incidents/{id}/finance/task-summary/{task_id}` (and the desktop
`modules.finance.services.get_task_finance_summary`) return a task's
estimated/committed/remaining/actual totals, splitting actual-cost lines
into task-only vs. "shared" (a line linked to estimates spanning more than
one task is counted once at the incident level, not fully against every
task it touches). The Task Detail window's adaptive Finance tab (shown only
for resource types actually assigned/estimated) is tracked in `backlog.md`
under `[Finance]` — not yet implemented; the API and service layer it will
call already exist.

## Migrating existing data

Incidents created before this model existed have their Finance data in the
legacy `finance_forecasts`/`finance_fuel_forecast_lines`/`finance_expenses`/
`finance_fuel_price_profiles`/`finance_funding_sources` collections,
which no router or UI reads anymore. Run
`python tools/scripts/migrate_finance_v2.py` (optionally `--incident <id>`,
or `--dry-run` first) to convert that data into the canonical collections.
It is idempotent per incident (skips an incident that already has any
`finance_estimates` documents).
