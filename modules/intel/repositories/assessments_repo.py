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
