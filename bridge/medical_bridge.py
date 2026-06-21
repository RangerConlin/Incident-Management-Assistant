"""Bridge layer exposing ICS 206 data to Qt widgets."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Sequence

from PySide6.QtCore import QObject, Signal
from modules.medical.data.mongo_access import get_incident_db, get_master_db, strip_mongo_id
from utils.incident_context import get_active_incident_id
from utils.state import AppState

TABLE_FIELDS: Dict[str, Sequence[str]] = {
    "aid_stations": ["id", "op_period", "name", "type", "level", "is_24_7", "notes"],
    "ambulance_services": [
        "id",
        "op_period",
        "name",
        "type",
        "phone",
        "location",
        "notes",
    ],
    "hospitals": [
        "id",
        "op_period",
        "name",
        "address",
        "phone",
        "helipad",
        "burn_center",
        "level",
        "notes",
    ],
    "air_ambulance": [
        "id",
        "op_period",
        "name",
        "phone",
        "base",
        "contact",
        "notes",
    ],
    "medical_comms": [
        "id",
        "op_period",
        "channel",
        "function",
        "frequency",
        "mode",
        "notes",
    ],
    "procedures": ["id", "op_period", "content"],
    "ics206_signatures": [
        "id",
        "op_period",
        "prepared_by",
        "position",
        "approved_by",
        "date",
    ],
}

COLLECTIONS = {
    "aid_stations": "ics_206_aid_stations",
    "ambulance_services": "ics_206_ambulance_services",
    "hospitals": "ics_206_hospitals",
    "air_ambulance": "ics_206_air_ambulance",
    "medical_comms": "ics_206_medical_comms",
    "procedures": "ics_206_procedures",
    "ics206_signatures": "ics_206_signatures",
}


class MedicalBridge(QObject):
    """MongoDB helper used by :class:`modules.medical.panels.ics206_panel.ICS206Panel`."""

    data_changed = Signal(str)
    toast = Signal(str)

    def _incident_id(self) -> str:
        incident_id = get_active_incident_id()
        if incident_id:
            return str(incident_id)
        inc = AppState.get_active_incident()
        if inc:
            return str(inc)
        raise RuntimeError("No active incident selected")

    def _op_period(self) -> int:
        op = AppState.get_active_op_period()
        if op is None:
            raise RuntimeError("No active operational period selected")
        return int(op)

    def _db(self):
        return get_incident_db(self._incident_id())

    def _master_db(self):
        return get_master_db()

    def _collection(self, table: str):
        return self._db()[COLLECTIONS[table]]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def ensure_ics206_tables(self) -> None:
        """Verify Mongo indexes for the active incident."""
        db = self._db()
        incident_id = self._incident_id()
        for table in (
            "aid_stations",
            "ambulance_services",
            "hospitals",
            "air_ambulance",
            "medical_comms",
        ):
            col = db[COLLECTIONS[table]]
            col.create_index([("incident_id", 1), ("op_period", 1)])
            col.create_index([("id", 1)], unique=True)
            col.create_index([("deleted", 1)])
        db[COLLECTIONS["procedures"]].create_index(
            [("incident_id", 1), ("op_period", 1)], unique=True
        )
        db[COLLECTIONS["ics206_signatures"]].create_index(
            [("incident_id", 1), ("op_period", 1)], unique=True
        )
        # Touch the database so connection issues surface during panel startup.
        db.command("ping")
        if not incident_id:
            raise RuntimeError("No active incident selected")

    def _base_query(self, op_period: int | None = None) -> dict[str, Any]:
        return {
            "incident_id": self._incident_id(),
            "op_period": self._op_period() if op_period is None else int(op_period),
            "deleted": {"$ne": True},
        }

    def _next_id(self, table: str) -> int:
        row = self._collection(table).find_one(sort=[("id", -1)], projection={"id": 1})
        return int(row["id"]) + 1 if row and row.get("id") is not None else 1

    def _clean_doc(self, table: str, document: Mapping[str, Any]) -> dict[str, Any]:
        fields = TABLE_FIELDS[table]
        return {field: document.get(field) for field in fields}

    def list_table(self, table: str) -> List[Dict[str, Any]]:
        rows = self._collection(table).find(self._base_query()).sort("id", 1)
        return [self._clean_doc(table, strip_mongo_id(row) or {}) for row in rows]

    def add_record(self, table: str, data: Dict[str, Any]) -> int:
        now = self._now()
        row_id = self._next_id(table)
        fields = [c for c in TABLE_FIELDS[table] if c not in ("id", "op_period")]
        doc = {
            "id": row_id,
            "incident_id": self._incident_id(),
            "op_period": self._op_period(),
            "deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        doc.update({field: data.get(field) for field in fields})
        self._collection(table).insert_one(doc)
        self.data_changed.emit(table)
        return row_id

    def update_record(self, table: str, id_value: int, data: Dict[str, Any]) -> bool:
        updates = {
            key: value
            for key, value in data.items()
            if key in TABLE_FIELDS[table] and key not in ("id", "op_period")
        }
        if not updates:
            return False
        updates["updated_at"] = self._now()
        result = self._collection(table).update_one(
            {"id": int(id_value), "incident_id": self._incident_id()},
            {"$set": updates},
        )
        self.data_changed.emit(table)
        return result.matched_count > 0

    def delete_record(self, table: str, id_value: int) -> bool:
        result = self._collection(table).update_one(
            {"id": int(id_value), "incident_id": self._incident_id()},
            {"$set": {"deleted": True, "updated_at": self._now()}},
        )
        self.data_changed.emit(table)
        return result.matched_count > 0

    def get_procedures(self) -> str:
        row = self._collection("procedures").find_one(self._base_query())
        return str(row.get("content") or "") if row else ""

    def save_procedures(self, text: str) -> None:
        self._collection("procedures").update_one(
            {"incident_id": self._incident_id(), "op_period": self._op_period()},
            {
                "$set": {
                    "content": text,
                    "deleted": False,
                    "updated_at": self._now(),
                },
                "$setOnInsert": {
                    "id": self._next_id("procedures"),
                    "created_at": self._now(),
                },
            },
            upsert=True,
        )
        self.data_changed.emit("procedures")

    def get_signatures(self) -> Dict[str, Any]:
        row = self._collection("ics206_signatures").find_one(self._base_query())
        if not row:
            return {}
        return {
            "prepared_by": row.get("prepared_by"),
            "position": row.get("position"),
            "approved_by": row.get("approved_by"),
            "date": row.get("date"),
        }

    def save_signatures(self, data: Dict[str, Any]) -> None:
        now = self._now()
        self._collection("ics206_signatures").update_one(
            {"incident_id": self._incident_id(), "op_period": self._op_period()},
            {
                "$set": {
                    "prepared_by": data.get("prepared_by"),
                    "position": data.get("position"),
                    "approved_by": data.get("approved_by"),
                    "date": data.get("date"),
                    "deleted": False,
                    "updated_at": now,
                },
                "$setOnInsert": {"id": self._next_id("ics206_signatures"), "created_at": now},
            },
            upsert=True,
        )
        self.data_changed.emit("ics206_signatures")

    def _import_master_rows(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = self._master_db()[collection].find(query or {"deleted": {"$ne": True}})
        return [strip_mongo_id(row) or {} for row in rows]

    def import_aid_stations(self) -> int:
        rows = self._import_master_rows("ems_agencies", {"type": "Medical Aid", "is_active": {"$ne": False}})
        for row in rows:
            self.add_record(
                "aid_stations",
                {
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "level": "",
                    "is_24_7": 0,
                    "notes": row.get("notes"),
                },
            )
        return len(rows)

    def import_ambulance_services(self) -> int:
        rows = self._import_master_rows(
            "ems_agencies",
            {"type": {"$in": ["Ambulance", "Air Ambulance"]}, "is_active": {"$ne": False}},
        )
        for row in rows:
            self.add_record(
                "ambulance_services",
                {
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "phone": row.get("phone"),
                    "location": row.get("address"),
                    "notes": row.get("notes"),
                },
            )
        return len(rows)

    def import_hospitals(self) -> int:
        rows = self._import_master_rows("hospitals", {"deleted": {"$ne": True}})
        for row in rows:
            self.add_record(
                "hospitals",
                {
                    "name": row.get("name"),
                    "address": row.get("address"),
                    "phone": row.get("phone") or row.get("phone_er") or row.get("phone_switchboard"),
                    "helipad": 1 if row.get("helipad") else 0,
                    "burn_center": 1 if row.get("burn_center") else 0,
                    "level": row.get("trauma_level") or row.get("level") or "",
                    "notes": row.get("notes"),
                },
            )
        return len(rows)

    def import_air_ambulance(self) -> int:
        rows = self._import_master_rows("ems_agencies", {"type": "Air Ambulance", "is_active": {"$ne": False}})
        for row in rows:
            self.add_record(
                "air_ambulance",
                {
                    "name": row.get("name"),
                    "phone": row.get("phone"),
                    "base": row.get("address"),
                    "contact": row.get("contact") or row.get("contact_name"),
                    "notes": row.get("notes"),
                },
            )
        return len(rows)

    def import_medical_comms(self) -> int:
        rows = self._import_master_rows("radio_channels", {"deleted": {"$ne": True}})
        for row in rows:
            self.add_record(
                "medical_comms",
                {
                    "channel": row.get("alpha_tag") or row.get("channel_name"),
                    "function": row.get("function"),
                    "frequency": row.get("freq_rx") or row.get("frequency"),
                    "mode": row.get("mode"),
                    "notes": row.get("notes"),
                },
            )
        return len(rows)

    def duplicate_last_op(self) -> bool:
        cur_op = self._op_period()
        row = self._collection("aid_stations").find_one(
            {
                "incident_id": self._incident_id(),
                "op_period": {"$lt": cur_op},
                "deleted": {"$ne": True},
            },
            sort=[("op_period", -1)],
        )
        if not row:
            return False
        prev = int(row["op_period"])
        now = self._now()
        for table, fields in TABLE_FIELDS.items():
            for source in self._collection(table).find(
                {"incident_id": self._incident_id(), "op_period": prev, "deleted": {"$ne": True}}
            ):
                doc = {field: source.get(field) for field in fields if field not in ("id", "op_period")}
                doc.update(
                    {
                        "id": self._next_id(table),
                        "incident_id": self._incident_id(),
                        "op_period": cur_op,
                        "deleted": False,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                self._collection(table).insert_one(doc)
        self.data_changed.emit("all")
        return True
