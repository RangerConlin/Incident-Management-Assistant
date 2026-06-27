"""Finance/Admin router — fuel pricing, forecasts, expenses, approvals.

All collections are incident-scoped (no master-level finance data; the old
sqlite `vendors` master table was dropped during migration — it had zero
readers/writers anywhere in the app).

`finance_approvals` is a module-specific approval log rather than reusing the
generic `APPROVAL_INSTANCES`/`APPROVAL_RECORDS` collections from
`approvals.py`. That's a deliberate scope choice for this pass, not an
oversight — see agents.md for the consolidation note: finance's
submit/approve workflow could plausibly be rebuilt on top of the generic
approvals system later, but that's a design change beyond a faithful port of
the existing sqlite behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sarapp_db.mongo.collection_names import IncidentCollections
from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

router = APIRouter()


class FuelPriceProfilesRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_FUEL_PRICE_PROFILES
    soft_deletes = False


class ForecastsRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_FORECASTS
    soft_deletes = False


class FuelForecastLinesRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_FUEL_FORECAST_LINES
    soft_deletes = False


class FundingSourcesRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_FUNDING_SOURCES
    soft_deletes = False


class ExpensesRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_EXPENSES
    soft_deletes = False


class FinanceApprovalsRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_APPROVALS
    soft_deletes = False


class FinanceAttachmentsRepository(BaseRepository):
    collection_name = IncidentCollections.FINANCE_ATTACHMENTS
    soft_deletes = False


def _fuel_price_repo(incident_id: str) -> FuelPriceProfilesRepository:
    return FuelPriceProfilesRepository(get_incident_db(incident_id))


def _forecasts_repo(incident_id: str) -> ForecastsRepository:
    return ForecastsRepository(get_incident_db(incident_id))


def _fuel_lines_repo(incident_id: str) -> FuelForecastLinesRepository:
    return FuelForecastLinesRepository(get_incident_db(incident_id))


def _funding_repo(incident_id: str) -> FundingSourcesRepository:
    return FundingSourcesRepository(get_incident_db(incident_id))


def _expenses_repo(incident_id: str) -> ExpensesRepository:
    return ExpensesRepository(get_incident_db(incident_id))


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
# Fuel price profiles
# ===========================================================================

class FuelPriceProfileBody(BaseModel):
    operational_period_id: Optional[str] = None
    gasoline_price: float
    diesel_price: float
    jet_a_price: float
    aviation_100ll_price: float
    location_note: Optional[str] = None
    source_note: Optional[str] = None
    entered_by: Optional[str] = None
    effective_at: str
    is_active: bool = False


@router.get("/incidents/{incident_id}/finance/fuel-price-profiles")
def list_fuel_price_profiles(incident_id: str) -> List[Dict[str, Any]]:
    repo = _fuel_price_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("effective_at", -1), ("int_id", -1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/fuel-price-profiles", status_code=201)
def create_fuel_price_profile(incident_id: str, body: FuelPriceProfileBody) -> Dict[str, Any]:
    repo = _fuel_price_repo(incident_id)
    if body.is_active:
        for doc in repo.find_many({"incident_id": incident_id, "is_active": True}):
            repo.update_one(doc["_id"], {"is_active": False})
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        **body.model_dump(),
        "entered_at": _utcnow(),
    })
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/fuel-price-profiles/active")
def get_active_fuel_price_profile(incident_id: str) -> Optional[Dict[str, Any]]:
    repo = _fuel_price_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id, "is_active": True}, sort=[("effective_at", -1), ("int_id", -1)], limit=1)
    return _strip(docs[0]) if docs else None


@router.get("/incidents/{incident_id}/finance/fuel-price-profiles/{profile_id}")
def get_fuel_price_profile(incident_id: str, profile_id: int) -> Dict[str, Any]:
    repo = _fuel_price_repo(incident_id)
    return _strip(_require(repo, incident_id, profile_id, "Fuel price profile"))


@router.post("/incidents/{incident_id}/finance/fuel-price-profiles/{profile_id}/activate")
def set_active_fuel_price_profile(incident_id: str, profile_id: int) -> None:
    repo = _fuel_price_repo(incident_id)
    _require(repo, incident_id, profile_id, "Fuel price profile")
    for doc in repo.find_many({"incident_id": incident_id, "is_active": True}):
        repo.update_one(doc["_id"], {"is_active": False})
    target = repo.find_one({"int_id": profile_id, "incident_id": incident_id})
    repo.update_one(target["_id"], {"is_active": True})


# ===========================================================================
# Forecasts + fuel forecast lines
# ===========================================================================

class ForecastBody(BaseModel):
    operational_period_id: Optional[str] = None
    forecast_name: str
    forecast_type: str = "Fuel"
    category: str = "Fuel"
    notes: Optional[str] = None
    created_by: Optional[str] = None


def _refresh_forecast_totals(incident_id: str, forecast_id: int) -> None:
    lines_repo = _fuel_lines_repo(incident_id)
    lines = lines_repo.find_many({"forecast_id": forecast_id})
    gallons = sum(l.get("estimated_gallons", 0) for l in lines)
    cost = sum(l.get("estimated_cost", 0) for l in lines)
    forecasts_repo = _forecasts_repo(incident_id)
    doc = forecasts_repo.find_one({"int_id": forecast_id, "incident_id": incident_id})
    if doc:
        forecasts_repo.update_one(doc["_id"], {"total_estimated_gallons": gallons, "total_estimated_cost": cost})


@router.get("/incidents/{incident_id}/finance/forecasts")
def list_forecasts(incident_id: str) -> List[Dict[str, Any]]:
    repo = _forecasts_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("created_at", -1), ("int_id", -1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/forecasts", status_code=201)
def create_forecast(incident_id: str, body: ForecastBody) -> Dict[str, Any]:
    repo = _forecasts_repo(incident_id)
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        **body.model_dump(),
        "status": "Draft",
        "total_estimated_cost": 0.0,
        "total_estimated_gallons": 0.0,
        "created_at": _utcnow(),
        "submitted_at": None,
        "approved_by": None,
        "approved_at": None,
    })
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/forecasts/{forecast_id}")
def get_forecast(incident_id: str, forecast_id: int) -> Dict[str, Any]:
    repo = _forecasts_repo(incident_id)
    return _strip(_require(repo, incident_id, forecast_id, "Forecast"))


class FuelForecastLineBody(BaseModel):
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: str
    fuel_type: str
    quantity: int = 1
    estimated_miles_per_resource: Optional[float] = None
    estimated_mpg: Optional[float] = None
    estimated_hours: Optional[float] = None
    gallons_per_hour: Optional[float] = None
    fuel_price: float
    linked_task_id: Optional[str] = None
    notes: Optional[str] = None


@router.post("/incidents/{incident_id}/finance/forecasts/{forecast_id}/fuel-lines", status_code=201)
def add_fuel_forecast_line(incident_id: str, forecast_id: int, body: FuelForecastLineBody) -> Dict[str, Any]:
    forecasts_repo = _forecasts_repo(incident_id)
    _require(forecasts_repo, incident_id, forecast_id, "Forecast")

    total_miles = (body.estimated_miles_per_resource or 0) * body.quantity
    gallons_from_miles = total_miles / body.estimated_mpg if body.estimated_mpg else 0
    gallons_from_hours = (body.estimated_hours or 0) * (body.gallons_per_hour or 0)
    gallons = gallons_from_miles if gallons_from_miles > 0 else gallons_from_hours
    cost = gallons * body.fuel_price

    lines_repo = _fuel_lines_repo(incident_id)
    doc = lines_repo.insert_one({
        "int_id": _next_int_id(lines_repo),
        "forecast_id": forecast_id,
        **body.model_dump(),
        "estimated_total_miles": total_miles,
        "estimated_gallons": gallons,
        "estimated_cost": cost,
    })
    _refresh_forecast_totals(incident_id, forecast_id)
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/forecasts/{forecast_id}/fuel-lines")
def list_fuel_forecast_lines(incident_id: str, forecast_id: int) -> List[Dict[str, Any]]:
    forecasts_repo = _forecasts_repo(incident_id)
    _require(forecasts_repo, incident_id, forecast_id, "Forecast")
    lines_repo = _fuel_lines_repo(incident_id)
    docs = lines_repo.find_many({"forecast_id": forecast_id}, sort=[("int_id", 1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/forecasts/{forecast_id}/submit")
def submit_forecast(incident_id: str, forecast_id: int, approver_role: Optional[str] = None) -> None:
    repo = _forecasts_repo(incident_id)
    doc = _require(repo, incident_id, forecast_id, "Forecast")
    now = _utcnow()
    repo.update_one(doc["_id"], {"status": "Submitted", "submitted_at": now})
    _record_approval(incident_id, "forecast", forecast_id, "Submitted", approver_role=approver_role, timestamp=now)


@router.post("/incidents/{incident_id}/finance/forecasts/{forecast_id}/approve")
def approve_forecast(incident_id: str, forecast_id: int, approved_by: Optional[str] = None, comments: Optional[str] = None) -> None:
    repo = _forecasts_repo(incident_id)
    doc = _require(repo, incident_id, forecast_id, "Forecast")
    now = _utcnow()
    repo.update_one(doc["_id"], {"status": "Approved", "approved_by": approved_by, "approved_at": now})
    _record_approval(incident_id, "forecast", forecast_id, "Approved", approver_id=approved_by, comments=comments, timestamp=now)


# ===========================================================================
# Funding sources
# ===========================================================================

class FundingSourceBody(BaseModel):
    name: str
    code: Optional[str] = None
    type: str = "Unknown"
    agency: Optional[str] = None
    starting_balance: Optional[float] = None
    current_balance: Optional[float] = None
    notes: Optional[str] = None
    is_active: bool = True


@router.get("/incidents/{incident_id}/finance/funding-sources")
def list_funding_sources(incident_id: str) -> List[Dict[str, Any]]:
    repo = _funding_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("name", 1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/funding-sources", status_code=201)
def create_funding_source(incident_id: str, body: FundingSourceBody) -> Dict[str, Any]:
    repo = _funding_repo(incident_id)
    doc = repo.insert_one({"int_id": _next_int_id(repo), "incident_id": incident_id, **body.model_dump()})
    return _strip(doc)


# ===========================================================================
# Expenses
# ===========================================================================

class ExpenseBody(BaseModel):
    operational_period_id: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    description: str
    vendor: Optional[str] = None
    expense_datetime: str
    amount_subtotal: float
    amount_tax: float = 0
    amount_tip: float = 0
    payment_method: Optional[str] = None
    funding_source_id: Optional[int] = None
    entered_by: Optional[str] = None
    notes: Optional[str] = None
    linked_forecast_id: Optional[int] = None
    receipt_attached: bool = False


class ExpenseUpdateBody(BaseModel):
    status: Optional[str] = None
    approved_by: Optional[str] = None
    notes: Optional[str] = None
    receipt_attached: Optional[bool] = None


@router.get("/incidents/{incident_id}/finance/expenses")
def list_expenses(incident_id: str) -> List[Dict[str, Any]]:
    repo = _expenses_repo(incident_id)
    docs = repo.find_many({"incident_id": incident_id}, sort=[("expense_datetime", -1), ("int_id", -1)])
    return [_strip(d) for d in docs]


@router.post("/incidents/{incident_id}/finance/expenses", status_code=201)
def create_expense(incident_id: str, body: ExpenseBody) -> Dict[str, Any]:
    if body.linked_forecast_id is not None:
        _require(_forecasts_repo(incident_id), incident_id, body.linked_forecast_id, "Forecast")
    repo = _expenses_repo(incident_id)
    count = repo.count({"incident_id": incident_id})
    expense_number = f"EXP-{count + 1:04d}"
    total = body.amount_subtotal + body.amount_tax + body.amount_tip
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        **body.model_dump(),
        "expense_number": expense_number,
        "amount_total": total,
        "status": "Draft",
        "entered_at": _utcnow(),
        "submitted_at": None,
        "approved_by": None,
        "approved_at": None,
        "paid_at": None,
    })
    return _strip(doc)


@router.get("/incidents/{incident_id}/finance/expenses/{expense_id}")
def get_expense(incident_id: str, expense_id: int) -> Dict[str, Any]:
    repo = _expenses_repo(incident_id)
    return _strip(_require(repo, incident_id, expense_id, "Expense"))


@router.patch("/incidents/{incident_id}/finance/expenses/{expense_id}")
def update_expense(incident_id: str, expense_id: int, body: ExpenseUpdateBody) -> Dict[str, Any]:
    repo = _expenses_repo(incident_id)
    doc = _require(repo, incident_id, expense_id, "Expense")
    fields = body.model_dump(exclude_none=True)
    if fields:
        repo.update_one(doc["_id"], fields)
    return _strip(repo.find_by_id(doc["_id"]))


@router.post("/incidents/{incident_id}/finance/expenses/{expense_id}/submit")
def submit_expense(incident_id: str, expense_id: int, approver_role: Optional[str] = None) -> None:
    repo = _expenses_repo(incident_id)
    doc = _require(repo, incident_id, expense_id, "Expense")
    now = _utcnow()
    repo.update_one(doc["_id"], {"status": "Submitted", "submitted_at": now})
    _record_approval(incident_id, "expense", expense_id, "Submitted", approver_role=approver_role, timestamp=now)


@router.post("/incidents/{incident_id}/finance/expenses/{expense_id}/approve")
def approve_expense(incident_id: str, expense_id: int, approved_by: Optional[str] = None, comments: Optional[str] = None) -> None:
    repo = _expenses_repo(incident_id)
    doc = _require(repo, incident_id, expense_id, "Expense")
    now = _utcnow()
    repo.update_one(doc["_id"], {"status": "Approved", "approved_by": approved_by, "approved_at": now})
    _record_approval(incident_id, "expense", expense_id, "Approved", approver_id=approved_by, comments=comments, timestamp=now)


class ExpenseStatusBody(BaseModel):
    status: str
    actor: Optional[str] = None
    comments: Optional[str] = None


@router.post("/incidents/{incident_id}/finance/expenses/{expense_id}/status")
def mark_expense_status(incident_id: str, expense_id: int, body: ExpenseStatusBody) -> None:
    repo = _expenses_repo(incident_id)
    doc = _require(repo, incident_id, expense_id, "Expense")
    now = _utcnow()
    updates: Dict[str, Any] = {"status": body.status}
    if body.status == "Paid/Reimbursed":
        updates["paid_at"] = now
    elif body.status in {"Returned for Information", "Denied", "Cancelled", "Closed"}:
        if not doc.get("approved_at"):
            updates["approved_at"] = now
    repo.update_one(doc["_id"], updates)
    _record_approval(incident_id, "expense", expense_id, body.status, approver_id=body.actor, comments=body.comments, timestamp=now)


# ===========================================================================
# Attachments + approvals (generic, by record_type/record_id)
# ===========================================================================

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
    if body.record_type == "expense":
        _require(_expenses_repo(incident_id), incident_id, body.record_id, "Expense")
    elif body.record_type == "forecast":
        _require(_forecasts_repo(incident_id), incident_id, body.record_id, "Forecast")

    repo = _attachments_repo(incident_id)
    doc = repo.insert_one({
        "int_id": _next_int_id(repo),
        "incident_id": incident_id,
        **body.model_dump(),
        "uploaded_at": _utcnow(),
    })

    if body.record_type == "expense":
        expenses_repo = _expenses_repo(incident_id)
        existing = expenses_repo.find_one({"int_id": body.record_id, "incident_id": incident_id})
        if existing:
            expenses_repo.update_one(existing["_id"], {"receipt_attached": True})

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
    if body.record_type == "expense":
        _require(_expenses_repo(incident_id), incident_id, body.record_id, "Expense")
    elif body.record_type == "forecast":
        _require(_forecasts_repo(incident_id), incident_id, body.record_id, "Forecast")

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
# Reporting — Python-side aggregation (no Mongo equivalent to the old SQL
# joins/CTEs; these read the full incident-scoped collections and aggregate
# in memory, which is fine at incident-scoped data volumes).
# ===========================================================================

@router.get("/incidents/{incident_id}/finance/dashboard")
def get_dashboard_snapshot(incident_id: str) -> Dict[str, Any]:
    forecasts = _forecasts_repo(incident_id).find_many({"incident_id": incident_id})
    expenses = _expenses_repo(incident_id).find_many({"incident_id": incident_id})

    total_forecast_cost = sum(f.get("total_estimated_cost", 0) for f in forecasts)
    total_actual_cost = sum(e.get("amount_total", 0) for e in expenses)
    fuel_forecast_cost = sum(f.get("total_estimated_cost", 0) for f in forecasts if f.get("category") == "Fuel")
    fuel_actual_cost = sum(e.get("amount_total", 0) for e in expenses if e.get("category") == "Fuel")
    pending_approvals = (
        sum(1 for f in forecasts if f.get("status") == "Submitted")
        + sum(1 for e in expenses if e.get("status") == "Submitted")
    )
    missing_receipts = sum(1 for e in expenses if not e.get("receipt_attached"))

    return {
        "total_forecast_cost": total_forecast_cost,
        "total_actual_cost": total_actual_cost,
        "fuel_forecast_cost": fuel_forecast_cost,
        "fuel_actual_cost": fuel_actual_cost,
        "pending_approvals": pending_approvals,
        "missing_receipts": missing_receipts,
        "forecast_count": len(forecasts),
        "expense_count": len(expenses),
    }


@router.get("/incidents/{incident_id}/finance/fuel-report")
def get_fuel_report(incident_id: str) -> List[Dict[str, Any]]:
    forecasts = {f["int_id"]: f for f in _forecasts_repo(incident_id).find_many({"incident_id": incident_id})}
    all_lines = _fuel_lines_repo(incident_id).find_many({})
    expenses = _expenses_repo(incident_id).find_many({
        "incident_id": incident_id,
        "category": "Fuel",
        "linked_forecast_id": {"$ne": None},
    })

    expense_totals: Dict[int, float] = {}
    for e in expenses:
        fid = e.get("linked_forecast_id")
        expense_totals[fid] = expense_totals.get(fid, 0) + e.get("amount_total", 0)

    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for line in all_lines:
        fid = line.get("forecast_id")
        if fid in forecasts:
            grouped.setdefault(fid, []).append(line)

    rows = []
    for fid, lines in grouped.items():
        forecast = forecasts[fid]
        resource_names = {l.get("resource_name") for l in lines}
        fuel_types = {l.get("fuel_type") for l in lines}
        estimated_gallons = sum(l.get("estimated_gallons", 0) for l in lines)
        estimated_cost = sum(l.get("estimated_cost", 0) for l in lines)
        actual_cost = expense_totals.get(fid, 0)
        rows.append({
            "forecast_name": forecast.get("forecast_name", ""),
            "resource_name": next(iter(resource_names)) if len(resource_names) == 1 else "Multiple resources",
            "fuel_type": next(iter(fuel_types)) if len(fuel_types) == 1 else "Mixed",
            "estimated_gallons": estimated_gallons,
            "estimated_cost": estimated_cost,
            "actual_cost": actual_cost,
            "variance": actual_cost - estimated_cost,
        })
    rows.sort(key=lambda r: r["forecast_name"])
    return rows


@router.get("/incidents/{incident_id}/finance/pending-approvals")
def list_pending_approvals(incident_id: str) -> List[Dict[str, Any]]:
    forecasts = _forecasts_repo(incident_id).find_many({"incident_id": incident_id, "status": "Submitted"})
    expenses = _expenses_repo(incident_id).find_many({"incident_id": incident_id, "status": "Submitted"})

    rows = [
        {
            "record_type": "forecast",
            "record_id": f["int_id"],
            "description": f.get("forecast_name", ""),
            "amount": f.get("total_estimated_cost", 0),
            "submitted_at": f.get("submitted_at"),
            "status": f.get("status"),
        }
        for f in forecasts
    ] + [
        {
            "record_type": "expense",
            "record_id": e["int_id"],
            "description": e.get("description", ""),
            "amount": e.get("amount_total", 0),
            "submitted_at": e.get("submitted_at"),
            "status": e.get("status"),
        }
        for e in expenses
    ]
    rows.sort(key=lambda r: r["submitted_at"] or "", reverse=True)
    return rows
