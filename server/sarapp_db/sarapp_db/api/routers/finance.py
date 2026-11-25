"""Finance/Admin router — canonical Budget / Estimate / Actual-Cost model
plus reusable Rate Tables.

Three financial concepts only, per the canonical model:

- Budget: the incident's authorized spending limit (optional category lines).
- Estimate: a projected cost (manual or calculated from a Rate Table entry),
  with status Estimated|Committed, that stays in projected-cost totals until
  satisfied or explicitly closed with a reason.
- Actual cost: a document (receipt/invoice/payroll/etc.) with one or more
  lines, each optionally linked to one or more Estimates. Linking an actual
  line to an estimate reduces that estimate's remaining amount; at zero the
  estimate is marked satisfied/closed.

There is no separate allocation/forecast/accrued-cost/paid-cost record type.
Rate Tables generalize what used to be a fuel-price-profile-only concept to
every rate category (personnel, aircraft, vehicle, equipment, fuel, lodging,
meals/per diem, rentals/contracted, other), each with a reusable master
template plus incident-specific entries/overrides.

`finance_approvals` is a module-specific approval log rather than reusing the
generic `APPROVAL_INSTANCES`/`APPROVAL_RECORDS` collections from
`approvals.py` — a deliberate scope choice, not an oversight (see agents.md).
This is also distinct from Logistics' `FINANCE_APPROVE`/`FINANCE_DENY`
Resource Request approval actions (`logistics_resource_requests.py`), which
this router's Estimates feed into rather than duplicate.

The legacy Forecast/FuelForecastLine/Expense/FuelPriceProfile/FundingSource
collections and endpoints have been removed. `scripts/migrate_finance_v2.py`
performs the one-time conversion of any existing data into this shape.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sarapp_db.mongo.collection_names import IncidentCollections, MasterCollections
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()

RATE_CATEGORIES = (
    "personnel",
    "aircraft",
    "vehicle",
    "equipment",
    "fuel",
    "lodging",
    "meals",
    "rentals",
    "contracted_services",
    "other",
)

ESTIMATE_STATUSES = ("estimated", "committed")

CLOSE_REASONS = (
    "No longer needed",
    "Request cancelled",
    "Resource not used",
    "Replaced by another estimate",
    "Duplicate",
    "Entered in error",
    "Included in another cost",
    "Provided at no charge",
    "Actual cost received",
)


# ===========================================================================
# Repositories
# ===========================================================================

class RateTablesRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_RATE_TABLES
    soft_deletes = False


class RateTableTemplatesRepository(BaseRepository):
    collection_name = MasterCollections.RATE_TABLE_TEMPLATES
    soft_deletes = False


class BudgetsRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_BUDGETS
    soft_deletes = False


class EstimatesRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_ESTIMATES
    soft_deletes = False


class ActualCostDocumentsRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_ACTUAL_COST_DOCUMENTS
    soft_deletes = False


class ActualCostLinesRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_ACTUAL_COST_LINES
    soft_deletes = False


class FinanceApprovalsRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_APPROVALS
    soft_deletes = False


class FinanceAttachmentsRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_ATTACHMENTS
    soft_deletes = False


def _rate_tables_repo(incident_id: str) -> RateTablesRepository:
    return RateTablesRepository(get_incident_db(incident_id))


def _rate_templates_repo() -> RateTableTemplatesRepository:
    return RateTableTemplatesRepository(get_master_db())


def _budgets_repo(incident_id: str) -> BudgetsRepository:
    return BudgetsRepository(get_incident_db(incident_id))


def _estimates_repo(incident_id: str) -> EstimatesRepository:
    return EstimatesRepository(get_incident_db(incident_id))


def _actual_docs_repo(incident_id: str) -> ActualCostDocumentsRepository:
    return ActualCostDocumentsRepository(get_incident_db(incident_id))


def _actual_lines_repo(incident_id: str) -> ActualCostLinesRepository:
    return ActualCostLinesRepository(get_incident_db(incident_id))


def _approvals_repo(incident_id: str) -> FinanceApprovalsRepository:
    return FinanceApprovalsRepository(get_incident_db(incident_id))


def _attachments_repo(incident_id: str) -> FinanceAttachmentsRepository:
    return FinanceAttachmentsRepository(get_incident_db(incident_id))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_int_id(repo: BaseRepository) -> int:
    top = repo._col.find_one({"int_id": {"$exists": True}}, sort=[("int_id", -1)])
    return (top["int_id"] + 1) if top else 1


def _strip(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc = dict(doc)
    doc.pop("_id", None)
    doc["id"] = doc.pop("int_id", None)
    return doc


def _require(repo: BaseRepository, incident_id: str, int_id: int, label: str) -> Dict[str, Any]:
    doc = repo.find_one({"int_id": int_id, "incident_id": incident_id})
    if doc is None:
        raise HTTPException(status_code=404, detail=f"{label} {int_id} not found")
    return doc


def _audit_entry(action: str, *, by: Optional[str] = None, detail: Optional[str] = None) -> Dict[str, Any]:
    return {"at": _utcnow(), "by": by, "action": action, "detail": detail}


def _record_approval(
    incident_id: str,
    record_type: str,
    record_id: int,
    action: str,
    *,
    approver_id: Optional[str] = None,
    approver_role: Optional[str] = None,
    comments: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> None:
    repo = _approvals_repo(incident_id)
    repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        "record_type": record_type,
        "record_id": record_id,
        "approver_id": approver_id,
        "approver_role": approver_role,
        "action": action,
        "comments": comments,
        "timestamp": timestamp or _utcnow(),
    })


# ===========================================================================
# Rate Tables
# ===========================================================================

class RateTableEntryBody(BaseModel):
    name: str
    category: Literal[RATE_CATEGORIES]  # type: ignore[valid-type]
    applies_to_type: Optional[str] = None  # person|resource|resource_type|organization|global
    applies_to_id: Optional[str] = None
    amount: float
    unit: str
    rate_kind: Optional[str] = None  # regular|overtime|None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    template_id: Optional[int] = None


class RateTableEntryUpdateBody(BaseModel):
    name: Optional[str] = None
    applies_to_type: Optional[str] = None
    applies_to_id: Optional[str] = None
    amount: Optional[float] = None
    unit: Optional[str] = None
    rate_kind: Optional[str] = None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    changed_by: Optional[str] = None


@router.get("/incidents/{incident_id}/finance/rate-tables")
def list_rate_tables(incident_id: str, category: Optional[str] = None, active_only: bool = False) -> List[Dict[str, Any]]:
    repo = _rate_tables_repo(incident_id)
    query: Dict[str, Any] = {"incident_id": incident_id}
    if category:
        query["category"] = category
    if active_only:
        query["is_active"] = True
    docs = repo.find_many(query, sort=[("category", 1), ("name", 1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/rate-tables", status_code=201)
def create_rate_table_entry(incident_id: str, body: RateTableEntryBody) -> Dict[str, Any]:
    repo = _rate_tables_repo(incident_id)
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        **body.model_dump(),
        "revision_history": [_audit_entry("created")],
    })
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/rate-tables/{entry_id}")
def get_rate_table_entry(incident_id: str, entry_id: int) -> Dict[str, Any]:
    repo = _rate_tables_repo(incident_id)
    return _strip(_require(repo, incident_id, entry_id, "Rate table entry"))


@router.patch("/incidents/{incident_id}/finance/rate-tables/{entry_id}")
def update_rate_table_entry(incident_id: str, entry_id: int, body: RateTableEntryUpdateBody) -> Dict[str, Any]:
    repo = _rate_tables_repo(incident_id)
    doc = _require(repo, incident_id, entry_id, "Rate table entry")
    fields = body.model_dump(exclude={"changed_by"}, exclude_none=True)
    if fields:
        history = doc.get("revision_history", [])
        history.append(_audit_entry("updated", by=body.changed_by, detail=", ".join(fields.keys())))
        repo.update_one(doc["_id"], {**fields, "revision_history": history})
    return _strip(repo.find_by_id(doc["_id"]))


@router.get("/incidents/{incident_id}/finance/rate-table-templates")
def list_rate_table_templates(incident_id: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    repo = _rate_templates_repo()
    query: Dict[str, Any] = {}
    if category:
        query["category"] = category
    docs = repo.find_many(query, sort=[("category", 1), ("name", 1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/rate-tables/seed-from-template/{template_id}", status_code=201)
def seed_rate_table_from_template(incident_id: str, template_id: int) -> Dict[str, Any]:
    templates_repo = _rate_templates_repo()
    template = templates_repo.find_one({"int_id": template_id})
    if template is None:
        raise HTTPException(status_code=404, detail=f"Rate table template {template_id} not found")
    repo = _rate_tables_repo(incident_id)
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        "name": template.get("name"),
        "category": template.get("category"),
        "applies_to_type": template.get("applies_to_type"),
        "applies_to_id": None,
        "amount": template.get("amount"),
        "unit": template.get("unit"),
        "rate_kind": template.get("rate_kind"),
        "effective_start": template.get("effective_start"),
        "effective_end": None,
        "is_active": True,
        "notes": template.get("notes"),
        "template_id": template_id,
        "revision_history": [_audit_entry("seeded_from_template", detail=f"template {template_id}")],
    })
    return _strip(doc)


# ===========================================================================
# Budget
# ===========================================================================

class BudgetCategoryLine(BaseModel):
    category: str
    amount: float
    notes: Optional[str] = None


class BudgetBody(BaseModel):
    total_budget: float
    category_lines: List[BudgetCategoryLine] = Field(default_factory=list)
    notes: Optional[str] = None


def _budget_summary(incident_id: str) -> Dict[str, Any]:
    budgets_repo = _budgets_repo(incident_id)
    budget_doc = budgets_repo.find_one({"incident_id": incident_id})
    total_budget = budget_doc.get("total_budget", 0.0) if budget_doc else 0.0

    estimates = _estimates_repo(incident_id).find_many({"incident_id": incident_id})
    open_estimated = sum(
        e.get("remaining_amount", 0.0) for e in estimates
        if not e.get("closed") and e.get("status") == "estimated"
    )
    open_committed = sum(
        e.get("remaining_amount", 0.0) for e in estimates
        if not e.get("closed") and e.get("status") == "committed"
    )

    lines = _actual_lines_repo(incident_id).find_many({"incident_id": incident_id})
    actual_cost = sum(l.get("line_subtotal", 0.0) + l.get("attributable_extra", 0.0) for l in lines)

    remaining_open = open_estimated + open_committed
    projected_incident_cost = actual_cost + remaining_open
    remaining_budget = total_budget - projected_incident_cost
    projected_budget_variance = total_budget - projected_incident_cost

    return {
        "total_budget": total_budget,
        "open_estimated_cost": open_estimated,
        "open_committed_cost": open_committed,
        "actual_cost": actual_cost,
        "projected_incident_cost": projected_incident_cost,
        "remaining_budget": remaining_budget,
        "projected_budget_variance": projected_budget_variance,
        "category_lines": budget_doc.get("category_lines", []) if budget_doc else [],
        "notes": budget_doc.get("notes") if budget_doc else None,
    }


@router.get("/incidents/{incident_id}/finance/budget")
def get_budget(incident_id: str) -> Dict[str, Any]:
    return _budget_summary(incident_id)


@router.put("/incidents/{incident_id}/finance/budget")
def set_budget(incident_id: str, body: BudgetBody) -> Dict[str, Any]:
    repo = _budgets_repo(incident_id)
    existing = repo.find_one({"incident_id": incident_id})
    payload = {
        "total_budget": body.total_budget,
        "category_lines": [l.model_dump() for l in body.category_lines],
        "notes": body.notes,
    }
    if existing is None:
        repo.insert_one({"incident_id": incident_id, **payload})
    else:
        repo.update_one(existing["_id"], payload)
    return _budget_summary(incident_id)


# ===========================================================================
# Estimates
# ===========================================================================

class ManualEstimateBody(BaseModel):
    description: str
    category: str
    source_type: Optional[str] = None  # e.g. "manual", "resource_request", "debrief"
    source_id: Optional[str] = None
    task_id: Optional[str] = None
    resource_request_id: Optional[str] = None
    resource_request_item_id: Optional[str] = None
    resource_type: Optional[str] = None  # personnel|team|vehicle|aircraft|equipment|other
    resource_id: Optional[str] = None
    operational_period_id: Optional[str] = None
    quantity: float = 1.0
    unit: Optional[str] = None
    amount: float
    status: Literal[ESTIMATE_STATUSES] = "estimated"  # type: ignore[valid-type]
    notes: Optional[str] = None
    created_by: Optional[str] = None


class CalculatedEstimateBody(BaseModel):
    description: str
    rate_table_entry_id: int
    task_id: Optional[str] = None
    resource_request_id: Optional[str] = None
    resource_request_item_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    operational_period_id: Optional[str] = None
    quantity: float
    status: Literal[ESTIMATE_STATUSES] = "estimated"  # type: ignore[valid-type]
    notes: Optional[str] = None
    created_by: Optional[str] = None


def _new_estimate_doc(
    incident_id: str,
    *,
    description: str,
    category: str,
    source_type: Optional[str],
    source_id: Optional[str],
    task_id: Optional[str],
    resource_request_id: Optional[str],
    resource_request_item_id: Optional[str],
    resource_type: Optional[str],
    resource_id: Optional[str],
    operational_period_id: Optional[str],
    quantity: float,
    unit: Optional[str],
    rate_snapshot: Optional[Dict[str, Any]],
    calc_method: str,
    calc_inputs: Dict[str, Any],
    amount: float,
    status: str,
    notes: Optional[str],
    created_by: Optional[str],
) -> Dict[str, Any]:
    return {
        "incident_id": incident_id,
        "description": description,
        "category": category,
        "source_type": source_type or "manual",
        "source_id": source_id,
        "task_id": task_id,
        "resource_request_id": resource_request_id,
        "resource_request_item_id": resource_request_item_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "operational_period_id": operational_period_id,
        "quantity": quantity,
        "unit": unit,
        "rate_snapshot": rate_snapshot,
        "calc_method": calc_method,
        "calc_inputs": calc_inputs,
        "original_amount": amount,
        "satisfied_amount": 0.0,
        "remaining_amount": amount,
        "status": status,
        "closed": False,
        "satisfied": False,
        "closed_reason": None,
        "linked_actual_line_ids": [],
        "notes": notes,
        "created_by": created_by,
        "audit_history": [_audit_entry("created", by=created_by)],
    }


@router.get("/incidents/{incident_id}/finance/estimates")
def list_estimates(
    incident_id: str,
    task_id: Optional[str] = None,
    resource_request_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    include_closed: bool = True,
) -> List[Dict[str, Any]]:
    repo = _estimates_repo(incident_id)
    query: Dict[str, Any] = {"incident_id": incident_id}
    if task_id:
        query["task_id"] = task_id
    if resource_request_id is not None:
        query["resource_request_id"] = resource_request_id
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if not include_closed:
        query["closed"] = False
    docs = repo.find_many(query, sort=[("created_at", -1), ("int_id", -1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/estimates", status_code=201)
def create_manual_estimate_default(incident_id: str, body: ManualEstimateBody) -> Dict[str, Any]:
    """Alias of /estimates/manual for generic CRUD-style clients (e.g. the
    web workspace scaffold) that only POST to the collection's base path."""
    return create_manual_estimate(incident_id, body)


