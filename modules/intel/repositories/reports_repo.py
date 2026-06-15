"""Reports repository — API-backed."""

from __future__ import annotations

from typing import Optional

from utils.api_client import api_client, APIError
from modules.intel.models.reports import IntelReport


class ReportsRepository:
    """CRUD operations for Intel reports via the server API."""

    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._base = f"/api/incidents/{incident_id}/intel/reports"

    def list(
        self,
        status: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list[IntelReport]:
        params: dict = {"include_deleted": include_deleted}
        if status:
            params["status"] = status
        try:
            data = api_client.get(self._base, params=params)
            return [IntelReport.from_api(d) for d in (data or [])]
        except APIError:
            return []

    def get(self, report_id: str) -> Optional[IntelReport]:
        try:
            data = api_client.get(f"{self._base}/{report_id}")
            return IntelReport.from_api(data)
        except APIError:
            return None

    def create(self, report: IntelReport) -> Optional[IntelReport]:
        try:
            data = api_client.post(self._base, json=report.to_api_dict())
            return IntelReport.from_api(data)
        except APIError:
            return None

    def update(self, report_id: str, updates: dict) -> Optional[IntelReport]:
        try:
            data = api_client.patch(f"{self._base}/{report_id}", json=updates)
            return IntelReport.from_api(data)
        except APIError:
            return None

    def delete(self, report_id: str) -> bool:
        try:
            api_client.delete(f"{self._base}/{report_id}")
            return True
        except APIError:
            return False
