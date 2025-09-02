from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Team:
    """Team domain model used by Team Detail Window.

    This model mirrors the minimum fields we need across UI and persistence.
    Multi-valued relationships are stored as lists and persisted as JSON blobs
    in the teams table (best-effort) until dedicated link tables are finalized.
    """

    team_id: Optional[int] = None
    name: str = ""
    callsign: Optional[str] = None
    role: Optional[str] = None
    status: str = "available"
    priority: Optional[int] = None
    current_task_id: Optional[int] = None
    team_leader_id: Optional[int] = None  # FK to personnel.id
    phone: Optional[str] = None
    notes: Optional[str] = None
    last_update_ts: datetime = field(default_factory=datetime.utcnow)
    last_comm_ts: Optional[datetime] = None
    last_known_lat: Optional[float] = None
    last_known_lon: Optional[float] = None
    members: List[int] = field(default_factory=list)
    vehicles: List[str] = field(default_factory=list)
    equipment: List[str] = field(default_factory=list)
    aircraft: List[str] = field(default_factory=list)
    comms_preset_id: Optional[int] = None
    team_type: str = "ground"  # "ground" or "aircraft"
    radio_ids: Optional[str] = None  # free-form text for now
    route: Optional[str] = None

    def to_db_dict(self) -> Dict[str, Any]:
        """Serialize to a dict suitable for DB operations.

        - Complex lists are encoded as JSON strings.
        - Datetimes are ISO strings (UTC).
        """
        import json

        return {
            "id": self.team_id,
            "name": self.name or None,
            "callsign": self.callsign,
            "role": self.role,
            "status": (self.status or "").strip().lower() if self.status else None,
            "priority": self.priority,
            "current_task_id": self.current_task_id,
            "team_leader": self.team_leader_id,
            "phone": self.phone,
            "notes": self.notes,
            "status_updated": (self.last_update_ts or datetime.utcnow()).isoformat(),
            "last_comm_ping": (self.last_comm_ts.isoformat() if self.last_comm_ts else None),
            "last_known_lat": self.last_known_lat,
            "last_known_lon": self.last_known_lon,
            "members_json": json.dumps(list(self.members or [])),
            "vehicles_json": json.dumps(list(self.vehicles or [])),
            "equipment_json": json.dumps(list(self.equipment or [])),
            "aircraft_json": json.dumps(list(self.aircraft or [])),
            "comms_preset_id": self.comms_preset_id,
            "team_type": self.team_type,
            "radio_ids": self.radio_ids,
            "route": self.route,
        }

    @staticmethod
    def from_db_row(row: Any) -> "Team":
        """Hydrate a Team from a sqlite3.Row or mapping.

        Missing columns are tolerated; defaults are used.
        """
        import json
        def _get(key: str, default: Any = None) -> Any:
            try:
                return row[key]
            except Exception:
                return default

        def _parse_json(s: Any) -> List[Any]:
            if not s:
                return []
            try:
                return list(json.loads(s))
            except Exception:
                return []

        status_raw = _get("status") or "available"
        status_norm = str(status_raw).strip().lower()
        # Normalize a few legacy values
        status_norm = {
            "en route": "enroute",
            "on scene": "arrival",
            "rtb": "returning",
        }.get(status_norm, status_norm)

        ts = _get("status_updated")
        try:
            last_ts = datetime.fromisoformat(ts) if ts else datetime.utcnow()
        except Exception:
            last_ts = datetime.utcnow()

        comm_ts = _get("last_comm_ping")
        try:
            comm_dt = datetime.fromisoformat(comm_ts) if comm_ts else None
        except Exception:
            comm_dt = None

        return Team(
            team_id=int(_get("id")) if _get("id") is not None else None,
            name=str(_get("name") or ""),
            callsign=_get("callsign"),
            role=_get("role"),
            status=status_norm,
            priority=(int(_get("priority")) if _get("priority") is not None else None),
            current_task_id=(int(_get("current_task_id")) if _get("current_task_id") is not None else None),
            team_leader_id=(int(_get("team_leader")) if _get("team_leader") is not None else None),
            phone=_get("phone"),
            notes=_get("notes"),
            last_update_ts=last_ts,
            last_comm_ts=comm_dt,
            last_known_lat=(float(_get("last_known_lat")) if _get("last_known_lat") is not None else None),
            last_known_lon=(float(_get("last_known_lon")) if _get("last_known_lon") is not None else None),
            members=_parse_json(_get("members_json")),
            vehicles=_parse_json(_get("vehicles_json")),
            equipment=_parse_json(_get("equipment_json")),
            aircraft=_parse_json(_get("aircraft_json")),
            comms_preset_id=(int(_get("comms_preset_id")) if _get("comms_preset_id") is not None else None),
            team_type=str(_get("team_type") or "ground"),
            radio_ids=_get("radio_ids"),
            route=_get("route"),
        )

    def to_qml(self) -> Dict[str, Any]:
        """Return a QML-friendly dict (simple JSON types only)."""
        return {
            "team_id": self.team_id,
            "name": self.name,
            "callsign": self.callsign,
            "role": self.role,
            "status": self.status,
            "priority": self.priority,
            "current_task_id": self.current_task_id,
            "team_leader_id": self.team_leader_id,
            "phone": self.phone,
            "notes": self.notes,
            "last_update_ts": (self.last_update_ts or datetime.utcnow()).isoformat(),
            "last_comm_ts": (self.last_comm_ts.isoformat() if self.last_comm_ts else None),
            "last_known_lat": self.last_known_lat,
            "last_known_lon": self.last_known_lon,
            "members": list(self.members or []),
            "vehicles": list(self.vehicles or []),
            "equipment": list(self.equipment or []),
            "aircraft": list(self.aircraft or []),
            "comms_preset_id": self.comms_preset_id,
            "team_type": self.team_type,
            "radio_ids": self.radio_ids,
            "route": self.route,
        }