@router.post("/incidents/{incident_id}/finance/estimates/manual", status_code=201)
def create_manual_estimate(incident_id: str, body: ManualEstimateBody) -> Dict[str, Any]:
    repo = _estimates_repo(incident_id)
    doc = _new_estimate_doc(
        incident_id,
        description=body.description,
        category=body.category,
        source_type=body.source_type,
        source_id=body.source_id,
        task_id=body.task_id,
        resource_request_id=body.resource_request_id,
        resource_request_item_id=body.resource_request_item_id,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        operational_period_id=body.operational_period_id,
        quantity=body.quantity,
        unit=body.unit,
        rate_snapshot=None,
        calc_method="manual",
        calc_inputs={},
        amount=body.amount,
        status=body.status,
        notes=body.notes,
        created_by=body.created_by,
    )
    doc["int_id"] = _next_int_id(repo)
    return _strip(repo.insert_one(doc))


@router.post("/incidents/{incident_id}/finance/estimates/calculated", status_code=201)
def create_calculated_estimate(incident_id: str, body: CalculatedEstimateBody) -> Dict[str, Any]:
    rate_entry = _require(_rate_tables_repo(incident_id), incident_id, body.rate_table_entry_id, "Rate table entry")
    amount = body.quantity * rate_entry.get("amount", 0.0)
    rate_snapshot = {
        "rate_table_entry_id": body.rate_table_entry_id,
        "name": rate_entry.get("name"),
        "category": rate_entry.get("category"),
        "amount": rate_entry.get("amount"),
        "unit": rate_entry.get("unit"),
        "rate_kind": rate_entry.get("rate_kind"),
        "snapshotted_at": _utcnow(),
    }
    repo = _estimates_repo(incident_id)
    doc = _new_estimate_doc(
        incident_id,
        description=body.description,
        category=rate_entry.get("category"),
        source_type="calculated",
        source_id=None,
        task_id=body.task_id,
        resource_request_id=body.resource_request_id,
        resource_request_item_id=body.resource_request_item_id,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        operational_period_id=body.operational_period_id,
        quantity=body.quantity,
        unit=rate_entry.get("unit"),
        rate_snapshot=rate_snapshot,
        calc_method="rate_table",
        calc_inputs={"quantity": body.quantity, "rate_table_entry_id": body.rate_table_entry_id},
        amount=amount,
        status=body.status,
        notes=body.notes,
        created_by=body.created_by,
    )
    doc["int_id"] = _next_int_id(repo)
    return _strip(repo.insert_one(doc))


