"""
Mock data providers for widgets. Replace with real APIs when ready.

TODOs:
 - incident.getSummary()
 - auth.getCurrentUser()
 - teams.getStatusSummary()
 - tasks.getSummary({active:true})
 - personnel.getAvailabilitySummary()
 - equipment.getSnapshot()
 - vehicles.getStatus(), aircraft.getStatus()
 - ops.getRecentEvents(limit)
 - comms.getRecentMessages(limit)
 - alerts.getAll({severity>=info})
 - comms.getPrimaryFrequencies()
 - comms.getCommsLog(limit)
 - planning.getObjectives(), getSITREP, getUpcomingTasks
 - safety.getAlerts()
 - medical.getIncidentLog(limit), get206Summary()
 - intel.getDashboard(), getClueLog(limit)
 - gis.getSnapshot(bounds|zoom)
 - pio.getPressDrafts(), getMediaLog(limit), getPendingApprovals()
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def incident_getSummary() -> Dict[str, Any]:
    return {
        "name": "Training Mission Bravo",
        "number": "IM-2025-0829",
        "type": "SAR",
        "status": "Active",
    }


def auth_getCurrentUser() -> Dict[str, Any]:
    return {
        "name": "j.doe",
        "role": "Planning Chief",
        "login": datetime.now(timezone.utc).isoformat(),
        "check_in": datetime.now(timezone.utc).isoformat(),
    }


def teams_getStatusSummary() -> Dict[str, int]:
    return {"available": 4, "assigned": 6, "out_of_service": 1}


def tasks_getSummary_active() -> Dict[str, int]:
    return {"draft": 2, "in_progress": 7, "completed": 12}


def personnel_getAvailabilitySummary() -> Dict[str, int]:
    return {"available": 18, "assigned": 22, "unavailable": 3, "pending": 2}


def equipment_getSnapshot() -> Dict[str, int]:
    return {"checked_in": 45, "assigned": 21, "out_of_service": 3}


def vehicles_getStatus() -> List[Dict[str, Any]]:
    return [
        {"unit": "V-1", "status": "Available"},
        {"unit": "ATV-2", "status": "Assigned"},
    ]


def aircraft_getStatus() -> List[Dict[str, Any]]:
    return [
        {"tail": "N123AB", "status": "On Standby"},
    ]


def ops_getRecentEvents(limit: int = 20) -> List[str]:
    return [f"Event {i}" for i in range(1, min(limit, 20) + 1)]


def comms_getRecentMessages(limit: int = 20) -> List[str]:
    return [f"Msg {i}" for i in range(1, min(limit, 20) + 1)]


def alerts_getAll_min_info() -> List[str]:
    return ["Safety: Heat index high", "Info: Ops period ends 1800Z"]


def comms_getPrimaryFrequencies() -> List[str]:
    return ["CH1 155.160", "CH5 155.340", "SAR 121.5"]


def comms_getCommsLog(limit: int = 50) -> List[str]:
    return [f"Log item {i}" for i in range(1, min(limit, 50) + 1)]


def planning_getObjectives() -> List[str]:
    return ["1. Ensure rescuer safety", "2. Locate subject"]


def planning_getSITREP(limit: int = 25) -> List[str]:
    return [f"SITREP {i}" for i in range(1, min(limit, 25) + 1)]


def planning_getUpcomingTasks() -> List[str]:
    return ["Brief G-2 at 0900L", "Prep medevac route"]


def safety_getAlerts() -> List[str]:
    return ["WASP hazard near sector C", "Slippery rocks by creek"]


def medical_getIncidentLog(limit: int = 25) -> List[str]:
    return [f"Medical entry {i}" for i in range(1, min(limit, 25) + 1)]


def medical_get206Summary() -> Dict[str, Any]:
    return {"hospitals": 3, "medevac": "AirCare-1", "plan": "Hydration & Rest"}


def intel_getDashboard() -> Dict[str, Any]:
    return {"clues": 5, "interviews": 3}


def intel_getClueLog(limit: int = 25) -> List[str]:
    return [f"Clue {i}" for i in range(1, min(limit, 25) + 1)]


def gis_getSnapshot() -> Dict[str, Any]:
    return {"layers": ["teams", "tasks", "hazards"], "zoom": 10}


def pio_getPressDrafts() -> List[str]:
    return ["Draft: Day 2 update", "Draft: Safety bulletin"]


def pio_getMediaLog(limit: int = 25) -> List[str]:
    return [f"Release {i}" for i in range(1, min(limit, 25) + 1)]


def pio_getPendingApprovals() -> List[str]:
    return ["Press release #3", "Community notice #2"]

