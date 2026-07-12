"""Bridge layer exposing ICS 206 data to Qt widgets."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Sequence

from PySide6.QtCore import QObject, Signal
from modules.medical.data.mongo_access import get_incident_db, get_master_db, strip_mongo_id
from utils.incident_context import get_active_incident_id
from utils.state import AppState

TABLE_FIELDS: Dict[str, Sequence[str]] = {
    "aid_stations": [
        "id",
        "op_period",
        "facility_id",
        "name",
        "type",
        "level",
        "is_24_7",
        "location_text",
        "latitude",
        "longitude",
        "manager_personnel_id",
        "manager_name",
        "notes",
    ],
    "ambulance_services": [
        "id",
        "op_period",
        "name",
        "type",
        "service_level",
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
        "adult_trauma_level",
        "pediatric_trauma_level",
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


def _service_level_from_row(row: Mapping[str, Any]) -> int:
    raw = row.get("service_level")
    try:
        if raw is not None and raw != "":
            level = int(raw)
            if level in (0, 1, 2):
                return level
    except (TypeError, ValueError):
        pass
    type_value = str(row.get("type") or "").strip().lower()
    if "als" in type_value:
        return 2
    if "bls" in type_value:
        return 1
    return 0


def _trauma_level_int(value: Any) -> int:
    if value in (None, "", 0, "0", False):
        return 0
    if isinstance(value, int):
        return max(0, min(value, 5))
    text = str(value).strip().upper()
    if text in {"I", "1"}:
        return 1
    if text in {"II", "2"}:
        return 2
    if text in {"III", "3"}:
        return 3
    if text in {"IV", "4"}:
        return 4
    if text in {"V", "5"}:
        return 5
    return 0


def _trauma_display(adult_level: int, pediatric_level: int) -> str:
    roman = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
    adult = roman.get(adult_level, "")
    pediatric = roman.get(pediatric_level, "")
    if adult and pediatric:
        return f"A-{adult} / P-{pediatric}"
    if adult:
        return adult
    if pediatric:
        return f"P-{pediatric}"
    return ""

COLLECTIONS = {
    "aid_stations": "ics_206_aid_stations",
    "medical_plan": "medical_plan",
}

PLAN_TABLES = {"ambulance_services", "hospitals", "air_ambulance", "medical_comms"}
PLAN_SINGLE_SECTIONS = {"procedures", "ics206_signatures"}
PLAN_SECTION_FIELD = {"ics206_signatures": "signatures"}


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
        op_data = AppState.get_active_op_period_dict()
        if op_data is None:
            raise RuntimeError("No active operational period selected")
        return int(op_data.get("number") or op_data.get("id") or 0)

    def _db(self):
        return get_incident_db(self._incident_id())

    def _master_db(self):
        return get_master_db()

    def _collection(self, table: str):
        return self._db()[COLLECTIONS[table]]

    def _repository(self, collection_name: str):
        db = self._db()
        from sarapp_db.mongo.repository import BaseRepository

        class MedicalRepository(BaseRepository):
            pass

        MedicalRepository.collection_name = collection_name
        MedicalRepository.soft_deletes = False
        return MedicalRepository(db)

    def _aid_stations_repo(self):
        return self._repository(COLLECTIONS["aid_stations"])

    def _medical_plan_repo(self):
        return self._repository(COLLECTIONS["medical_plan"])

    def _aid_station_doc(self, id_value: int) -> dict[str, Any] | None:
        return self._aid_stations_repo().find_one({
            "id": int(id_value),
            "incident_id": self._incident_id(),
        })

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def ensure_ics206_tables(self) -> None:
        """Verify Mongo indexes for the active incident."""
        db = self._db()
        incident_id = self._incident_id()
        aid_stations = db[COLLECTIONS["aid_stations"]]
        aid_stations.create_index([("incident_id", 1), ("op_period", 1)])
        aid_stations.create_index([("id", 1)], unique=True)
        aid_stations.create_index([("deleted", 1)])
        plan = db[COLLECTIONS["medical_plan"]]
        plan.create_index(
            [("incident_id", 1), ("op_period", 1)], unique=True
        )
        plan.create_index([("plan_id", 1)], unique=True)
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
        if table == "aid_stations":
            row = self._collection(table).find_one(sort=[("id", -1)], projection={"id": 1})
            return int(row["id"]) + 1 if row and row.get("id") is not None else 1
        rows = self._plan_array(table)
        ids = [int(row.get("id") or 0) for row in rows]
        return max(ids, default=0) + 1

    def _clean_doc(self, table: str, document: Mapping[str, Any]) -> dict[str, Any]:
        fields = TABLE_FIELDS[table]
        return {field: document.get(field) for field in fields}

    def _plan_id(self, op_period: int | None = None) -> str:
        op = self._op_period() if op_period is None else int(op_period)
        return f"{self._incident_id()}-MEDICAL-PLAN-{op}"

    def _empty_plan_doc(self, op_period: int | None = None) -> dict[str, Any]:
        op = self._op_period() if op_period is None else int(op_period)
        return {
            "plan_id": self._plan_id(op),
            "incident_id": self._incident_id(),
            "op_period": op,
            "ambulance_services": [],
            "hospitals": [],
            "air_ambulance": [],
            "medical_comms": [],
            "procedures": {"id": 1, "op_period": op, "content": ""},
            "signatures": {
                "id": 1,
                "op_period": op,
                "prepared_by": "",
                "position": "",
                "approved_by": "",
                "date": "",
            },
            "deleted": False,
        }

    def _ensure_plan(self, op_period: int | None = None) -> dict[str, Any]:
        repo = self._medical_plan_repo()
        op = self._op_period() if op_period is None else int(op_period)
        query = {"incident_id": self._incident_id(), "op_period": op}
        doc = repo.find_one(query)
        if doc:
            return doc
        return repo.insert_one(self._empty_plan_doc(op))

    def _plan_array(self, table: str, op_period: int | None = None) -> list[dict[str, Any]]:
        doc = self._ensure_plan(op_period)
        rows = doc.get(table) or []
        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if not row.get("deleted")]

    def _update_plan(self, updates: dict[str, Any], op_period: int | None = None) -> bool:
        doc = self._ensure_plan(op_period)
        return self._medical_plan_repo().update_one(doc["_id"], updates)

    def list_table(self, table: str) -> List[Dict[str, Any]]:
        if table in PLAN_TABLES:
            rows = self._plan_array(table)
            return [self._clean_doc(table, row) for row in sorted(rows, key=lambda row: int(row.get("id") or 0))]
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
        if table in PLAN_TABLES:
            doc.pop("incident_id", None)
            rows = self._plan_array(table)
            rows.append(doc)
            self._update_plan({table: rows})
        else:
            self._aid_stations_repo().insert_one(doc)
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
        if table in PLAN_TABLES:
            rows = self._plan_array(table)
            matched = False
            for row in rows:
                if int(row.get("id") or 0) == int(id_value):
                    row.update(updates)
                    matched = True
                    break
            result = self._update_plan({table: rows}) if matched else False
            self.data_changed.emit(table)
            return bool(result)
        existing = self._aid_station_doc(id_value)
        if not existing:
            self.data_changed.emit(table)
            return False
        result = self._aid_stations_repo().update_one(existing["_id"], updates)
        self.data_changed.emit(table)
        return result

    def delete_record(self, table: str, id_value: int) -> bool:
        if table in PLAN_TABLES:
            rows = self._plan_array(table)
            matched = False
            for row in rows:
                if int(row.get("id") or 0) == int(id_value):
                    row["deleted"] = True
                    row["updated_at"] = self._now()
                    matched = True
                    break
            result = self._update_plan({table: rows}) if matched else False
            self.data_changed.emit(table)
            return bool(result)
        existing = self._aid_station_doc(id_value)
        if not existing:
            self.data_changed.emit(table)
            return False
        result = self._aid_stations_repo().update_one(
            existing["_id"],
            {"deleted": True, "updated_at": self._now()},
        )
        self.data_changed.emit(table)
        return result

    def get_procedures(self) -> str:
        plan = self._ensure_plan()
        row = plan.get("procedures") or {}
        return str(row.get("content") or "") if isinstance(row, dict) else ""

    def save_procedures(self, text: str) -> None:
        op = self._op_period()
        self._update_plan({
            "procedures": {
                "id": 1,
                "op_period": op,
                "content": text,
                "deleted": False,
                "updated_at": self._now(),
            }
        })
        self.data_changed.emit("procedures")

    def get_signatures(self) -> Dict[str, Any]:
        row = self._ensure_plan().get("signatures")
        if not isinstance(row, dict):
            return {}
        return {
            "prepared_by": row.get("prepared_by"),
            "position": row.get("position"),
            "approved_by": row.get("approved_by"),
            "date": row.get("date"),
        }

    def save_signatures(self, data: Dict[str, Any]) -> None:
        now = self._now()
        self._update_plan({
            "signatures": {
                "id": 1,
                "op_period": self._op_period(),
                "prepared_by": data.get("prepared_by"),
                "position": data.get("position"),
                "approved_by": data.get("approved_by"),
                "date": data.get("date"),
                "deleted": False,
                "updated_at": now,
            }
        })
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
                    "facility_id": "",
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "level": "",
                    "is_24_7": 0,
                    "location_text": row.get("address") or "",
                    "latitude": row.get("latitude"),
                    "longitude": row.get("longitude"),
                    "manager_personnel_id": "",
                    "manager_name": row.get("contact") or row.get("contact_name") or "",
                    "notes": row.get("notes"),
                },
            )
        return len(rows)

    def import_ambulance_services(self) -> int:
        rows = self._import_master_rows(
            "ems_agencies",
            {"type": {"$in": ["Ground Ambulance", "Ambulance", "Air Ambulance"]}, "is_active": {"$ne": False}},
        )
        for row in rows:
            self.add_record(
                "ambulance_services",
                {
                    "name": row.get("name"),
                    "type": row.get("type"),
                    "service_level": _service_level_from_row(row),
                    "phone": row.get("phone"),
                    "location": row.get("address"),
                    "notes": row.get("notes"),
                },
            )
        return len(rows)

    def import_hospitals(self) -> int:
        rows = self._import_master_rows("hospitals", {"deleted": {"$ne": True}})
        for row in rows:
            adult_level = _trauma_level_int(
                row.get("adult_trauma_level") or row.get("trauma_level")
            )
            pediatric_level = _trauma_level_int(
                row.get("pediatric_trauma_level")
            )
            if pediatric_level == 0 and row.get("pediatric_capability") and adult_level:
                pediatric_level = adult_level
            self.add_record(
                "hospitals",
                {
                    "name": row.get("name"),
                    "address": row.get("address"),
                    "phone": row.get("phone") or row.get("phone_er") or row.get("phone_switchboard"),
                    "helipad": 1 if row.get("helipad") else 0,
                    "burn_center": 1 if row.get("burn_center") else 0,
                    "level": _trauma_display(adult_level, pediatric_level),
                    "adult_trauma_level": adult_level,
                    "pediatric_trauma_level": pediatric_level,
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
        aid_row = self._collection("aid_stations").find_one(
            {
                "incident_id": self._incident_id(),
                "op_period": {"$lt": cur_op},
                "deleted": {"$ne": True},
            },
            sort=[("op_period", -1)],
        )
        plan_row = self._collection("medical_plan").find_one(
            {
                "incident_id": self._incident_id(),
                "op_period": {"$lt": cur_op},
                "deleted": {"$ne": True},
            },
            sort=[("op_period", -1)],
        )
        if not aid_row and not plan_row:
            return False
        now = self._now()
        copied = False
        if aid_row:
            prev = int(aid_row["op_period"])
            for source in self._collection("aid_stations").find(
                {"incident_id": self._incident_id(), "op_period": prev, "deleted": {"$ne": True}}
            ):
                doc = {field: source.get(field) for field in TABLE_FIELDS["aid_stations"] if field not in ("id", "op_period")}
                doc.update(
                    {
                        "id": self._next_id("aid_stations"),
                        "incident_id": self._incident_id(),
                        "op_period": cur_op,
                        "deleted": False,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                self._aid_stations_repo().insert_one(doc)
                copied = True
        if plan_row:
            plan = strip_mongo_id(plan_row) or {}
            plan["plan_id"] = self._plan_id(cur_op)
            plan["incident_id"] = self._incident_id()
            plan["op_period"] = cur_op
            plan["deleted"] = False
            plan["created_at"] = now
            plan["updated_at"] = now
            for table in PLAN_TABLES:
                rows = []
                for source in plan.get(table) or []:
                    row = dict(source)
                    row["op_period"] = cur_op
                    row["deleted"] = False
                    row["created_at"] = now
                    row["updated_at"] = now
                    rows.append(row)
                plan[table] = rows
            procedures = dict(plan.get("procedures") or {})
            procedures["op_period"] = cur_op
            procedures["updated_at"] = now
            plan["procedures"] = procedures
            signatures = dict(plan.get("signatures") or {})
            signatures["op_period"] = cur_op
            signatures["updated_at"] = now
            plan["signatures"] = signatures
            existing = self._medical_plan_repo().find_one({
                "incident_id": self._incident_id(),
                "op_period": cur_op,
            })
            if existing:
                self._medical_plan_repo().update_one(existing["_id"], plan)
            else:
                self._medical_plan_repo().insert_one(plan)
            copied = True
        self.data_changed.emit("all")
        return copied
