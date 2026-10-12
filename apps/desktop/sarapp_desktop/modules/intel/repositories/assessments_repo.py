"""Assessments repository — API-backed."""

from __future__ import annotations

from typing import Optional

from utils.api_client import api_client, APIError
from modules.intel.models.assessments import Assessment


class AssessmentsRepository:
    """CRUD operations for Intel assessments via the server API."""

    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._base = f"/api/incidents/{incident_id}/intel/assessments"

    def list(
        self,
        status: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list[Assessment]:
        params: dict = {"include_deleted": include_deleted}
        if status:
            params["status"] = status
        try:
            data = api_client.get(self._base, params=params)
            return [Assessment.from_api(d) for d in (data or [])]
        except APIError:
            return []

    def get(self, assessment_id: str) -> Optional[Assessment]:
        try:
            data = api_client.get(f"{self._base}/{assessment_id}")
            return Assessment.from_api(data)
        except APIError:
            return None

    def create(self, assessment: Assessment) -> Optional[Assessment]:
        try:
            data = api_client.post(self._base, json=assessment.to_api_dict())
            return Assessment.from_api(data)
        except APIError:
            return None

    def update(self, assessment_id: str, updates: dict) -> Optional[Assessment]:
        try:
            data = api_client.patch(f"{self._base}/{assessment_id}", json=updates)
            return Assessment.from_api(data)
        except APIError:
            return None

    def archive(self, assessment_id: str) -> bool:
        try:
            api_client.delete(f"{self._base}/{assessment_id}")
            return True
        except APIError:
            return False

    def link_subject(self, assessment_id: str, subject_id: str) -> Optional[Assessment]:
        current = self.get(assessment_id)
        if current is None:
            return None
        ids = list(current.linked_subject_ids or [])
        if subject_id not in ids:
            ids.append(subject_id)
        return self.update(assessment_id, {"linked_subject_ids": ids})

    def unlink_subject(self, assessment_id: str, subject_id: str) -> Optional[Assessment]:
        current = self.get(assessment_id)
        if current is None:
            return None
        ids = [s for s in (current.linked_subject_ids or []) if s != subject_id]
        return self.update(assessment_id, {"linked_subject_ids": ids})

    def link_item(self, assessment_id: str, item_id: str) -> Optional[Assessment]:
        current = self.get(assessment_id)
        if current is None:
            return None
        ids = list(current.linked_item_ids or [])
        if item_id not in ids:
            ids.append(item_id)
        return self.update(assessment_id, {"linked_item_ids": ids})

    def unlink_item(self, assessment_id: str, item_id: str) -> Optional[Assessment]:
        current = self.get(assessment_id)
        if current is None:
            return None
        ids = [i for i in (current.linked_item_ids or []) if i != item_id]
        return self.update(assessment_id, {"linked_item_ids": ids})
