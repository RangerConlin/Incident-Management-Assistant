"""One-time migration: legacy Finance/Admin data -> canonical Budget /
Estimate / Actual-Cost model.

Converts, per incident:
- finance_fuel_price_profiles  -> finance_rate_tables (category="fuel")
- finance_forecasts + finance_fuel_forecast_lines -> finance_estimates
  (one estimate per fuel forecast line; status "committed" if the parent
  forecast was Approved, else "estimated"; closed+"No longer needed" if the
  forecast was Rejected)
- finance_expenses -> finance_actual_cost_documents (one header per expense)
  + finance_actual_cost_lines (one line per expense), linked to the migrated
  estimate when the expense had a linked_forecast_id (split evenly across
  that forecast's migrated line-estimates, since the legacy data has no
  finer-grained link).
- finance_funding_sources is dropped; a single finance_budgets document is
  created per incident from the sum of current_balance (or starting_balance)
  across funding sources, if any existed, so existing budget figures are not
  silently lost.

This connects to Mongo directly (not through the HTTP API) because the
legacy collections and endpoints no longer exist in
server/sarapp_db/sarapp_db/api/routers/finance.py. It is idempotent per
incident: it skips incidents that already have any finance_estimates
documents, so re-running after a partial run or by mistake is safe.

Usage:
    python tools/scripts/migrate_finance_v2.py                 # all incidents
    python tools/scripts/migrate_finance_v2.py --incident INC-1 # one incident
    python tools/scripts/migrate_finance_v2.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(str(Path(__file__).resolve().parents[2] / "server" / "sarapp_db"))

from sarapp_db.api.routers.ic_overview import list_incidents  # noqa: E402
from sarapp_db.mongo.database_manager import get_incident_db  # noqa: E402


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_int_id(col) -> int:
    top = col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (top["int_id"] + 1) if top else 1


def migrate_incident(incident_id: str, *, dry_run: bool) -> Dict[str, int]:
    db = get_incident_db(incident_id)
    counts = {"rate_tables": 0, "estimates": 0, "actual_docs": 0, "actual_lines": 0, "budgets": 0}

    if db["finance_estimates"].find_one({}) is not None:
        print(f"[{incident_id}] already has finance_estimates — skipping (idempotent).")
        return counts

    # --- Fuel price profiles -> rate tables -------------------------------
    rate_tables_col = db["finance_rate_tables"]
    for profile in db["finance_fuel_price_profiles"].find({}):
        for fuel_type, price_field in (
            ("gasoline", "gasoline_price"),
            ("diesel", "diesel_price"),
            ("jet_a", "jet_a_price"),
            ("100ll", "aviation_100ll_price"),
        ):
            price = profile.get(price_field)
            if price is None:
                continue
            doc = {
                "int_id": _next_int_id(rate_tables_col),
                "incident_id": incident_id,
                "name": f"Fuel — {fuel_type}",
                "category": "fuel",
                "applies_to_type": "global",
                "applies_to_id": None,
                "amount": price,
                "unit": "gallon",
                "rate_kind": None,
                "effective_start": profile.get("effective_at"),
                "effective_end": None,
                "is_active": bool(profile.get("is_active")),
                "notes": profile.get("source_note") or profile.get("location_note"),
                "template_id": None,
                "revision_history": [{"at": _utcnow(), "by": None, "action": "migrated_from_fuel_price_profile", "detail": str(profile.get("int_id"))}],
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
            }
            counts["rate_tables"] += 1
            if not dry_run:
                rate_tables_col.insert_one(doc)

    # --- Forecasts + fuel forecast lines -> estimates ----------------------
    estimates_col = db["finance_estimates"]
    forecast_line_estimate_ids: Dict[int, List[int]] = {}  # forecast_id -> [estimate int_id]

    forecasts = {f["int_id"]: f for f in db["finance_forecasts"].find({})}
    for line in db["finance_fuel_forecast_lines"].find({}):
        forecast = forecasts.get(line.get("forecast_id"))
        status = "committed" if forecast and forecast.get("status") == "Approved" else "estimated"
        closed = bool(forecast and forecast.get("status") == "Rejected")
        amount = line.get("estimated_cost", 0.0)
        est_int_id = _next_int_id(estimates_col)
        doc = {
            "int_id": est_int_id,
            "incident_id": incident_id,
            "description": f"{line.get('resource_name', 'Resource')} fuel — {forecast.get('forecast_name') if forecast else 'migrated forecast'}",
            "category": "fuel",
            "source_type": "migrated_forecast_line",
            "source_id": str(line.get("int_id")),
            "task_id": line.get("linked_task_id"),
            "resource_request_id": None,
            "resource_request_item_id": None,
            "resource_type": line.get("resource_type"),
            "resource_id": line.get("resource_id"),
            "operational_period_id": forecast.get("operational_period_id") if forecast else None,
            "quantity": line.get("estimated_gallons", 0.0),
            "unit": "gallon",
            "rate_snapshot": {
                "rate_table_entry_id": None,
                "name": f"Fuel — {line.get('fuel_type')}",
                "category": "fuel",
                "amount": line.get("fuel_price"),
                "unit": "gallon",
                "rate_kind": None,
                "snapshotted_at": _utcnow(),
            },
            "calc_method": "migrated_fuel_forecast_line",
            "calc_inputs": {
                "estimated_miles_per_resource": line.get("estimated_miles_per_resource"),
                "estimated_mpg": line.get("estimated_mpg"),
                "estimated_hours": line.get("estimated_hours"),
                "gallons_per_hour": line.get("gallons_per_hour"),
            },
            "original_amount": amount,
            "satisfied_amount": 0.0,
            "remaining_amount": 0.0 if closed else amount,
            "status": status,
            "closed": closed,
            "satisfied": False,
            "closed_reason": "No longer needed" if closed else None,
            "linked_actual_line_ids": [],
            "notes": line.get("notes"),
            "created_by": None,
            "audit_history": [{"at": _utcnow(), "by": None, "action": "migrated_from_fuel_forecast_line", "detail": str(line.get("int_id"))}],
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }
        counts["estimates"] += 1
        forecast_line_estimate_ids.setdefault(line.get("forecast_id"), []).append(est_int_id)
        if not dry_run:
            estimates_col.insert_one(doc)

    # --- Expenses -> actual-cost documents + lines --------------------------
    actual_docs_col = db["finance_actual_cost_documents"]
    actual_lines_col = db["finance_actual_cost_lines"]
    estimates_lookup = {d["int_id"]: d for d in estimates_col.find({})} if not dry_run else {}

    for expense in db["finance_expenses"].find({}):
        subtotal = expense.get("amount_subtotal", 0.0)
        tax = expense.get("amount_tax", 0.0)
        shipping_fees = expense.get("amount_tip", 0.0)
        total = expense.get("amount_total", subtotal + tax + shipping_fees)
        doc_int_id = _next_int_id(actual_docs_col)
        doc = {
            "int_id": doc_int_id,
            "incident_id": incident_id,
            "vendor": expense.get("vendor") or "Unknown vendor",
            "document_number": expense.get("expense_number"),
            "document_date": expense.get("expense_datetime"),
            "subtotal": subtotal,
            "tax": tax,
            "shipping_fees": shipping_fees,
            "total": total,
            "notes": expense.get("notes"),
            "entered_by": expense.get("entered_by"),
            "verification_status": "verified" if expense.get("status") in {"Approved", "Paid/Reimbursed", "Closed"} else "unverified",
            "paid": expense.get("status") == "Paid/Reimbursed",
            "paid_date": expense.get("paid_at"),
            "paid_reference": None,
            "audit_history": [{"at": _utcnow(), "by": None, "action": "migrated_from_expense", "detail": str(expense.get("int_id"))}],
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }
        counts["actual_docs"] += 1
        if not dry_run:
            actual_docs_col.insert_one(doc)

        linked_forecast_id = expense.get("linked_forecast_id")
        candidate_estimate_ids = forecast_line_estimate_ids.get(linked_forecast_id, [])
        links: List[Dict[str, Any]] = []
        if candidate_estimate_ids and not dry_run:
            # No per-expense line-item split exists in the legacy data —
            # apply the full amount to the single migrated estimate when
            # there is exactly one; otherwise leave unlinked rather than
            # inventing a split the source document didn't provide.
            if len(candidate_estimate_ids) == 1:
                links = [{"estimate_id": candidate_estimate_ids[0], "amount": total}]

        line_int_id = _next_int_id(actual_lines_col)
        line_doc_id = f"migrated-actual-line-{incident_id}-{line_int_id}"
        line_doc = {
            "_id": line_doc_id,
            "int_id": line_int_id,
            "incident_id": incident_id,
            "document_id": doc_int_id,
            "description": expense.get("description") or expense.get("category", "Migrated expense"),
            "category": expense.get("category", "other"),
            "quantity": 1,
            "unit_price": total,
            "line_subtotal": subtotal,
            "attributable_extra": tax + shipping_fees,
            "linked_estimate_ids": [l["estimate_id"] for l in links],
            "linked_resource_request_item_id": None,
            "notes": None,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }
        counts["actual_lines"] += 1
        if not dry_run:
            actual_lines_col.insert_one(line_doc)
            if links:
                estimate_doc = estimates_lookup.get(links[0]["estimate_id"])
                if estimate_doc is not None:
                    satisfied = estimate_doc.get("satisfied_amount", 0.0) + links[0]["amount"]
                    remaining = max(estimate_doc.get("original_amount", 0.0) - satisfied, 0.0)
                    estimates_col.update_one(
                        {"int_id": estimate_doc["int_id"]},
                        {"$set": {
                            "satisfied_amount": satisfied,
                            "remaining_amount": remaining,
                            "closed": remaining <= 0,
                            "satisfied": remaining <= 0,
                            "closed_reason": "Actual cost received" if remaining <= 0 else estimate_doc.get("closed_reason"),
                            "linked_actual_line_ids": list(set(estimate_doc.get("linked_actual_line_ids", []) + [line_doc_id])),
                        }},
                    )
                    estimate_doc["satisfied_amount"] = satisfied
                    estimate_doc["remaining_amount"] = remaining

    # --- Funding sources -> a single budget total ---------------------------
    budgets_col = db["finance_budgets"]
    if budgets_col.find_one({}) is None:
        funding_total = sum(
            (fs.get("current_balance") if fs.get("current_balance") is not None else fs.get("starting_balance")) or 0.0
            for fs in db["finance_funding_sources"].find({})
        )
        if funding_total:
            counts["budgets"] += 1
            if not dry_run:
                budgets_col.insert_one({
                    "incident_id": incident_id,
                    "total_budget": funding_total,
                    "category_lines": [],
                    "notes": "Migrated from legacy funding sources — review and adjust.",
                    "created_at": _utcnow(),
                    "updated_at": _utcnow(),
                })

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incident", help="Migrate a single incident id instead of every incident.")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be migrated without writing.")
    args = parser.parse_args()

    if args.incident:
        incident_ids = [args.incident]
    else:
        incident_ids = [inc["id"] for inc in list_incidents() if inc.get("id")]

    if not incident_ids:
        print("No incidents found.")
        return

    for incident_id in incident_ids:
        counts = migrate_incident(incident_id, dry_run=args.dry_run)
        print(f"[{incident_id}] {'would migrate' if args.dry_run else 'migrated'}: {counts}")


if __name__ == "__main__":
    main()
