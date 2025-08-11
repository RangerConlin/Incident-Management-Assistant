from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import text

from .repository import with_master_session, with_mission_session
from .rates import resolve_labor_cost, resolve_equipment_cost
from .approvals import get_chain, next_step, record_approval
from .models.schemas import (
    TimeEntryCreate,
    TimeEntryUpdate,
    TimeEntryRead,
    RequisitionCreate,
    RequisitionRead,
    POCreate,
    PORead,
    ReceiptCreate,
    ReceiptRead,
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceRead,
    CostEntryCreate,
    CostEntryRead,
    DailyCostFinalizeRequest,
    BudgetCreate,
    BudgetRead,
    ClaimCreate,
    ClaimUpdate,
    ClaimRead,
    VendorRead,
    LaborRateRead,
    EquipmentRateRead,
    AccountRead,
    ReportRequest,
    ExportArtifactRead,
)
from .exporter import export_daily_cost_summary, list_artifacts

# Lookups -------------------------------------------------------------------

def list_vendors() -> List[VendorRead]:
    with with_master_session() as session:
        rows = session.execute(text("SELECT * FROM vendors")).mappings().all()
        return [VendorRead(**row) for row in rows]


def list_labor_rates() -> List[LaborRateRead]:
    with with_master_session() as session:
        rows = session.execute(text("SELECT * FROM labor_rates")).mappings().all()
        return [LaborRateRead(**row) for row in rows]


def list_equipment_rates() -> List[EquipmentRateRead]:
    with with_master_session() as session:
        rows = session.execute(text("SELECT * FROM equipment_rates")).mappings().all()
        return [EquipmentRateRead(**row) for row in rows]


def list_accounts() -> List[AccountRead]:
    with with_master_session() as session:
        rows = session.execute(text("SELECT * FROM accounts")).mappings().all()
        return [AccountRead(**row) for row in rows]

# Time Unit -----------------------------------------------------------------

def create_time_entry(mission_id: str, data: TimeEntryCreate) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO time_entries (mission_id, person_id, role, op_period, date, hours_worked, overtime_hours, labor_rate_id, equipment_id, notes, status)
                VALUES (:mission_id, :person_id, :role, :op_period, :date, :hours_worked, :overtime_hours, :labor_rate_id, :equipment_id, :notes, 'draft')
                """
            ),
            {"mission_id": mission_id, **data.dict()},
        )
        session.commit()
        return result.lastrowid


def update_time_entry(mission_id: str, entry_id: int, data: TimeEntryUpdate) -> None:
    fields = {k: v for k, v in data.dict().items() if v is not None}
    sets = ", ".join(f"{k}=:{k}" for k in fields)
    with with_mission_session(mission_id) as session:
        session.execute(
            text(f"UPDATE time_entries SET {sets} WHERE id=:id"),
            {"id": entry_id, **fields},
        )
        session.commit()


def submit_time_entry(mission_id: str, entry_id: int) -> None:
    with with_mission_session(mission_id) as session:
        session.execute(
            text("UPDATE time_entries SET status='submitted' WHERE id=:id"),
            {"id": entry_id},
        )
        session.commit()


def approve_time_entry(mission_id: str, entry_id: int, approver_id: int, approve: bool) -> None:
    status = "approved" if approve else "rejected"
    with with_mission_session(mission_id) as session:
        session.execute(
            text(
                "UPDATE time_entries SET status=:status, approved_by=:a, approved_at=:t WHERE id=:id"
            ),
            {"status": status, "a": approver_id, "t": datetime.utcnow(), "id": entry_id},
        )
        session.commit()

# Procurement ----------------------------------------------------------------

def create_requisition(mission_id: str, data: RequisitionCreate) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO requisitions (mission_id, req_number, requestor_id, date, description, amount_est, status, approval_chain_id)
                VALUES (:mission_id, :req_number, :requestor_id, :date, :description, :amount_est, 'draft', :approval_chain_id)
                """
            ),
            {"mission_id": mission_id, **data.dict()},
        )
        session.commit()
        return result.lastrowid