def create_estimate_for_request_item(
    incident_id: str,
    *,
    resource_request_id: str,
    resource_request_item_id: str,
    description: str,
    category: str,
    quantity: float,
    unit: Optional[str],
    amount: float,
    status: str = "committed",
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Create the Estimate that backs a Resource Request item's cost impact.

    Called from `logistics_resource_requests.record_approval` on
    FINANCE_APPROVE — not an HTTP endpoint itself, so Logistics' approval
    log stays the single source of truth for *that* the request was
    approved, while this is Finance's own record of *what it will cost*.
    See docs/archive/design-documents/Instructions/finance_architecture.md.
    """
    repo = _estimates_repo(incident_id)
    doc = _new_estimate_doc(
        incident_id,
        description=description,
        category=category,
        source_type="resource_request",
        source_id=str(resource_request_id),
        task_id=None,
        resource_request_id=resource_request_id,
        resource_request_item_id=resource_request_item_id,
        resource_type=None,
        resource_id=None,
        operational_period_id=None,
        quantity=quantity,
        unit=unit,
        rate_snapshot=None,
        calc_method="resource_request_approval",
        calc_inputs={},
        amount=amount,
        status=status,
        notes=None,
        created_by=created_by,
    )
    doc["int_id"] = _next_int_id(repo)
    return _strip(repo.insert_one(doc))


@router.get("/incidents/{incident_id}/finance/estimates/{estimate_id}")
def get_estimate(incident_id: str, estimate_id: int) -> Dict[str, Any]:
    repo = _estimates_repo(incident_id)
    return _strip(_require(repo, incident_id, estimate_id, "Estimate"))


class EstimateRecalculateBody(BaseModel):
    quantity: float
    changed_by: Optional[str] = None
    detail: Optional[str] = None


@router.post("/incidents/{incident_id}/finance/estimates/{estimate_id}/recalculate")
def recalculate_estimate(incident_id: str, estimate_id: int, body: EstimateRecalculateBody) -> Dict[str, Any]:
    repo = _estimates_repo(incident_id)
    doc = _require(repo, incident_id, estimate_id, "Estimate")
    if doc.get("closed"):
        raise HTTPException(status_code=400, detail="Cannot recalculate a closed estimate")
    rate_snapshot = doc.get("rate_snapshot")
    if not rate_snapshot:
        raise HTTPException(status_code=400, detail="Estimate has no snapshotted rate to recalculate from")
    new_amount = body.quantity * rate_snapshot.get("amount", 0.0)
    new_remaining = new_amount - doc.get("satisfied_amount", 0.0)
    history = doc.get("audit_history", [])
    history.append(_audit_entry("recalculated", by=body.changed_by, detail=body.detail))
    repo.update_one(doc["_id"], {
        "quantity": body.quantity,
        "original_amount": new_amount,
        "remaining_amount": new_remaining,
        "calc_inputs": {**doc.get("calc_inputs", {}), "quantity": body.quantity},
        "audit_history": history,
    })
    return _strip(repo.find_by_id(doc["_id"]))


class EstimateCommitBody(BaseModel):
    changed_by: Optional[str] = None
    detail: Optional[str] = None


@router.post("/incidents/{incident_id}/finance/estimates/{estimate_id}/commit")
def commit_estimate(incident_id: str, estimate_id: int, body: EstimateCommitBody) -> Dict[str, Any]:
    repo = _estimates_repo(incident_id)
    doc = _require(repo, incident_id, estimate_id, "Estimate")
    if doc.get("closed"):
        raise HTTPException(status_code=400, detail="Cannot commit a closed estimate")
    history = doc.get("audit_history", [])
    history.append(_audit_entry("committed", by=body.changed_by, detail=body.detail))
    repo.update_one(doc["_id"], {"status": "committed", "audit_history": history})
    return _strip(repo.find_by_id(doc["_id"]))


class EstimateCloseBody(BaseModel):
    closed_reason: Literal[CLOSE_REASONS]  # type: ignore[valid-type]
    changed_by: Optional[str] = None
    detail: Optional[str] = None


@router.post("/incidents/{incident_id}/finance/estimates/{estimate_id}/close")
def close_estimate(incident_id: str, estimate_id: int, body: EstimateCloseBody) -> Dict[str, Any]:
    repo = _estimates_repo(incident_id)
    doc = _require(repo, incident_id, estimate_id, "Estimate")
    if doc.get("closed"):
        raise HTTPException(status_code=400, detail="Estimate already closed")
    history = doc.get("audit_history", [])
    history.append(_audit_entry("closed", by=body.changed_by, detail=f"{body.closed_reason}: {body.detail or ''}".strip(": ")))
    repo.update_one(doc["_id"], {
        "closed": True,
        "closed_reason": body.closed_reason,
        "remaining_amount": 0.0,
        "audit_history": history,
    })
    return _strip(repo.find_by_id(doc["_id"]))


class DebriefRefinementBody(BaseModel):
    debrief_id: str
    task_id: Optional[str] = None
    description: str
    category: str
    quantity: float
    unit: Optional[str] = None
    rate_table_entry_id: Optional[int] = None
    amount: Optional[float] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    calc_inputs: Dict[str, Any] = Field(default_factory=dict)
    changed_by: Optional[str] = None


@router.post("/incidents/{incident_id}/finance/estimates/debrief-refinement")
def refine_estimate_from_debrief(incident_id: str, body: DebriefRefinementBody) -> Dict[str, Any]:
    """Idempotent: updates the one estimate sourced from this debrief, or
    creates it on first call. Never creates an Actual Cost. Safe to call
    repeatedly as a debrief is edited (upsert keyed on source_type/source_id).
    """
    repo = _estimates_repo(incident_id)
    existing = repo.find_one({
        "incident_id": incident_id,
        "source_type": "debrief",
        "source_id": body.debrief_id,
    })

    amount = body.amount
    rate_snapshot = None
    if amount is None and body.rate_table_entry_id is not None:
        rate_entry = _require(_rate_tables_repo(incident_id), incident_id, body.rate_table_entry_id, "Rate table entry")
        amount = body.quantity * rate_entry.get("amount", 0.0)
        rate_snapshot = {
            "rate_table_entry_id": body.rate_table_entry_id,
            "name": rate_entry.get("name"),
            "category": rate_entry.get("category"),
            "amount": rate_entry.get("amount"),
            "unit": rate_entry.get("unit"),
            "rate_kind": rate_entry.get("rate_kind"),
            "snapshotted_at": _utcnow(),
        }
    if amount is None:
        raise HTTPException(status_code=400, detail="Either amount or rate_table_entry_id is required")

    if existing is None:
        doc = _new_estimate_doc(
            incident_id,
            description=body.description,
            category=body.category,
            source_type="debrief",
            source_id=body.debrief_id,
            task_id=body.task_id,
            resource_request_id=None,
            resource_request_item_id=None,
            resource_type=body.resource_type,
            resource_id=body.resource_id,
            operational_period_id=None,
            quantity=body.quantity,
            unit=body.unit,
            rate_snapshot=rate_snapshot,
            calc_method="debrief_refinement",
            calc_inputs=body.calc_inputs,
            amount=amount,
            status="estimated",
            notes=None,
            created_by=body.changed_by,
        )
        doc["int_id"] = _next_int_id(repo)
        return _strip(repo.insert_one(doc))

    if existing.get("closed"):
        history = existing.get("audit_history", [])
        history.append(_audit_entry(
            "debrief_reopened_for_review", by=body.changed_by,
            detail=f"debrief {body.debrief_id} changed after estimate was closed — needs review",
        ))
        repo.update_one(existing["_id"], {"audit_history": history})
        return _strip(repo.find_by_id(existing["_id"]))

    new_remaining = amount - existing.get("satisfied_amount", 0.0)
    history = existing.get("audit_history", [])
    history.append(_audit_entry("refined_from_debrief", by=body.changed_by, detail=f"debrief {body.debrief_id}"))
    repo.update_one(existing["_id"], {
        "quantity": body.quantity,
        "unit": body.unit or existing.get("unit"),
        "original_amount": amount,
        "remaining_amount": new_remaining,
        "rate_snapshot": rate_snapshot or existing.get("rate_snapshot"),
        "calc_inputs": body.calc_inputs,
        "audit_history": history,
    })
    return _strip(repo.find_by_id(existing["_id"]))


@router.post("/incidents/{incident_id}/finance/estimates/debrief-refinement/{debrief_id}/flag-for-review")
def flag_debrief_estimate_for_review(incident_id: str, debrief_id: str, changed_by: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Called when a debrief is reopened or deleted — flags the linked
    estimate's audit history rather than silently reversing it."""
    repo = _estimates_repo(incident_id)
    existing = repo.find_one({"incident_id": incident_id, "source_type": "debrief", "source_id": debrief_id})
    if existing is None:
        return None
    history = existing.get("audit_history", [])
    history.append(_audit_entry("debrief_reopened_or_deleted", by=changed_by, detail=f"debrief {debrief_id} — needs review"))
    repo.update_one(existing["_id"], {"audit_history": history})
    return _strip(repo.find_by_id(existing["_id"]))


# ===========================================================================
# Actual cost documents + lines
# ===========================================================================

class ActualCostDocumentBody(BaseModel):
    vendor: str
    document_number: Optional[str] = None
    document_date: str
    subtotal: float
    tax: float = 0.0
    shipping_fees: float = 0.0
    notes: Optional[str] = None
    entered_by: Optional[str] = None


@router.get("/incidents/{incident_id}/finance/actual-cost-documents")
def list_actual_cost_documents(incident_id: str) -> List[Dict[str, Any]]:
    repo = _actual_docs_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("document_date", -1), ("int_id", -1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/actual-cost-documents", status_code=201)
def create_actual_cost_document(incident_id: str, body: ActualCostDocumentBody) -> Dict[str, Any]:
    repo = _actual_docs_repo(incident_id)
    total = body.subtotal + body.tax + body.shipping_fees
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        **body.model_dump(),
        "total": total,
        "verification_status": "unverified",
        "paid": False,
        "paid_date": None,
        "paid_reference": None,
        "audit_history": [_audit_entry("created", by=body.entered_by)],
    })
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/actual-cost-documents/{document_id}")
def get_actual_cost_document(incident_id: str, document_id: int) -> Dict[str, Any]:
    repo = _actual_docs_repo(incident_id)
    return _strip(_require(repo, incident_id, document_id, "Actual cost document"))


