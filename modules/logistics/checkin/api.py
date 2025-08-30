"""High level services orchestrating repository operations."""
from __future__ import annotations

from typing import Dict, List

from . import repository

# Mapping helpers allowing generic functions
FIND_BY_ID = {
    "personnel": repository.find_personnel_by_id,
    "equipment": repository.find_equipment_by_id,
    "vehicle": repository.find_vehicle_by_id,
    "aircraft": repository.find_aircraft_by_id,
}

FIND_BY_NAME = {
    "personnel": repository.find_personnel_by_name,
    "equipment": repository.find_equipment_by_name,
    "vehicle": repository.find_vehicle_by_name,
    "aircraft": repository.find_aircraft_by_tail,
}

COPY_TO_INCIDENT = {
    "personnel": repository.copy_personnel_to_incident,
    "equipment": repository.copy_equipment_to_incident,
    "vehicle": repository.copy_vehicle_to_incident,
    "aircraft": repository.copy_aircraft_to_incident,
}

CREATE_MASTER = {
    "personnel": repository.create_or_update_personnel_master,
    "equipment": repository.create_or_update_equipment_master,
    "vehicle": repository.create_or_update_vehicle_master,
    "aircraft": repository.create_or_update_aircraft_master,
}


def lookup_entity(entity_type: str, mode: str, **kwargs) -> List[Dict]:
    """Lookup entities for display in the UI."""
    if mode == "id":
        result = FIND_BY_ID[entity_type](kwargs.get("value"))
        return [result] if result else []
    else:
        if entity_type == "aircraft":
            return FIND_BY_NAME[entity_type](kwargs.get("value"))
        if entity_type == "personnel":
            return FIND_BY_NAME[entity_type](kwargs.get("first"), kwargs.get("last"))
        return FIND_BY_NAME[entity_type](kwargs.get("value"))


def check_in_entity(entity_type: str, lookup_key: Dict, payload: Dict | None = None) -> Dict:
    """Perform a check-in operation based on the lookup key.

    Parameters
    ----------
    entity_type:
        One of ``personnel``, ``equipment``, ``vehicle`` or ``aircraft``.
    lookup_key:
        Dict describing how to lookup the entity.  For example
        ``{"mode": "id", "value": "P-123"}`` or
        ``{"mode": "name", "first": "A", "last": "B"}``.
    payload:
        Optional payload used when the record needs to be created.
    """
    mode = lookup_key.get("mode")
    params = {k: v for k, v in lookup_key.items() if k != "mode"}
    candidates = lookup_entity(entity_type, mode, **params)
    if candidates:
        # Found in master -> copy to incident
        entity = candidates[0]
        COPY_TO_INCIDENT[entity_type](entity)
        return {
            "success": True,
            "message": "Checked in",
            "entity": entity,
            "was_created": False,
            "was_copied": True,
        }
    else:
        return {"success": False, "requiresCreate": True, "message": "Not found"}


def create_master_plus_incident(entity_type: str, payload: Dict) -> Dict:
    """Create a new master record and copy it to the incident DB."""
    CREATE_MASTER[entity_type](payload)
    COPY_TO_INCIDENT[entity_type](payload)
    return {
        "success": True,
        "message": "Created and checked in",
        "entity": payload,
        "was_created": True,
        "was_copied": True,
    }


def update_incident_status(entity_type: str, entity_id: str, status: str) -> None:
    """Update the status for an incident record."""
    sql_map = {
        "personnel": "UPDATE personnel_incident SET status = ? WHERE id = ?",
        "equipment": "UPDATE equipment_incident SET status = ? WHERE id = ?",
        "vehicle": "UPDATE vehicle_incident SET status = ? WHERE id = ?",
        "aircraft": "UPDATE aircraft_incident SET status = ? WHERE id = ?",
    }
    from utils.db import get_incident_conn
    with get_incident_conn() as conn:
        conn.execute(sql_map[entity_type], (status, entity_id))
        conn.commit()