def create_purchase_order(mission_id: str, data: POCreate) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO purchase_orders (mission_id, po_number, vendor_id, req_id, date, amount_auth, status)
                VALUES (:mission_id, :po_number, :vendor_id, :req_id, :date, :amount_auth, 'open')
                """
            ),
            {"mission_id": mission_id, **data.dict()},
        )
        session.commit()
        return result.lastrowid


def receive_po(mission_id: str, data: ReceiptCreate) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO receipts (mission_id, po_id, date, qty, amount, notes)
                VALUES (:mission_id, :po_id, :date, :qty, :amount, :notes)
                """
            ),
            {"mission_id": mission_id, **data.dict()},
        )
        session.commit()
        return result.lastrowid


def create_invoice(mission_id: str, data: InvoiceCreate) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO invoices (mission_id, po_id, vendor_invoice_no, date, amount, status)
                VALUES (:mission_id, :po_id, :vendor_invoice_no, :date, :amount, 'pending')
                """
            ),
            {"mission_id": mission_id, **data.dict()},
        )
        session.commit()
        return result.lastrowid


def approve_invoice(mission_id: str, invoice_id: int) -> None:
    with with_mission_session(mission_id) as session:
        session.execute(
            text("UPDATE invoices SET status='approved' WHERE id=:id"),
            {"id": invoice_id},
        )
        session.commit()

# Cost Unit ------------------------------------------------------------------

def post_cost_entry(mission_id: str, data: CostEntryCreate) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO cost_entries (mission_id, date, account_id, description, amount, source, ref_table, ref_id)
                VALUES (:mission_id, :date, :account_id, :description, :amount, :source, :ref_table, :ref_id)
                """
            ),
            {"mission_id": mission_id, **data.dict()},
        )
        session.commit()
        return result.lastrowid


def create_budget(mission_id: str, data: BudgetCreate) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO budgets (mission_id, account_id, amount_budgeted, notes)
                VALUES (:mission_id, :account_id, :amount_budgeted, :notes)
                """
            ),
            {"mission_id": mission_id, **data.dict()},
        )
        session.commit()
        return result.lastrowid


def finalize_daily_cost_summary(mission_id: str, data: DailyCostFinalizeRequest) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO daily_cost_summary (mission_id, date, total_labor, total_equipment, total_procurement, total_other, notes, finalized_by, finalized_at)
                VALUES (:mission_id, :date, 0, 0, 0, 0, :notes, :fb, :fa)
                """
            ),
            {
                "mission_id": mission_id,
                "date": data.date,
                "notes": data.notes,
                "fb": 0,
                "fa": datetime.utcnow(),
            },
        )
        session.commit()
        return result.lastrowid

# Claims ---------------------------------------------------------------------

def create_claim(mission_id: str, data: ClaimCreate) -> int:
    with with_mission_session(mission_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO claims (mission_id, claim_type, claimant_id, date_reported, description, amount_est, status, attachments_json)
                VALUES (:mission_id, :claim_type, :claimant_id, :date_reported, :description, :amount_est, 'open', :attachments_json)
                """
            ),
            {"mission_id": mission_id, **data.dict()},
        )
        session.commit()
        return result.lastrowid


def update_claim(mission_id: str, claim_id: int, data: ClaimUpdate) -> None:
    fields = {k: v for k, v in data.dict().items() if v is not None}
    sets = ", ".join(f"{k}=:{k}" for k in fields)
    with with_mission_session(mission_id) as session:
        session.execute(
            text(f"UPDATE claims SET {sets} WHERE id=:id"),
            {"id": claim_id, **fields},
        )
        session.commit()

# Exports --------------------------------------------------------------------

def generate_report(mission_id: str, req: ReportRequest) -> ExportArtifactRead:
    with with_mission_session(mission_id) as session:
        if req.report_type == "daily_cost_summary":
            info = export_daily_cost_summary(session, mission_id, req.date.isoformat())
            return ExportArtifactRead(**info)
        raise ValueError("unsupported report type")


def list_exports(mission_id: str) -> List[ExportArtifactRead]:
    artifacts = list_artifacts(mission_id)
    return [ExportArtifactRead(**a) for a in artifacts]