class ActualCostDocumentStatusBody(BaseModel):
    verification_status: Optional[str] = None  # verified|unverified|disputed
    paid: Optional[bool] = None
    paid_date: Optional[str] = None
    paid_reference: Optional[str] = None
    changed_by: Optional[str] = None


@router.patch("/incidents/{incident_id}/finance/actual-cost-documents/{document_id}")
def update_actual_cost_document(incident_id: str, document_id: int, body: ActualCostDocumentStatusBody) -> Dict[str, Any]:
    repo = _actual_docs_repo(incident_id)
    doc = _require(repo, incident_id, document_id, "Actual cost document")
    fields = body.model_dump(exclude={"changed_by"}, exclude_none=True)
    if fields:
        history = doc.get("audit_history", [])
        history.append(_audit_entry("updated", by=body.changed_by, detail=", ".join(fields.keys())))
        repo.update_one(doc["_id"], {**fields, "audit_history": history})
    return _strip(repo.find_by_id(doc["_id"]))


class ActualCostLineLink(BaseModel):
    estimate_id: int
    amount: float


class ActualCostLineBody(BaseModel):
    description: str
    category: str
    quantity: float = 1.0
    unit_price: float
    attributable_tax: float = 0.0
    attributable_shipping: float = 0.0
    attributable_fees: float = 0.0
    linked_resource_request_item_id: Optional[str] = None
    notes: Optional[str] = None
    links: List[ActualCostLineLink] = Field(default_factory=list)


