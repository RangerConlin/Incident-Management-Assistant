"""Background resolution of NWS location codes for incident locations.

Watches facility and ICP coordinates and resolves each one to the NWS
metadata needed by other weather queries (forecast office, gridpoint,
forecast URLs, nearby observation stations). Resolved codes are cached
locally and persisted per-incident through the API server so every client
can skip the points lookup.
"""

from __future__ import annotations

import concurrent.futures
import functools
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Signal

from ..data_providers.nws_points import NwsPointsProvider
from . import cache

LOGGER = logging.getLogger(__name__)

_POLL_MINUTES = 30
_CACHE_NAME = "nws_location_codes"


class NwsLocationCodeService(QObject):
    """Resolves known incident coordinates to NWS location codes in the background."""

    codesUpdated = Signal(dict)

    _instance: "NwsLocationCodeService" | None = None

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("nwsLocationCodeService")
        self._provider = NwsPointsProvider()
        self._codes: Dict[str, Dict[str, Any]] = {}
        self._pending: set[str] = set()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_now)
        self._timer.start(_POLL_MINUTES * 60_000)
        self._load_persisted()
        QTimer.singleShot(0, self.refresh_now)
        LOGGER.info(
            "NwsLocationCodeService started with %s minute polling (%d cached)",
            _POLL_MINUTES,
            len(self._codes),
        )

    @classmethod
    def instance(cls) -> "NwsLocationCodeService":
        if cls._instance is None:
            cls._instance = NwsLocationCodeService()
        return cls._instance

    @staticmethod
    def location_key(latitude: float, longitude: float) -> str:
        return f"{float(latitude):.4f},{float(longitude):.4f}"

    def codes_for(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        return self._codes.get(self.location_key(latitude, longitude))

    def office_for(self, latitude: float, longitude: float) -> Optional[str]:
        office = str((self.codes_for(latitude, longitude) or {}).get("office") or "").strip().upper()
        return office or None

    def forecast_url_for(self, latitude: float, longitude: float) -> Optional[str]:
        url = str((self.codes_for(latitude, longitude) or {}).get("forecast_url") or "").strip()
        return url or None

    def stations_for(self, latitude: float, longitude: float) -> List[str]:
        stations = (self.codes_for(latitude, longitude) or {}).get("stations") or []
        return [str(item).upper() for item in stations if item]

    def all_codes(self) -> Dict[str, Dict[str, Any]]:
        return {key: dict(value) for key, value in self._codes.items()}

    def refresh_now(self) -> None:
        for label, latitude, longitude in self._gather_locations():
            key = self.location_key(latitude, longitude)
            existing = self._codes.get(key)
            if existing is not None:
                if label and existing.get("label") != label:
                    existing["label"] = label
                continue
            if key in self._pending:
                continue
            self._pending.add(key)
            LOGGER.debug("Resolving NWS location codes for %s (%s)", label or key, key)
            self._run_async(
                functools.partial(self._provider.resolve, latitude, longitude),
                functools.partial(self._on_resolved, key, label, latitude, longitude),
            )

    def _gather_locations(self) -> List[Tuple[str, float, float]]:
        locations: List[Tuple[str, float, float]] = []
        try:
            from utils.incident_meta import get_icp_location

            icp = get_icp_location()
            if icp and icp.latitude is not None and icp.longitude is not None:
                locations.append(("ICP", float(icp.latitude), float(icp.longitude)))
        except Exception:
            pass
        try:
            from modules.logistics.facilities.service import FacilitiesService

            for facility in FacilitiesService().list_facilities(status="active"):
                if facility.latitude is None or facility.longitude is None:
                    continue
                locations.append(
                    (facility.name, float(facility.latitude), float(facility.longitude))
                )
        except Exception:
            LOGGER.debug("Facility list unavailable for NWS location resolution", exc_info=True)
        return locations

    def _run_async(self, func: Callable[[], Any], callback: Callable[[Any], None]) -> None:
        future = self._executor.submit(func)

        def _done(f: concurrent.futures.Future) -> None:
            try:
                result = f.result()
            except Exception:  # noqa: BLE001
                LOGGER.exception("NWS location code resolution failed")
                result = None
            QTimer.singleShot(0, lambda: callback(result))

        future.add_done_callback(_done)

    def _on_resolved(
        self,
        key: str,
        label: str,
        latitude: float,
        longitude: float,
        payload: Optional[Dict[str, Any]],
    ) -> None:
        self._pending.discard(key)
        if not payload:
            return
        entry = dict(payload)
        entry["label"] = label
        entry["latitude"] = latitude
        entry["longitude"] = longitude
        self._codes[key] = entry
        cache.write_cache(_CACHE_NAME, self._codes)
        self.codesUpdated.emit(self.all_codes())
        self._save_to_server()

    def _load_persisted(self) -> None:
        entries: List[Dict[str, Any]] = []
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id

            incident_id = get_active_incident_id()
            if incident_id:
                payload = api_client.get(f"/api/incidents/{incident_id}/weather/location-codes") or {}
                entries = [item for item in (payload.get("codes") or []) if isinstance(item, dict)]
        except Exception:
            LOGGER.warning("Could not load NWS location codes from server, using local cache")
        if not entries:
            cached = cache.read_cache(_CACHE_NAME) or {}
            entries = [item for item in cached.values() if isinstance(item, dict)]
        for item in entries:
            try:
                key = self.location_key(float(item["latitude"]), float(item["longitude"]))
            except Exception:  # noqa: BLE001
                continue
            self._codes[key] = dict(item)

    def _save_to_server(self) -> None:
        try:
            from utils.api_client import api_client
            from utils.incident_context import get_active_incident_id

            incident_id = get_active_incident_id()
            if not incident_id:
                return
            payload = {"codes": list(self._codes.values())}
            self._executor.submit(
                lambda: api_client.post(
                    f"/api/incidents/{incident_id}/weather/location-codes", json=payload
                )
            )
        except Exception:
            LOGGER.exception("Failed to post NWS location codes to server")


__all__ = ["NwsLocationCodeService"]
