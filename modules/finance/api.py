from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import List

from modules.finance import services
from modules.finance.models.schemas import (
    VendorRead, LaborRateRead, EquipmentRateRead, AccountRead,
    TimeEntryCreate, TimeEntryUpdate, RequisitionCreate, POCreate,
    ReceiptCreate, InvoiceCreate, InvoiceUpdate, CostEntryCreate,
    BudgetCreate, DailyCostFinalizeRequest, ClaimCreate, ClaimUpdate,
    ReportRequest, ExportArtifactRead,
)

router = APIRouter(prefix="/api/finance", tags=["finance"])

# Lookups --------------------------------------------------------------------

@router.get("/lookups/vendors", response_model=List[VendorRead])
def lookup_vendors():
    return services.list_vendors()


@router.get("/lookups/rates/labor", response_model=List[LaborRateRead])
def lookup_labor_rates():
    return services.list_labor_rates()


@router.get("/lookups/rates/equipment", response_model=List[EquipmentRateRead])
def lookup_equipment_rates():
    return services.list_equipment_rates()


@router.get("/lookups/accounts", response_model=List[AccountRead])
def lookup_accounts():
    return services.list_accounts()

# Time Unit ------------------------------------------------------------------

@router.post("/time", response_model=int)
def create_time_entry(mission_id: str, data: TimeEntryCreate):
    return services.create_time_entry(mission_id, data)


@router.put("/time/{entry_id}")
def update_time_entry(mission_id: str, entry_id: int, data: TimeEntryUpdate):
    services.update_time_entry(mission_id, entry_id, data)
    return {"status": "ok"}


@router.post("/time/{entry_id}/submit")
def submit_time_entry(mission_id: str, entry_id: int):
    services.submit_time_entry(mission_id, entry_id)
    return {"status": "ok"}


@router.post("/time/{entry_id}/approve")
def approve_time_entry(mission_id: str, entry_id: int, approve: bool, actor_id: int):
    services.approve_time_entry(mission_id, entry_id, actor_id, approve)
    return {"status": "ok"}

# Procurement ----------------------------------------------------------------

@router.post("/requisitions", response_model=int)
def create_requisition(mission_id: str, data: RequisitionCreate):
    return services.create_requisition(mission_id, data)


@router.post("/pos", response_model=int)
def create_po(mission_id: str, data: POCreate):
    return services.create_purchase_order(mission_id, data)


@router.post("/pos/{po_id}/receive", response_model=int)
def receive_po(mission_id: str, po_id: int, data: ReceiptCreate):
    data.po_id = po_id
    return services.receive_po(mission_id, data)


@router.post("/invoices", response_model=int)
def create_invoice(mission_id: str, data: InvoiceCreate):
    return services.create_invoice(mission_id, data)


@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(mission_id: str, invoice_id: int):
    services.approve_invoice(mission_id, invoice_id)
    return {"status": "ok"}

# Cost Unit ------------------------------------------------------------------

@router.post("/costs", response_model=int)
def post_cost_entry(mission_id: str, data: CostEntryCreate):
    return services.post_cost_entry(mission_id, data)


@router.post("/budgets", response_model=int)
def create_budget(mission_id: str, data: BudgetCreate):
    return services.create_budget(mission_id, data)


@router.post("/daily/finalize", response_model=int)
def finalize_daily(mission_id: str, data: DailyCostFinalizeRequest):
    return services.finalize_daily_cost_summary(mission_id, data)

# Claims ---------------------------------------------------------------------

@router.post("/claims", response_model=int)
def create_claim(mission_id: str, data: ClaimCreate):
    return services.create_claim(mission_id, data)


@router.put("/claims/{claim_id}")
def update_claim(mission_id: str, claim_id: int, data: ClaimUpdate):
    services.update_claim(mission_id, claim_id, data)
    return {"status": "ok"}

# Exports --------------------------------------------------------------------

@router.post("/exports/report", response_model=ExportArtifactRead)
def export_report(mission_id: str, req: ReportRequest):
    return services.generate_report(mission_id, req)


@router.get("/exports", response_model=List[ExportArtifactRead])
def list_exports(mission_id: str):
    return services.list_exports(mission_id)
