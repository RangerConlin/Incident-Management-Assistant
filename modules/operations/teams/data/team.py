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
    primary_task: Optional[str] = None
    assignment: Optional[str] = None
    location: Optional[str] = None
    team_leader_id: Optional[int] = None  # FK to personnel.id
    team_leader_phone: Optional[str] = None
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
    team_type: str = "GT"  # e.g., GT, UDF, AIR
    resource_type_id: Optional[int] = None
    operational_unit_id: Optional[int] = None  # chain-of-command: org chart position id (any section)
    readiness_status: str = "Unknown"
    radio_ids: Optional[str] = None  # free-form text for now
    route: Optional[str] = None
    # Attention flag (aka "needs assistance")
    needs_attention: bool = False

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
            "primary_task": self.primary_task,
            "assignment": self.assignment,
            "location": self.location,
            "team_leader": self.team_leader_id,
            "leader_phone": self.team_leader_phone,
            "phone": self.phone,
            "notes": self.notes,
            "status_updated": (self.last_update_ts or datetime.utcnow()).isoformat(timespec="seconds"),
            "last_comm_ping": (self.last_comm_ts.isoformat(timespec="seconds") if self.last_comm_ts else None),
            "last_known_lat": self.last_known_lat,
            "last_known_lon": self.last_known_lon,
            "members_json": json.dumps(list(self.members or [])),
            "vehicles_json": json.dumps(list(self.vehicles or [])),
            "equipment_json": json.dumps(list(self.equipment or [])),
            "aircraft_json": json.dumps(list(self.aircraft or [])),
            "comms_preset_id": self.comms_preset_id,
            "team_type": self.team_type,
            "resource_type_id": self.resource_type_id,
            "readiness_status": self.readiness_status or "Unknown",
            "radio_ids": self.radio_ids,
            "route": self.route,
            "needs_attention": 1 if bool(self.needs_attention) else 0,
        }

    def to_qml(self) -> Dict[str, Any]:
        """Return a QML-friendly dict (simple JSON types only)."""
        data: Dict[str, Any] = {
            "team_id": self.team_id,
            "name": self.name,
            "callsign": self.callsign,
            "role": self.role,
            "status": self.status,
            "priority": self.priority,
            "current_task_id": self.current_task_id,
            "primary_task": self.primary_task,
            "assignment": self.assignment,
            "location": self.location,
            "team_leader_id": self.team_leader_id,
            "team_leader_phone": self.team_leader_phone,
            "phone": self.phone,
            "notes": self.notes,
            "last_update_ts": (self.last_update_ts or datetime.utcnow()).isoformat(timespec="seconds"),
            "last_comm_ts": (self.last_comm_ts.isoformat(timespec="seconds") if self.last_comm_ts else None),
            "last_known_lat": self.last_known_lat,
            "last_known_lon": self.last_known_lon,
            "members": list(self.members or []),
            "vehicles": list(self.vehicles or []),
            "equipment": list(self.equipment or []),
            "aircraft": list(self.aircraft or []),
            "comms_preset_id": self.comms_preset_id,
            "team_type": self.team_type,
            "resource_type_id": self.resource_type_id,
            "operational_unit_id": self.operational_unit_id,
            "readiness_status": self.readiness_status,
            "radio_ids": self.radio_ids,
            "route": self.route,
            "needs_attention": bool(self.needs_attention),
        }
        # Compatibility aliases for existing QML bindings
        data["last_contact_ts"] = data["last_comm_ts"]
        data["primary_task_id"] = data["current_task_id"]
        data["needs_assist"] = data["needs_attention"]
        return data