def _apply_actual_line_links(incident_id: str, line_id: str, links: List[ActualCostLineLink]) -> None:
    """Atomically apply a line's linked amounts to each target estimate's
    satisfied/remaining amount, closing any that reach zero remaining."""
    estimates_repo = _estimates_repo(incident_id)
    for link in links:
        estimate = _require(estimates_repo, incident_id, link.estimate_id, "Estimate")
        if estimate.get("closed"):
            raise HTTPException(status_code=400, detail=f"Estimate {link.estimate_id} is already closed")
        satisfied = estimate.get("satisfied_amount", 0.0) + link.amount
        remaining = max(estimate.get("original_amount", 0.0) - satisfied, 0.0)
        linked_lines = list(estimate.get("linked_actual_line_ids", []))
        if line_id not in linked_lines:
            linked_lines.append(line_id)
        updates: Dict[str, Any] = {
            "satisfied_amount": satisfied,
            "remaining_amount": remaining,
            "linked_actual_line_ids": linked_lines,
        }
        history = estimate.get("audit_history", [])
        history.append(_audit_entry("actual_cost_linked", detail=f"line {line_id} +{link.amount}"))
        updates["audit_history"] = history
        if remaining <= 0:
            updates.update({
                "status": estimate.get("status"),
                "closed": True,
                "satisfied": True,
                "closed_reason": "Actual cost received",
            })
        estimates_repo.update_one(estimate["_id"], updates)


