"""
HazardPrefillService
====================
Auto-suggests hazards for a Work Assignment based on its resource types.

Reads from the Hazard Type Library (master.db) via HazardTypeRepository.
The master library stores default hazard→resource-type mappings.

This service is kept separate so the prefill logic can be improved
without touching the repository or UI.
"""
from __future__ import annotations

from typing import Any


class HazardPrefillService:
    """
    Suggests and applies default hazards to a Work Assignment.

    Usage:
        svc = HazardPrefillService()
        added, skipped = svc.apply_default_hazards(work_assignment_id)
    """

    def __init__(self) -> None:
        self._hazard_repo: Any = None

    def _get_hazard_repo(self):
        if self._hazard_repo is None:
            try:
                from modules.admin.hazard_types.data.hazard_type_repository import (
                    HazardTypeRepository,
                )
                self._hazard_repo = HazardTypeRepository()
            except Exception:
                self._hazard_repo = None
        return self._hazard_repo

    def _get_hazard_types_for_resource_type(self, resource_type_id: int) -> list[dict[str, Any]]:
        """
        Query the Hazard Type Library for hazard types linked as defaults
        for the given resource type.

        The library stores this in a hazard_type_resource_defaults table
        (populated by HazardTypeRepository.list_resource_defaults).
        We query it in reverse: hazards that list this resource type as a default.
        """
        repo = self._get_hazard_repo()
        if repo is None:
            return []
        try:
            # list_resource_defaults(hazard_type_id) returns the resource types
            # linked TO a hazard.  We need the reverse: hazards linked to a resource.
            # Query the underlying DB directly if the repo does not expose this method.
            if hasattr(repo, "_connect"):
                with repo._connect() as con:
                    rows = con.execute(
                        """SELECT DISTINCT hazard_type_id
                           FROM hazard_type_resource_defaults
                           WHERE resource_type_id = ?""",
                        (resource_type_id,),
                    ).fetchall()
                hazard_type_ids = [r[0] for r in rows]
            elif hasattr(repo, "get_hazards_for_resource_type"):
                # If the repo ever adds this method, use it
                return repo.get_hazards_for_resource_type(resource_type_id)
            else:
                return []

            hazard_types = []
            for htid in hazard_type_ids:
                ht = repo.get_hazard_type(htid)
                if ht:
                    hazard_types.append(ht if isinstance(ht, dict) else ht.__dict__)
            return hazard_types
        except Exception:
            # Table may not exist on older databases — degrade gracefully
            return []

    def get_default_hazards_for_resource_type(
        self, resource_type_id: int
    ) -> list[dict[str, Any]]:
        """Return default hazard type dicts for a given resource type ID."""
        return self._get_hazard_types_for_resource_type(resource_type_id)

    def suggest_hazards_for_assignment(self, work_assignment_id: int) -> list[dict[str, Any]]:
        """
        Return a list of hazard dicts that should be added to this work assignment
        based on its current resource type requirements.

        Does NOT write to the DB — call apply_default_hazards to persist.
        """
        from modules.planning.tactics_resources.data.work_assignment_repository import (
            WorkAssignmentRepository,
        )
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
            hazard_types = self._get_hazard_types_for_resource_type(req.resource_type_id)
            for ht in hazard_types:
                htid = ht.get("id") or ht.get("hazard_type_id")
                if htid and htid in seen_hazard_type_ids:
                    continue
                if htid:
                    seen_hazard_type_ids.add(htid)
                suggestions.append(ht)

        return suggestions

    def build_hazard_from_hazard_type(self, hazard_type_id: int) -> dict[str, Any]:
        """
        Build a work_assignment_hazards data dict pre-filled from a library hazard type.

        The caller should save this dict via WorkAssignmentRepository.add_hazard().
        """
        repo = self._get_hazard_repo()
        if repo is None:
            return {}
        try:
            ht = repo.get_hazard_type(hazard_type_id)
            if not ht:
                return {}
            d = ht if isinstance(ht, dict) else ht.__dict__

            # Pull first mitigation and PPE text from the library if available
            mitigation_text = ""
            ppe_text = ""
            try:
                mitigations = repo.list_mitigations(hazard_type_id) if hasattr(repo, "list_mitigations") else []
                if mitigations:
                    mitigation_text = "; ".join(
                        m.get("mitigation_text", "") or m.get("text", "") for m in mitigations[:3]
                    )
            except Exception:
                pass
            try:
                ppe_list = repo.list_ppe(hazard_type_id)
                if ppe_list:
                    ppe_text = "; ".join(
                        p.get("ppe_text", "") or p.get("text", "") for p in ppe_list[:3]
                    )
            except Exception:
                pass

            return {
                "hazard_type_id": hazard_type_id,
                "hazard_type_text": d.get("name", "") or d.get("hazard_type_text", ""),
                "category": d.get("category", ""),
                "risk_level": d.get("default_risk_level", "Unknown") or "Unknown",
                "likelihood": d.get("default_likelihood", "Unknown") or "Unknown",
                "severity": d.get("default_severity", "Unknown") or "Unknown",
                "control_measure": d.get("default_control_measure", ""),
                "mitigation_text": mitigation_text or d.get("default_mitigation", ""),
                "ppe_text": ppe_text,
                "safety_message": d.get("default_safety_message", ""),
                "source": "Default from Hazard Library",
            }
        except Exception:
            return {}

    def apply_default_hazards(self, work_assignment_id: int) -> tuple[int, int]:
        """
        Apply default hazards to the work assignment based on its resource types.

        Skips hazards already present (matched by hazard_type_id) to avoid duplicates.
        Returns (added_count, skipped_count).
        """
        from modules.planning.tactics_resources.data.work_assignment_repository import (
            WorkAssignmentRepository,
        )
        try:
            repo = WorkAssignmentRepository()
            existing = repo.list_hazards(work_assignment_id)
        except Exception:
            return 0, 0

        # Build a set of hazard_type_ids already on this assignment
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
