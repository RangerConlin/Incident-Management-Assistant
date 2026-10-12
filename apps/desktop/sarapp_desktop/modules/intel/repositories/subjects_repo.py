"""Subjects repository — API-backed."""

from __future__ import annotations

from typing import Optional

from utils.api_client import api_client, APIError
from modules.intel.models.subjects import Subject


class SubjectsRepository:
    """CRUD operations for Intel subjects via the server API."""

    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._base = f"/api/incidents/{incident_id}/intel/subjects"

    def list(
        self,
        subject_type: Optional[str] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list[Subject]:
        params: dict = {"include_deleted": include_deleted}
        if subject_type:
            params["subject_type"] = subject_type
        if status:
            params["status"] = status
        try:
            data = api_client.get(self._base, params=params)
            return [Subject.from_api(d) for d in (data or [])]
        except APIError:
            return []

    def get(self, subject_id: str) -> Optional[Subject]:
        try:
            data = api_client.get(f"{self._base}/{subject_id}")
            return Subject.from_api(data)
        except APIError:
            return None

    def create(self, subject: Subject) -> Optional[Subject]:
        try:
            data = api_client.post(self._base, json=subject.to_api_dict())
            return Subject.from_api(data)
        except APIError:
            return None

    def update(self, subject_id: str, updates: dict) -> Optional[Subject]:
        try:
            data = api_client.patch(f"{self._base}/{subject_id}", json=updates)
            return Subject.from_api(data)
        except APIError:
            return None

    def archive(self, subject_id: str) -> bool:
        try:
            api_client.delete(f"{self._base}/{subject_id}")
            return True
        except APIError:
            return False