@router.post("/incidents/{incident_id}/finance/actual-cost-documents/{document_id}/lines", status_code=201)
def add_actual_cost_line(incident_id: str, document_id: int, body: ActualCostLineBody) -> Dict[str, Any]:
    _require(_actual_docs_repo(incident_id), incident_id, document_id, "Actual cost document")
    subtotal = body.quantity * body.unit_price
    extra = body.attributable_tax + body.attributable_shipping + body.attributable_fees

    lines_repo = _actual_lines_repo(incident_id)
    doc = lines_repo.insert_one({
        "int_id": _next_int_id(lines_repo),
        "incident_id": incident_id,
        "document_id": document_id,
        "description": body.description,
        "category": body.category,
        "quantity": body.quantity,
        "unit_price": body.unit_price,
        "line_subtotal": subtotal,
        "attributable_extra": extra,
        "linked_estimate_ids": [l.estimate_id for l in body.links],
        "linked_resource_request_item_id": body.linked_resource_request_item_id,
        "notes": body.notes,
    })
    if body.links:
        _apply_actual_line_links(incident_id, str(doc["_id"]), body.links)
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/actual-cost-documents/{document_id}/lines")
def list_actual_cost_lines(incident_id: str, document_id: int) -> List[Dict[str, Any]]:
    _require(_actual_docs_repo(incident_id), incident_id, document_id, "Actual cost document")
    repo = _actual_lines_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id, "document_id": document_id}, sort=[("int_id", 1)])
    return [_strip(d) for d in docs]


