from __future__ import annotations

"""Repository managing incident-specific communication plans.

Plan rows only ever store a reference (``master_id``) plus incident-specific
fields (assignment, priority, encryption, remarks) - channel identity always
comes live from the master catalog. See ``ApiIncidentRepository`` below and
the matching server-side join in
``data/db/sarapp_db/api/routers/communications.py``.
"""

from typing import Any, Dict, List


def infer_band(freq: float | None) -> str:
    """Infer a band string from ``freq`` in MHz."""
    if freq is None:
        return "Other"
    f = float(freq)
    if 3 <= f < 30:
        return "HF"
    if 30 <= f < 54:
        return "VHF-LOW"
    if 118 <= f <= 137:
        return "Air"
    if 156 <= f <= 163:
        return "Marine"
    if 54 <= f < 300:
        return "VHF"
    if 300 <= f < 700:
        return "UHF"
    if 700 <= f <= 869:
        return "700/800"
    return "Other"


class ApiIncidentRepository:
    """IncidentRepository backed by the SARApp API (MongoDB)."""

    def __init__(self, incident_number: str | int):
        self._incident_id = str(incident_number)
        self._base = f"/api/incidents/{self._incident_id}/channels-plan"
        self._plan_base = f"/api/incidents/{self._incident_id}/communications-plan"

    def list_plan(self) -> List[Dict[str, Any]]:
        from utils.api_client import api_client
        return api_client.get(self._base)

    def add_from_master(self, master_id: int, defaults: Dict[str, Any] | None = None) -> Dict[str, Any]:
        from utils.api_client import api_client
        return api_client.post(self._base, json={"master_id": master_id, "defaults": defaults or {}})

    def get_row(self, row_id: int) -> Dict[str, Any]:
        from utils.api_client import api_client
        try:
            return api_client.get(f"{self._base}/{row_id}")
        except Exception:
            return {}

    def update_row(self, row_id: int, patch: Dict[str, Any]) -> None:
        from utils.api_client import api_client
        api_client.put(f"{self._base}/{row_id}", json=patch)

    def delete_row(self, row_id: int) -> None:
        from utils.api_client import api_client
        api_client.delete(f"{self._base}/{row_id}")

    def reorder(self, row_id: int, direction: str) -> None:
        from utils.api_client import api_client
        api_client.patch(f"{self._base}/{row_id}/reorder", json={"direction": direction})

    def validate_plan(self) -> Dict[str, Any]:
        from utils.api_client import api_client
        return api_client.get(f"{self._base}/validate")

    def preview_rows(self) -> List[Dict[str, Any]]:
        from utils.api_client import api_client
        return api_client.get(f"{self._base}/preview")

    def get_plan(self, op_period_id: str | None = None) -> Dict[str, Any]:
        from utils.api_client import api_client
        try:
            params = {"op_period_id": op_period_id} if op_period_id is not None else None
            return api_client.get(self._plan_base, params=params)
        except Exception:
            return {"special_instructions": "", "op_period_id": None}

    def save_plan(self, special_instructions: str, op_period_id: str | None) -> Dict[str, Any]:
        from utils.api_client import api_client
        return api_client.put(
            self._plan_base,
            json={
                "special_instructions": special_instructions,
                "op_period_id": op_period_id,
            },
        )


__all__ = ["ApiIncidentRepository", "infer_band"]
