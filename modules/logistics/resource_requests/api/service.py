"""Service layer for the Logistics Resource Requests module."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from models import database as master_database

from ..models import request as request_model
from ..models.approval import ApprovalRecord
from ..models.audit import AuditRecord
from ..models.enums import ApprovalAction, FulfillmentStatus, Priority, RequestStatus
from ..models.fulfillment import FulfillmentRecord
from ..models.request import ResourceRequest
from ..models.request_item import RequestItem, create_item
from ..models.supplier import Supplier
from . import validators
from .validators import ValidationError

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "migrations" / "0001_init.sql"
)

ENTITY_REQUEST = "resource_request"
ENTITY_ITEM = "resource_request_item"
ENTITY_FULFILLMENT = "resource_fulfillment"
ENTITY_APPROVAL = "resource_request_approval"

ACTION_STATUS_MAP = {
    ApprovalAction.SUBMIT: RequestStatus.SUBMITTED,
    ApprovalAction.REVIEW: RequestStatus.REVIEWED,
    ApprovalAction.APPROVE: RequestStatus.APPROVED,
    ApprovalAction.DENY: RequestStatus.DENIED,
    ApprovalAction.CANCEL: RequestStatus.CANCELLED,
    ApprovalAction.REOPEN: RequestStatus.REVIEWED,
}


class ResourceRequestService:
    """SQLite-backed service implementing the resource request lifecycle."""

    def __init__(self, incident_id: str, db_path: Path):
        self.incident_id = incident_id
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------ database
    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            with open(MIGRATION_PATH, "r", encoding="utf-8") as handle:
                conn.executescript(handle.read())
            conn.commit()

    def _generate_id(self) -> str:
        return uuid.uuid4().hex

    def _fetch_request(self, conn: sqlite3.Connection, request_id: str) -> ResourceRequest:
        row = conn.execute(
            "SELECT * FROM resource_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if not row:
            raise ValidationError(f"Unknown resource request: {request_id}")
        return ResourceRequest.from_row(dict(row))

    def _write_audit_records(
        self,
        conn: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        changes: Dict[str, Dict[str, Optional[str]]],
        actor_id: Optional[str],
    ) -> None:
        if not changes:
            return
        now = request_model.utcnow()
        for field, change in changes.items():
            record = AuditRecord(
                id=self._generate_id(),
                entity_type=entity_type,
                entity_id=entity_id,
                actor_id=actor_id,
                field=field,
                old_value=change.get("old") if change else None,
                new_value=change.get("new") if change else None,
                ts_utc=now,
            )
            conn.execute(
                """
                INSERT INTO audit_log(id, entity_type, entity_id, actor_id, field, old_value, new_value, ts_utc)
                VALUES (:id, :entity_type, :entity_id, :actor_id, :field, :old_value, :new_value, :ts_utc)
                """,
                record.to_row(),
            )

    def _diff(self, before: Dict[str, object], after: Dict[str, object]) -> Dict[str, Dict[str, Optional[str]]]:
        diff: Dict[str, Dict[str, Optional[str]]] = {}
        for key, old_value in before.items():
            new_value = after.get(key)
            if old_value != new_value:
                diff[key] = {
                    "old": None if old_value is None else str(old_value),
                    "new": None if new_value is None else str(new_value),
                }
        return diff

    def _update_request_row(
        self,
        conn: sqlite3.Connection,
        request_id: str,
        updates: Dict[str, object],
    ) -> None:
        if not updates:
            return
        columns = ", ".join(f"{key} = :{key}" for key in updates)
        updates = dict(updates)
        updates["id"] = request_id
        conn.execute(
            f"UPDATE resource_requests SET {columns} WHERE id = :id",
            updates,
        )

    # ----------------------------------------------------------------- CRUD API
    def create_request(self, header: Dict[str, object], items: Iterable[Dict[str, object]]) -> str:
        header = dict(header)
        priority = validators.validate_priority(header["priority"])
        header["priority"] = priority.value
        header.setdefault("status", RequestStatus.DRAFT.value)
        header.setdefault("created_by_id", header.get("created_by_id", "unknown"))
        header.setdefault("created_utc", request_model.utcnow())
        header.setdefault("last_updated_utc", header["created_utc"])

        request_id = header.get("id") or self._generate_id()
        request = request_model.create_from_header(request_id, self.incident_id, header)

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO resource_requests(
                    id, incident_id, title, requesting_section, needed_by_utc, priority, status,
                    created_utc, created_by_id, last_updated_utc, justification, delivery_location,
                    comms_requirements, links, version
                ) VALUES(:id, :incident_id, :title, :requesting_section, :needed_by_utc, :priority, :status,
                    :created_utc, :created_by_id, :last_updated_utc, :justification, :delivery_location,
                    :comms_requirements, :links, :version)
                """,
                request.to_row(),
            )

            for raw_item in items:
                item_id = raw_item.get("id") or self._generate_id()
                item = create_item(item_id, request_id, raw_item)
                self._insert_item(conn, item)

            self._write_audit_records(
                conn,
                ENTITY_REQUEST,
                request_id,
                {
                    "create": {
                        "old": None,
                        "new": json.dumps({"title": request.title, "priority": request.priority.value}),
                    }
                },
                actor_id=request.created_by_id,
            )
        return request_id

    def update_request(self, request_id: str, patch: Dict[str, object]) -> None:
        patch = dict(patch)
        actor_id = patch.pop("actor_id", None)
        if not patch:
            return

        with self.connection() as conn:
            request = self._fetch_request(conn, request_id)
            validators.ensure_edit_allowed(request.status)
            validators.ensure_post_submission_edit_allowed(request.status, patch.keys())

            updates: Dict[str, object] = {}
            for field, value in patch.items():
                if field == "priority":
                    priority = validators.validate_priority(value)
                    updates["priority"] = priority.value
                elif field == "status":
                    raise ValidationError("Use change_status to update the workflow status")
                else:
                    updates[field] = value

            updates["last_updated_utc"] = request_model.utcnow()
            if request.status != RequestStatus.DRAFT:
                updates["version"] = request.version + 1

            before = request.to_row()
            after = dict(before)
            after.update(updates)

            self._update_request_row(conn, request_id, updates)
            self._write_audit_records(
                conn,
                ENTITY_REQUEST,
                request_id,
                self._diff(before, after),
                actor_id,
            )

    def add_items(self, request_id: str, items: Iterable[Dict[str, object]]) -> List[str]:
        item_ids: List[str] = []
        with self.connection() as conn:
            self._fetch_request(conn, request_id)
            for raw_item in items:
                item_id = raw_item.get("id") or self._generate_id()
                item = create_item(item_id, request_id, raw_item)
                self._insert_item(conn, item)
                item_ids.append(item_id)
                self._write_audit_records(
                    conn,
                    ENTITY_ITEM,
                    request_id,
                    {
                        f"item_create:{item_id}": {
                            "old": None,
                            "new": json.dumps({"description": item.description, "quantity": item.quantity}),
                        }
                    },
                    actor_id=None,
                )
        return item_ids

    def change_status(self, request_id: str, status: str, actor_id: str, note: Optional[str] = None) -> None:
        new_status = validators.validate_status(status)

        with self.connection() as conn:
            request = self._fetch_request(conn, request_id)
            validators.validate_status_transition(request.status, new_status)

            updates: Dict[str, object] = {
                "status": validators.normalise_status_for_transition(request.status, new_status).value,
                "last_updated_utc": request_model.utcnow(),
            }
            if request.status != RequestStatus.DRAFT:
                updates["version"] = request.version + 1

            before = request.to_row()
            after = dict(before)
            after.update(updates)

            self._update_request_row(conn, request_id, updates)
            change_dict = {
                "status": {
                    "old": request.status.value,
                    "new": updates["status"],
                }
            }
            if note:
                change_dict["status_note"] = {"old": None, "new": note}
            self._write_audit_records(
                conn,
                ENTITY_REQUEST,
                request_id,
                change_dict,
                actor_id,
            )

    def record_approval(self, request_id: str, action: str, actor_id: str, note: Optional[str] = None) -> str:
        parsed_action = validators.validate_approval_action(action, note)
        approval_id = self._generate_id()
        now = request_model.utcnow()

        with self.connection() as conn:
            self._fetch_request(conn, request_id)
            record = ApprovalRecord(
                id=approval_id,
                request_id=request_id,
                action=parsed_action,
                actor_id=actor_id,
                note=note,
                ts_utc=now,
            )
            conn.execute(
                """
                INSERT INTO resource_request_approvals(id, request_id, action, actor_id, note, ts_utc)
                VALUES(:id, :request_id, :action, :actor_id, :note, :ts_utc)
                """,
                record.to_row(),
            )
            self._write_audit_records(
                conn,
                ENTITY_APPROVAL,
                request_id,
                {
                    f"approval:{approval_id}": {
                        "old": None,
                        "new": parsed_action.value,
                    }
                },
                actor_id,
            )

        target_status = ACTION_STATUS_MAP.get(parsed_action)
        if target_status:
            self.change_status(request_id, target_status.value, actor_id, note=note)
        return approval_id

    def assign_fulfillment(
        self,
        request_id: str,
        supplier_id: Optional[str] = None,
        team_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        eta_utc: Optional[str] = None,
        note: Optional[str] = None,
    ) -> str:
        with self.connection() as conn:
            request = self._fetch_request(conn, request_id)
            status = (
                FulfillmentStatus.ASSIGNED
                if any([supplier_id, team_id, vehicle_id])
                else FulfillmentStatus.SOURCING
            )
            fulfillment_id = self._generate_id()
            record = FulfillmentRecord(
                id=fulfillment_id,
                request_id=request_id,
                supplier_id=supplier_id,
                assigned_team_id=team_id,
                assigned_vehicle_id=vehicle_id,
                eta_utc=eta_utc,
                status=status,
                note=note,
                ts_utc=request_model.utcnow(),
            )
            conn.execute(
                """
                INSERT INTO resource_fulfillments(id, request_id, supplier_id, assigned_team_id, assigned_vehicle_id, eta_utc, status, note, ts_utc)
                VALUES(:id, :request_id, :supplier_id, :assigned_team_id, :assigned_vehicle_id, :eta_utc, :status, :note, :ts_utc)
                """,
                record.to_row(),
            )
            self._write_audit_records(
                conn,
                ENTITY_FULFILLMENT,
                request_id,
                {
                    f"fulfillment_create:{fulfillment_id}": {
                        "old": None,
                        "new": json.dumps({"status": record.status.value}),
                    }
                },
                actor_id=None,
            )
        return fulfillment_id

    def update_fulfillment(
        self,
        fulfillment_id: str,
        status: str,
        note: Optional[str] = None,
        eta_utc: Optional[str] = None,
    ) -> None:
        parsed_status = validators.validate_fulfillment_status(status)
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM resource_fulfillments WHERE id = ?", (fulfillment_id,)
            ).fetchone()
            if not row:
                raise ValidationError(f"Unknown fulfillment record: {fulfillment_id}")
            updates: Dict[str, object] = {
                "status": parsed_status.value,
                "note": note,
                "eta_utc": eta_utc,
                "ts_utc": request_model.utcnow(),
            }
            before = row
            after = dict(row)
            after.update(updates)
            conn.execute(
                """
                UPDATE resource_fulfillments
                SET status = :status, note = :note, eta_utc = :eta_utc, ts_utc = :ts_utc
                WHERE id = :id
                """,
                {"id": fulfillment_id, **updates},
            )
            self._write_audit_records(
                conn,
                ENTITY_FULFILLMENT,
                row["request_id"],
                self._diff(dict(before), after),
                actor_id=None,
            )

    def list_requests(self, filters: Dict[str, object]) -> List[Dict[str, object]]:
        clauses = ["incident_id = :incident_id"]
        params: Dict[str, object] = {"incident_id": self.incident_id}

        status_filter = filters.get("status")
        if status_filter:
            if isinstance(status_filter, str):
                status_values = [validators.validate_status(status_filter).value]
            else:
                status_values = [validators.validate_status(value).value for value in status_filter]
            placeholders = ",".join(f":status_{i}" for i, _ in enumerate(status_values))
            clauses.append(f"status IN ({placeholders})")
            params.update({f"status_{i}": value for i, value in enumerate(status_values)})

        priority = filters.get("priority")
        if priority:
            clauses.append("priority = :priority")
            params["priority"] = validators.validate_priority(priority).value

        text = filters.get("text")
        if text:
            clauses.append("(title LIKE :text OR justification LIKE :text)")
            params["text"] = f"%{text}%"

        start = filters.get("start")
        if start:
            clauses.append("created_utc >= :start")
            params["start"] = start
        end = filters.get("end")
        if end:
            clauses.append("created_utc <= :end")
            params["end"] = end

        sql = "SELECT * FROM resource_requests WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_utc DESC"

        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def get_request(self, request_id: str) -> Dict[str, object]:
        with self.connection() as conn:
            request = self._fetch_request(conn, request_id)

            items = [
                RequestItem.from_row(dict(row)).to_row()
                for row in conn.execute(
                    "SELECT * FROM resource_request_items WHERE request_id = ?",
                    (request_id,),
                )
            ]
            approvals = [
                ApprovalRecord.from_row(dict(row)).to_row()
                for row in conn.execute(
                    "SELECT * FROM resource_request_approvals WHERE request_id = ? ORDER BY ts_utc",
                    (request_id,),
                )
            ]
            fulfillments = [
                FulfillmentRecord.from_row(dict(row)).to_row()
                for row in conn.execute(
                    "SELECT * FROM resource_fulfillments WHERE request_id = ? ORDER BY ts_utc",
                    (request_id,),
                )
            ]
            audit = [
                AuditRecord.from_row(dict(row)).to_row()
                for row in conn.execute(
                    "SELECT * FROM audit_log WHERE entity_id = ? ORDER BY ts_utc",
                    (request_id,),
                )
            ]

        result = request.to_row()
        result["items"] = items
        result["approvals"] = approvals
        result["fulfillments"] = fulfillments
        result["audit"] = audit
        return result

    # ---------------------------------------------------------------- suppliers
    def list_suppliers(self) -> List[Supplier]:
        conn = master_database.get_connection()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
            return [Supplier.from_row(dict(row)) for row in rows]
        finally:
            conn.close()

    # ----------------------------------------------------------- item helpers
    def _insert_item(self, conn: sqlite3.Connection, item: RequestItem) -> None:
        conn.execute(
            """
            INSERT INTO resource_request_items(id, request_id, kind, ref_id, description, quantity, unit, special_instructions)
            VALUES(:id, :request_id, :kind, :ref_id, :description, :quantity, :unit, :special_instructions)
            """,
            item.to_row(),
        )

    def replace_items(self, request_id: str, items: Iterable[Dict[str, object]]) -> None:
        with self.connection() as conn:
            self._fetch_request(conn, request_id)
            conn.execute("DELETE FROM resource_request_items WHERE request_id = ?", (request_id,))
            summary = []
            for raw_item in items:
                item_id = raw_item.get("id") or self._generate_id()
                item = create_item(item_id, request_id, raw_item)
                self._insert_item(conn, item)
                summary.append({"id": item.id, "description": item.description, "quantity": item.quantity})

            self._write_audit_records(
                conn,
                ENTITY_ITEM,
                request_id,
                {
                    "items": {
                        "old": "replaced",
                        "new": json.dumps(summary),
                    }
                },
                actor_id=None,
            )
