"""Intel Items repository — API-backed."""

from __future__ import annotations

from typing import Optional

from utils.api_client import api_client, APIError
from modules.intel.models.intel_items import IntelItem, Observation


class IntelItemsRepository:
    """CRUD operations for Intel items and their embedded observations."""

    def __init__(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._base = f"/api/incidents/{incident_id}/intel/items"

    def list(
        self,
        item_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        trend: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list[IntelItem]:
        params: dict = {"include_deleted": include_deleted}
        if item_type:
            params["item_type"] = item_type
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        if trend:
            params["trend"] = trend
        try:
            data = api_client.get(self._base, params=params)
            return [IntelItem.from_api(d) for d in (data or [])]
        except APIError:
            return []

    def get(self, item_id: str) -> Optional[IntelItem]:
        try:
            data = api_client.get(f"{self._base}/{item_id}")
            return IntelItem.from_api(data)
        except APIError:
            return None

    def create(self, item: IntelItem) -> Optional[IntelItem]:
        try:
            data = api_client.post(self._base, json=item.to_api_dict())
            return IntelItem.from_api(data)
        except APIError:
            return None

    def update(self, item_id: str, updates: dict) -> Optional[IntelItem]:
        try:
            data = api_client.patch(f"{self._base}/{item_id}", json=updates)
            return IntelItem.from_api(data)
        except APIError:
            return None

    def archive(self, item_id: str) -> bool:
        try:
            api_client.delete(f"{self._base}/{item_id}")
            return True
        except APIError:
            return False

    def add_observation(self, item_id: str, obs: Observation) -> Optional[IntelItem]:
        """Append an observation to the item's embedded observations array."""
        try:
            data = api_client.post(
                f"{self._base}/{item_id}/observations",
                json=obs.to_api_dict(),
            )
            return IntelItem.from_api(data)
        except APIError:
            return None

    def update_observation(
        self, item_id: str, obs_id: str, updates: dict
    ) -> Optional[IntelItem]:
        try:
            data = api_client.patch(
                f"{self._base}/{item_id}/observations/{obs_id}",
                json=updates,
            )
            return IntelItem.from_api(data)
        except APIError:
            return None
