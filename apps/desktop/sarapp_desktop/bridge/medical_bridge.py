"""Bridge layer exposing ICS 206 data to Qt widgets.

Talks to the shared API server's editable ICS-206 plan endpoints
(``/api/incidents/{id}/medical/plan...``, ``.../medical/aid-stations...``)
rather than MongoDB directly — see ``utils/api_client.py``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from PySide6.QtCore import QObject, Signal
from utils.api_client import APIError, api_client
from utils.incident_context import get_active_incident_id
from utils.state import AppState

TABLE_FIELDS: Dict[str, Sequence[str]] = {
    "aid_stations": [
        "id",
        "op_period",
        "version",
        "facility_id",
        "name",
        "type",
        "level",
        "contact_frequency",
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
        "source_ref",
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
        "source_ref",
        "name",
        "address",
        "phone",
        "helipad",
        "burn_center",
        "level",
        "adult_trauma_level",
        "pediatric_trauma_level",
        "lat",
        "lon",
        "travel_time_min",
        "travel_time_air_min",
        "travel_time_ground_min",
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
        "prepared_by_id",
        "position",
        "prepared_at",
        "date",
        "approved_by",
        "approved_by_id",
        "approved_by_position",
        "approved_at",
    ],
}

PLAN_TABLES = {"ambulance_services", "hospitals", "air_ambulance", "medical_comms"}
# Plan tables that can be filled from the nearby-facility lookup -> API kind.
NEARBY_KINDS = {"ambulance_services": "ambulance-services", "hospitals": "hospitals"}
NEARBY_SEARCH_TIMEOUT_S = 180.0
PLAN_SINGLE_SECTIONS = {"procedures", "ics206_signatures"}
PLAN_SECTION_FIELD = {"ics206_signatures": "signatures"}

# Plan lifecycle, shared with modules.approvals (ApprovalStatus). Only a
# version that has not been submitted for approval can be edited.
APPROVAL_NOT_STARTED = "not_started"
APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"
APPROVAL_LABELS = {
    APPROVAL_NOT_STARTED: "Draft",
    APPROVAL_PENDING: "In review",
    APPROVAL_APPROVED: "Approved",
    APPROVAL_REJECTED: "Rejected",
}


class MedicalBridge(QObject):
    """API-backed data access used by :class:`modules.medical.panels.ics206_panel.ICS206Panel`."""

    data_changed = Signal(str)
    toast = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # (op_period, version) the panel has selected; None means "latest".
        self._selected: tuple[int, int] | None = None
        # Cached result of the last GET .../medical/plan call for the active
        # (op, version); invalidated by any write.  Avoids a round trip for
        # every field read (approval_status, signatures, plan arrays, ...).
        self._plan_cache: tuple[int, int, dict[str, Any]] | None = None

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

    def _base(self) -> str:
        return f"/api/incidents/{self._incident_id()}"

    def ensure_ics206_tables(self) -> None:
        """Verify the server is reachable for the active incident.

        Indexes and schema setup now live server-side (see
        ``sarapp_db.mongo.indexes``); this just surfaces connection issues
        during panel startup, as it always has.
        """
        incident_id = self._incident_id()
        if not incident_id:
            raise RuntimeError("No active incident selected")
        api_client.get(f"{self._base()}/medical/aid-stations", params={"op": self._op_period()})

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------
    def _latest_version(self, op_period: int) -> int:
        versions = self.list_versions_for(op_period)
        return max((int(v.get("version") or 1) for v in versions), default=1)

    def list_versions_for(self, op_period: int) -> list[dict[str, Any]]:
        return api_client.get(f"{self._base()}/medical/plan/versions", params={"op": op_period}) or []

    def _version(self) -> int:
        """Version the panel is working on for the active OP (latest by default)."""
        op = self._op_period()
        if self._selected and self._selected[0] == op:
            return self._selected[1]
        return self._latest_version(op)

    def current_version(self) -> int:
        return self._version()

    def select_version(self, version: int | None) -> None:
        """Point the bridge at ``version`` of the active OP (``None`` = latest)."""
        self._selected = None if version is None else (self._op_period(), int(version))
        self._plan_cache = None
        self.data_changed.emit("all")

    def _plan(self, *, force: bool = False) -> dict[str, Any]:
        op = self._op_period()
        version = self._version()
        if not force and self._plan_cache and self._plan_cache[:2] == (op, version):
            return self._plan_cache[2]
        person = self.current_person() or {}
        plan = api_client.get(
            f"{self._base()}/medical/plan",
            params={
                "op": op,
                "version": version,
                "prepared_name": person.get("name", ""),
                "prepared_personnel_id": person.get("personnel_id", ""),
                "prepared_position": person.get("position", ""),
            },
        ) or {}
        self._plan_cache = (op, version, plan)
        return plan

    def _invalidate(self) -> None:
        self._plan_cache = None

    def approval_status(self) -> str:
        return str(self._plan().get("approval_status") or APPROVAL_NOT_STARTED)

    def is_locked(self) -> bool:
        return self.approval_status() != APPROVAL_NOT_STARTED

    def approval_target(self) -> tuple[str, str]:
        """(incident_id, plan_id) identifying this version's approval chain."""
        return self._incident_id(), str(self._plan()["plan_id"])

    def current_person(self) -> dict[str, str] | None:
        """Identify the signed-in user from the master personnel record."""
        person_record = AppState.get_active_user_id()
        if person_record in (None, ""):
            return None
        person = api_client.get(f"/api/master/personnel/{int(person_record)}") or {}
        name = str(person.get("name") or "").strip()
        if not name:
            return None
        return {
            "personnel_id": str(person.get("id") or person.get("person_record") or person_record),
            "name": name,
            "position": str(person.get("primary_role") or person.get("role") or "").strip(),
        }

    @staticmethod
    def local_stamp(iso_value: str) -> str:
        from utils.timefmt import to_datetime

        dt = to_datetime(iso_value)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else ""

    def list_versions(self) -> list[dict[str, Any]]:
        return self.list_versions_for(self._op_period())

    def _clean_doc(self, table: str, document: Mapping[str, Any]) -> dict[str, Any]:
        fields = TABLE_FIELDS[table]
        return {field: document.get(field) for field in fields}

    def find_nearby(self, table: str, radius_mi: float, refresh: bool = False) -> dict[str, Any]:
        """Facilities near the incident that could be added to ``table``.

        Returns ``{"results", "warnings", "note", "source"}``.  Each result
        carries ``already_added`` so the picker can grey out entries the
        selected version already lists.
        """
        profile = api_client.get(f"{self._base()}/profile") or {}
        lat, lon = profile.get("latitude"), profile.get("longitude")
        if lat is None or lon is None:
            raise RuntimeError("The incident has no location set, so nearby facilities cannot be searched.")
        found = api_client.get(
            f"/api/medical/nearby/{NEARBY_KINDS[table]}",
            params={"lat": lat, "lon": lon, "radius_mi": radius_mi, "refresh": refresh},
            # The first search in a state downloads and geocodes its hospitals.
            timeout=NEARBY_SEARCH_TIMEOUT_S,
        ) or {}
        rows = found.get("results") or []
        existing = self.list_table(table)
        refs = {str(row.get("source_ref")) for row in existing if row.get("source_ref")}
        names = {str(row.get("name") or "").strip().lower() for row in existing}
        return {
            **found,
            "results": [
                {**row, "already_added": row["source_ref"] in refs or row["name"].strip().lower() in names}
                for row in rows
            ],
        }

    def hide_nearby(self, table: str, row: Mapping[str, Any], reason: str) -> None:
        """Hide ``row`` from all future nearby searches (closed, not public, etc.)."""
        person = self.current_person()
        api_client.post(
            "/api/medical/nearby-exclusions",
            json={
                "source_ref": row["source_ref"],
                "kind": NEARBY_KINDS[table],
                "name": row["name"],
                "address": row["address"],
                "reason": reason,
                "excluded_by": person["name"] if person else "",
            },
        )

    def list_hidden_nearby(self) -> list[dict[str, Any]]:
        return api_client.get("/api/medical/nearby-exclusions") or []

    def restore_nearby(self, exclusion_id: str) -> None:
        api_client.delete(f"/api/medical/nearby-exclusions/{exclusion_id}")

    def add_nearby(self, table: str, rows: Sequence[Mapping[str, Any]]) -> int:
        """Add lookup results to ``table``.  Fields the source lacks are left blank."""
        added = 0
        for row in rows:
            if row.get("already_added"):
                continue
            base = {"source_ref": row["source_ref"], "name": row["name"]}
            if table == "ambulance_services":
                base.update({"service_level": 0, "location": row["address"]})
            else:
                base.update({
                    "address": row["address"],
                    "phone": row.get("phone", ""),
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "helipad": 0,
                    "burn_center": 0,
                })
            self.add_record(table, base)
            added += 1
        return added

    # ------------------------------------------------------------------
    # Table CRUD ---------------------------------------------------------
    def _plan_endpoint(self, table: str, suffix: str = "") -> str:
        base = f"{self._base()}/medical/plan/{table}"
        return f"{base}/{suffix}" if suffix else base

    def _aid_endpoint(self, suffix: str = "") -> str:
        base = f"{self._base()}/medical/aid-stations"
        return f"{base}/{suffix}" if suffix else base

    def _rw_params(self) -> dict[str, int]:
        return {"op": self._op_period(), "version": self._version()}

    def list_table(self, table: str) -> List[Dict[str, Any]]:
        if table in PLAN_TABLES:
            rows = self._plan().get(table) or []
            return [self._clean_doc(table, row) for row in sorted(rows, key=lambda row: int(row.get("id") or 0))]
        rows = api_client.get(self._aid_endpoint(), params=self._rw_params()) or []
        return [self._clean_doc(table, row) for row in rows]

    def add_record(self, table: str, data: Dict[str, Any]) -> int:
        self._plan()  # ensure the plan doc exists, stamped with the current preparer
        try:
            if table in PLAN_TABLES:
                row = api_client.post(self._plan_endpoint(table), json=data, params=self._rw_params())
            else:
                row = api_client.post(self._aid_endpoint(), json=data, params=self._rw_params())
        except APIError as exc:
            self._invalidate()
            if exc.status_code == 409:
                raise RuntimeError(str(exc)) from exc
            raise
        self._invalidate()
        self.data_changed.emit(table)
        return int(row["id"])

    def update_record(self, table: str, id_value: int, data: Dict[str, Any]) -> bool:
        self._plan()
        try:
            if table in PLAN_TABLES:
                api_client.patch(self._plan_endpoint(table, str(id_value)), json=data, params=self._rw_params())
            else:
                api_client.patch(self._aid_endpoint(str(id_value)), json=data, params=self._rw_params())
        except APIError as exc:
            self._invalidate()
            self.data_changed.emit(table)
            if exc.status_code == 404:
                return False
            if exc.status_code == 409:
                raise RuntimeError(str(exc)) from exc
            raise
        self._invalidate()
        self.data_changed.emit(table)
        return True

    def delete_record(self, table: str, id_value: int) -> bool:
        self._plan()
        try:
            if table in PLAN_TABLES:
                api_client.delete(self._plan_endpoint(table, str(id_value)), params=self._rw_params())
            else:
                api_client.delete(self._aid_endpoint(str(id_value)), params=self._rw_params())
        except APIError as exc:
            self._invalidate()
            self.data_changed.emit(table)
            if exc.status_code == 404:
                return False
            if exc.status_code == 409:
                raise RuntimeError(str(exc)) from exc
            raise
        self._invalidate()
        self.data_changed.emit(table)
        return True

    def _import_table(self, table: str) -> int:
        self._plan()
        if table in PLAN_TABLES:
            result = api_client.post(self._plan_endpoint(table, "import"), params=self._rw_params()) or {}
        else:
            result = api_client.post(self._aid_endpoint("import"), params=self._rw_params()) or {}
        self._invalidate()
        self.data_changed.emit(table)
        return int(result.get("count") or 0)

    def import_aid_stations(self) -> int:
        return self._import_table("aid_stations")

    def import_ambulance_services(self) -> int:
        return self._import_table("ambulance_services")

    def import_hospitals(self) -> int:
        return self._import_table("hospitals")

    def import_air_ambulance(self) -> int:
        return self._import_table("air_ambulance")

    def import_medical_comms(self) -> int:
        return self._import_table("medical_comms")

    # ------------------------------------------------------------------
    # Procedures and signatures ------------------------------------------
    def get_procedures(self) -> str:
        row = self._plan().get("procedures") or {}
        return str(row.get("content") or "") if isinstance(row, dict) else ""

    def save_procedures(self, text: str) -> None:
        self._plan()
        try:
            api_client.patch(
                f"{self._base()}/medical/plan/procedures", json={"content": text}, params=self._rw_params()
            )
        except APIError as exc:
            self._invalidate()
            if exc.status_code == 409:
                raise RuntimeError(str(exc)) from exc
            raise
        self._invalidate()
        self.data_changed.emit("procedures")

    def get_signatures(self) -> Dict[str, Any]:
        row = self._plan().get("signatures")
        if not isinstance(row, dict):
            return {}
        return {
            field: row.get(field) or ""
            for field in TABLE_FIELDS["ics206_signatures"]
            if field not in ("id", "op_period")
        }

    def mark_pending(self) -> None:
        """Lock the selected draft while its approval chain runs."""
        self._plan()
        try:
            api_client.patch(
                f"{self._base()}/medical/plan/status", json={"status": APPROVAL_PENDING}, params=self._rw_params()
            )
        except APIError as exc:
            self._invalidate()
            if exc.status_code == 409:
                raise RuntimeError(str(exc)) from exc
            raise
        self._invalidate()
        self.data_changed.emit("all")

    def apply_approval_outcome(self, outcome: str) -> None:
        """Record a finished approval chain (``approved`` or ``rejected``).

        On approval the signed-in user, who just signed the final step, is
        stamped as the approver.
        """
        if outcome not in (APPROVAL_APPROVED, APPROVAL_REJECTED):
            raise ValueError(f"Not a final approval outcome: {outcome}")
        person = self.current_person()
        if outcome == APPROVAL_APPROVED and person is None:
            raise RuntimeError("No signed-in user; cannot record an approver.")
        api_client.post(
            f"{self._base()}/medical/plan/approval",
            json={"outcome": outcome, "person": person or {}},
            params=self._rw_params(),
        )
        self._invalidate()
        self.data_changed.emit("all")

    def create_new_version(self, change_note: str = "") -> int:
        """Copy the selected version into a new draft and switch to it."""
        op = self._op_period()
        person = self.current_person() or {}
        result = api_client.post(
            f"{self._base()}/medical/plan/new-version",
            json={"change_note": change_note.strip(), "person": person},
            params=self._rw_params(),
        ) or {}
        version = int(result["version"])
        self._selected = (op, version)
        self._invalidate()
        self.data_changed.emit("all")
        return version

    def duplicate_last_op(self) -> bool:
        """Replace the selected draft's contents with the previous OP's latest version."""
        person = self.current_person() or {}
        try:
            result = api_client.post(
                f"{self._base()}/medical/plan/duplicate-last-op",
                json={"person": person},
                params=self._rw_params(),
            ) or {}
        except APIError as exc:
            self._invalidate()
            if exc.status_code == 409:
                raise RuntimeError(str(exc)) from exc
            raise
        self._invalidate()
        self.data_changed.emit("all")
        return bool(result.get("duplicated"))


__all__ = ["MedicalBridge"]