class LinkMoreEstimatesBody(BaseModel):
    links: List[ActualCostLineLink]


@router.post("/incidents/{incident_id}/finance/actual-cost-lines/{line_int_id}/link")
def link_more_estimates(incident_id: str, line_int_id: int, body: LinkMoreEstimatesBody) -> Dict[str, Any]:
    lines_repo = _actual_lines_repo(incident_id)
    line = _require(lines_repo, incident_id, line_int_id, "Actual cost line")
    _apply_actual_line_links(incident_id, str(line["_id"]), body.links)
    linked_ids = list(line.get("linked_estimate_ids", []))
    for l in body.links:
        if l.estimate_id not in linked_ids:
            linked_ids.append(l.estimate_id)
    lines_repo.update_one(line["_id"], {"linked_estimate_ids": linked_ids})
    return _strip(lines_repo.find_by_id(line["_id"]))


# ===========================================================================
# Attachments + approvals (generic, by record_type/record_id)
# ===========================================================================

_ATTACHABLE_RECORD_TYPES = {"estimate", "actual_cost_document"}


class AttachmentBody(BaseModel):
    record_type: str
    record_id: int
    filename: str
    file_path: str
    file_type: Optional[str] = None
    attachment_type: str = "Receipt"
    uploaded_by: Optional[str] = None
    notes: Optional[str] = None


@router.post("/incidents/{incident_id}/finance/attachments", status_code=201)
def create_attachment(incident_id: str, body: AttachmentBody) -> Dict[str, Any]:
    if body.record_type == "actual_cost_document":
        _require(_actual_docs_repo(incident_id), incident_id, body.record_id, "Actual cost document")
    elif body.record_type == "estimate":
        _require(_estimates_repo(incident_id), incident_id, body.record_id, "Estimate")

    repo = _attachments_repo(incident_id)
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        **body.model_dump(),
        "uploaded_at": _utcnow(),
    })
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/attachments")
def list_attachments(incident_id: str, record_type: str = Query(...), record_id: int = Query(...)) -> List[Dict[str, Any]]:
    repo = _attachments_repo(incident_id)
    docs = repo.find_many(
        {"incident_id": incident_id, "record_type": record_type, "record_id": record_id},
        sort=[("uploaded_at", -1), ("int_id", -1)],
    )
    return [_strip(d) for d in docs]


