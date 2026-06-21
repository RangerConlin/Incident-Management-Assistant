"""API-backed repository for aircraft catalog records."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

ISO_FMT = "%Y-%m-%dT%H:%M:%S"

_BASE = "/api/master/aircraft"


def _client():
    from utils.api_client import api_client
    return api_client


def _bool(value: Any) -> bool:
    return bool(int(value)) if value not in (None, "", False) else False


def _coerce_int(value: Optional[str | int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    return datetime.utcnow().strftime(ISO_FMT)


@dataclass(slots=True)
class AircraftRecord:
    """Serializable aircraft record used by the UI layer."""

    tail_number: str
    id: Optional[int] = None
    callsign: str = ""
    type: str = "Helicopter"
    make: str = ""
    model: str = ""
    base: str = ""
    current_location: str = ""
    status: str = "Available"
    assigned_team_id: Optional[str] = None
    assigned_team_name: Optional[str] = None
    organization: Optional[str] = None
    fuel_type: str = "Jet A"
    range_nm: int = 0
    endurance_hr: float = 0.0
    cruise_kt: int = 0
    crew_min: int = 0
    crew_max: int = 0
    adsb_hex: str = ""
    radio_vhf_air: bool = False
    radio_vhf_sar: bool = False
    radio_uhf: bool = False
    cap_hoist: bool = False
    cap_nvg: bool = False
    cap_flir: bool = False
    cap_ifr: bool = False
    payload_kg: float = 0.0
    med_config: str = "None"
    serial_number: str = ""
    year: Optional[int] = None
    owner_operator: str = ""
    registration_exp: Optional[str] = None
    inspection_due: Optional[str] = None
    last_100hr: Optional[str] = None
    next_100hr: Optional[str] = None
    notes: str = ""
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


_RECORD_FIELD_NAMES = {fld.name for fld in fields(AircraftRecord)}


def _record_kwargs(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: payload[key] for key in payload if key in _RECORD_FIELD_NAMES}


def _doc_to_dict(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize an API response to the dict shape the UI expects."""
    make = doc.get("make") or ""
    model = doc.get("model") or ""
    return {
        "id": doc.get("id") or doc.get("int_id"),
        "tail_number": doc.get("tail_number") or "",
        "callsign": doc.get("callsign") or "",
        "type": doc.get("type") or "",
        "make": make,
        "model": model,
        "make_model": " ".join(filter(None, (make, model))).strip(),
        "base": doc.get("base") or "",
        "current_location": doc.get("current_location") or "",
        "status": doc.get("status") or "Available",
        "assigned_team_id": doc.get("assigned_team_id"),
        "assigned_team_name": doc.get("assigned_team_name"),
        "organization": doc.get("organization"),
        "fuel_type": doc.get("fuel_type") or "Jet A",
        "range_nm": doc.get("range_nm") or 0,
        "endurance_hr": doc.get("endurance_hr") or 0.0,
        "cruise_kt": doc.get("cruise_kt") or 0,
        "crew_min": doc.get("crew_min") or 0,
        "crew_max": doc.get("crew_max") or 0,
        "adsb_hex": doc.get("adsb_hex") or "",
        "radio_vhf_air": _bool(doc.get("radio_vhf_air")),
        "radio_vhf_sar": _bool(doc.get("radio_vhf_sar")),
        "radio_uhf": _bool(doc.get("radio_uhf")),
        "cap_hoist": _bool(doc.get("cap_hoist")),
        "cap_nvg": _bool(doc.get("cap_nvg")),
        "cap_flir": _bool(doc.get("cap_flir")),
        "cap_ifr": _bool(doc.get("cap_ifr")),
        "payload_kg": doc.get("payload_kg") or 0.0,
        "med_config": doc.get("med_config") or "None",
        "serial_number": doc.get("serial_number") or "",
        "year": doc.get("year"),
        "owner_operator": doc.get("owner_operator") or "",
        "registration_exp": doc.get("registration_exp"),
        "inspection_due": doc.get("inspection_due"),
        "last_100hr": doc.get("last_100hr"),
        "next_100hr": doc.get("next_100hr"),
        "notes": doc.get("notes") or "",
        "attachments": doc.get("attachments") or [],
        "history": doc.get("history") or [],
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def _make_body(record: AircraftRecord) -> Dict[str, Any]:
    return {
        "tail_number": record.tail_number,
        "callsign": record.callsign,
        "type": record.type or "Helicopter",
        "make": record.make,
        "model": record.model,
        "base": record.base,
        "current_location": record.current_location,
        "status": record.status or "Available",
        "assigned_team_id": record.assigned_team_id,
        "assigned_team_name": record.assigned_team_name,
        "organization": record.organization,
        "fuel_type": record.fuel_type or "Jet A",
        "range_nm": int(max(record.range_nm, 0)),
        "endurance_hr": float(max(record.endurance_hr, 0.0)),
        "cruise_kt": int(max(record.cruise_kt, 0)),
        "crew_min": int(max(record.crew_min, 0)),
        "crew_max": int(max(record.crew_max, record.crew_min)),
        "adsb_hex": record.adsb_hex,
        "radio_vhf_air": bool(record.radio_vhf_air),
        "radio_vhf_sar": bool(record.radio_vhf_sar),
        "radio_uhf": bool(record.radio_uhf),
        "cap_hoist": bool(record.cap_hoist),
        "cap_nvg": bool(record.cap_nvg),
        "cap_flir": bool(record.cap_flir),
        "cap_ifr": bool(record.cap_ifr),
        "payload_kg": float(max(record.payload_kg, 0.0)),
        "med_config": record.med_config or "None",
        "serial_number": record.serial_number,
        "year": record.year,
        "owner_operator": record.owner_operator,
        "registration_exp": record.registration_exp,
        "inspection_due": record.inspection_due,
        "last_100hr": record.last_100hr,
        "next_100hr": record.next_100hr,
        "notes": record.notes,
        "attachments": list(record.attachments),
        "history": list(record.history),
    }


class AircraftRepository:
    """API-backed repository for aircraft master catalog entries."""

    def __init__(self, db_path=None) -> None:
        pass

    def list_aircraft(self) -> List[Dict[str, Any]]:
        try:
            docs = _client().get(_BASE) or []
            return [_doc_to_dict(d) for d in docs]
        except Exception:
            return []

    def fetch_aircraft(self, aircraft_id: int) -> Optional[Dict[str, Any]]:
        try:
            doc = _client().get(f"{_BASE}/{aircraft_id}")
            return _doc_to_dict(doc) if doc else None
        except Exception:
            return None

    def find_by_tail(self, tail_number: str) -> Optional[Dict[str, Any]]:
        try:
            docs = _client().get(_BASE, params={"search": tail_number}) or []
            upper = tail_number.strip().upper()
            for d in docs:
                if (d.get("tail_number") or "").upper() == upper:
                    return _doc_to_dict(d)
            return None
        except Exception:
            return None

    def create_aircraft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = AircraftRecord(**_record_kwargs(payload))
        doc = _client().post(_BASE, json=_make_body(record))
        return _doc_to_dict(doc)

    def update_aircraft(self, aircraft_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        current = self.fetch_aircraft(int(aircraft_id))
        if current is None:
            raise LookupError(f"Aircraft {aircraft_id} does not exist")
        merged = {**current, **payload, "id": aircraft_id}
        record = AircraftRecord(**_record_kwargs(merged))
        body = _make_body(record)
        body.pop("tail_number", None)
        doc = _client().patch(f"{_BASE}/{aircraft_id}", json=body)
        return _doc_to_dict(doc)

    def delete_aircraft(self, aircraft_id: int) -> None:
        _client().delete(f"{_BASE}/{aircraft_id}")

    def set_status(self, aircraft_ids: Iterable[int], status: str, notes: str = "") -> None:
        normalized = status.strip() or "Available"
        for aircraft_id in aircraft_ids:
            try:
                _client().patch(
                    f"{_BASE}/{aircraft_id}/status",
                    json={"status": normalized, "notes": notes},
                )
            except Exception:
                pass

    def assign_team(
        self,
        aircraft_ids: Iterable[int],
        team_id: Optional[str],
        team_name: Optional[str],
        notify: bool = False,
    ) -> None:
        for aircraft_id in aircraft_ids:
            try:
                _client().patch(
                    f"{_BASE}/{aircraft_id}/assignment",
                    json={"team_id": team_id, "team_name": team_name},
                )
            except Exception:
                pass

    def clear_assignment(self, aircraft_ids: Iterable[int]) -> None:
        self.assign_team(aircraft_ids, None, None)
