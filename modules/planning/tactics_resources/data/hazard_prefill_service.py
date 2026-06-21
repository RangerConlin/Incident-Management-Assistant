"""
HazardPrefillService
====================
Auto-suggests hazards for a Work Assignment based on its resource types.
Reads from the Hazard Type Library (MongoDB) via the SARApp API.
"""
from __future__ import annotations

from typing import Any


def _client():
    from utils.api_client import api_client
    return api_client


class HazardPrefillService:
    """
    Suggests and applies default hazards to a Work Assignment.

    Usage:
        svc = HazardPrefillService()
        added, skipped = svc.apply_default_hazards(work_assignment_id)
    """

    def _get_hazard_types_for_resource_type(self, resource_type_id: int) -> list[dict[str, Any]]:
        try:
            return _client().get(f"/api/hazard-types/by-resource-type/{resource_type_id}") or []
        except Exception:
            return []

    def get_default_hazards_for_resource_type(self, resource_type_id: int) -> list[dict[str, Any]]:
        return self._get_hazard_types_for_resource_type(resource_type_id)

    def suggest_hazards_for_assignment(self, work_assignment_id: int) -> list[dict[str, Any]]:
        from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
        try:
            repo = WorkAssignmentRepository()
            requirements = repo.list_resource_requirements(work_assignment_id)
        except Exception:
            return []

        seen_hazard_type_ids: set[int] = set()
        suggestions: list[dict[str, Any]] = []

        for req in requirements:
            if req.resource_type_id is None:
                continue
            for ht in self._get_hazard_types_for_resource_type(req.resource_type_id):
                htid = ht.get("id") or ht.get("hazard_type_id")
                if htid and htid in seen_hazard_type_ids:
                    continue
                if htid:
                    seen_hazard_type_ids.add(htid)
                suggestions.append(ht)

        return suggestions

    def build_hazard_from_hazard_type(self, hazard_type_id: int) -> dict[str, Any]:
        try:
            ht = _client().get(f"/api/hazard-types/{hazard_type_id}")
            if not ht:
                return {}
        except Exception:
            return {}

        mitigation_text = "; ".join(
            m.get("mitigation_text") or m.get("text") or ""
            for m in (ht.get("mitigations") or [])[:3]
            if m.get("mitigation_text") or m.get("text")
        )
        ppe_text = "; ".join(
            p.get("ppe_text") or p.get("text") or ""
            for p in (ht.get("ppe_items") or [])[:3]
            if p.get("ppe_text") or p.get("text")
        )

        return {
            "hazard_type_id": hazard_type_id,
            "hazard_type_text": ht.get("name") or ht.get("hazard_type_text") or "",
            "category": ht.get("category") or "",
            "risk_level": ht.get("default_risk_level") or "Unknown",
            "likelihood": ht.get("default_likelihood") or "Unknown",
            "severity": ht.get("default_severity") or "Unknown",
            "control_measure": ht.get("default_control_measure") or "",
            "mitigation_text": mitigation_text or ht.get("default_mitigation") or "",
            "ppe_text": ppe_text,
            "safety_message": ht.get("default_safety_message") or "",
            "source": "Default from Hazard Library",
        }

    def apply_default_hazards(self, work_assignment_id: int) -> tuple[int, int]:
        from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
        try:
            repo = WorkAssignmentRepository()
            existing = repo.list_hazards(work_assignment_id)
        except Exception:
            return 0, 0

        existing_htids: set[int] = {
            h.hazard_type_id for h in existing if h.hazard_type_id is not None
        }

        suggestions = self.suggest_hazards_for_assignment(work_assignment_id)
        added = 0
        skipped = 0

        for ht in suggestions:
            htid = ht.get("id") or ht.get("hazard_type_id")
            if htid and int(htid) in existing_htids:
                skipped += 1
                continue
            hazard_data = self.build_hazard_from_hazard_type(int(htid)) if htid else {}
            if not hazard_data.get("hazard_type_text"):
                skipped += 1
                continue
            try:
                repo.add_hazard(work_assignment_id, hazard_data)
                if htid:
                    existing_htids.add(int(htid))
                added += 1
            except Exception:
                skipped += 1

        return added, skipped