class ApprovalBody(BaseModel):
    record_type: str
    record_id: int
    approver_id: Optional[str] = None
    approver_role: Optional[str] = None
    action: str
    comments: Optional[str] = None


@router.post("/incidents/{incident_id}/finance/approvals", status_code=201)
def create_approval(incident_id: str, body: ApprovalBody) -> Dict[str, Any]:
    if body.record_type == "actual_cost_document":
        _require(_actual_docs_repo(incident_id), incident_id, body.record_id, "Actual cost document")
    elif body.record_type == "estimate":
        _require(_estimates_repo(incident_id), incident_id, body.record_id, "Estimate")

    repo = _approvals_repo(incident_id)
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        **body.model_dump(),
        "timestamp": _utcnow(),
    })
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/approvals")
def list_approvals(incident_id: str, record_type: str = Query(...), record_id: int = Query(...)) -> List[Dict[str, Any]]:
    repo = _approvals_repo(incident_id)
    docs = repo.find_many(
        {"incident_id": incident_id, "record_type": record_type, "record_id": record_id},
        sort=[("timestamp", -1), ("int_id", -1)],
    )
    return [_strip(d) for d in docs]


# ===========================================================================
# Reporting
# ===========================================================================

@router.get("/incidents/{incident_id}/finance/dashboard")
def get_dashboard_snapshot(incident_id: str) -> Dict[str, Any]:
    summary = _budget_summary(incident_id)
    estimates = _estimates_repo(incident_id).find_many({"incident_id": incident_id})
    open_estimates = [e for e in estimates if not e.get("closed")]
    missing_docs = sum(
        1 for e in open_estimates
        if e.get("status") == "committed" and not e.get("linked_actual_line_ids")
    )
    return {
        **summary,
        "open_estimate_count": len(open_estimates),
        "committed_pending_documentation": missing_docs,
        "estimate_count": len(estimates),
    }


@router.get("/incidents/{incident_id}/finance/task-summary/{task_id}")
def get_task_finance_summary(incident_id: str, task_id: str) -> Dict[str, Any]:
    estimates = _estimates_repo(incident_id).find_many({"incident_id": incident_id, "task_id": task_id})
    estimated_total = sum(e.get("original_amount", 0.0) for e in estimates if e.get("status") == "estimated" and not e.get("closed"))
    committed_total = sum(e.get("original_amount", 0.0) for e in estimates if e.get("status") == "committed" and not e.get("closed"))
    remaining_open = sum(e.get("remaining_amount", 0.0) for e in estimates if not e.get("closed"))

    line_ids = set()
    for e in estimates:
        line_ids.update(e.get("linked_actual_line_ids", []))
    lines_repo = _actual_lines_repo(incident_id)
    lines = [lines_repo.find_by_id(lid) for lid in line_ids]
    lines = [l for l in lines if l]
    shared_lines = [l for l in lines if len(l.get("linked_estimate_ids", [])) > 1 or _line_spans_multiple_tasks(incident_id, l)]
    task_only_lines = [l for l in lines if l not in shared_lines]
    actual_total = sum(l.get("line_subtotal", 0.0) + l.get("attributable_extra", 0.0) for l in task_only_lines)
    shared_total = sum(l.get("line_subtotal", 0.0) + l.get("attributable_extra", 0.0) for l in shared_lines)

    return {
        "task_id": task_id,
        "estimated_total": estimated_total,
        "committed_total": committed_total,
        "remaining_open_estimate": remaining_open,
        "actual_total": actual_total,
        "shared_actual_total": shared_total,
        "estimates": [_strip(e) for e in estimates],
    }


def _line_spans_multiple_tasks(incident_id: str, line: Dict[str, Any]) -> bool:
    estimates_repo = _estimates_repo(incident_id)
    task_ids = set()
    for est_id in line.get("linked_estimate_ids", []):
        est = estimates_repo.find_one({"int_id": est_id, "incident_id": incident_id})
        if est and est.get("task_id"):
            task_ids.add(est.get("task_id"))
    return len(task_ids) > 1


@router.get("/incidents/{incident_id}/finance/pending-approvals")
def list_pending_approvals(incident_id: str) -> List[Dict[str, Any]]:
    estimates = _estimates_repo(incident_id).find_many({
        "incident_id": incident_id, "status": "committed", "closed": False,
    })
    docs = _actual_docs_repo(incident_id).find_many({
        "incident_id": incident_id, "verification_status": "unverified",
    })
    rows = [
        {
            "record_type": "estimate",
            "record_id": e["int_id"],
            "description": e.get("description", ""),
            "amount": e.get("remaining_amount", 0.0),
            "status": e.get("status"),
        }
        for e in estimates
    ] + [
        {
            "record_type": "actual_cost_document",
            "record_id": d["int_id"],
            "description": d.get("vendor", ""),
            "amount": d.get("total", 0.0),
            "status": d.get("verification_status"),
        }
        for d in docs
    ]
    return rows
