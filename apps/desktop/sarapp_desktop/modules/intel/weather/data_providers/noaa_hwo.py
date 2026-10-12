"""NOAA Hazardous Weather Outlook text product provider."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .base import get_shared_client
from ..services import settings

LOGGER = logging.getLogger(__name__)

_NWS_POINTS_URL = "https://api.weather.gov/points"
_NWS_PRODUCTS_URL = "https://api.weather.gov/products"


class NoaaHwoProvider:
    """Fetch the latest HWO text product for a point.

    This implementation uses the official NWS API points endpoint to resolve
    the forecast office, then queries the text products API for the latest HWO.
    The exact product-location path is inferred from the documented products API
    shape, with a fallback query form to improve compatibility.
    """

    def fetch_hwo(
        self, latitude: float, longitude: float, office: str | None = None
    ) -> Dict[str, Any] | None:
        points_url, products_url, headers = _hwo_endpoints_and_headers()
        office = (office or "").strip().upper()
        try:
            client = get_shared_client()
            if not office:
                points_resp = client.get(
                    f"{points_url}/{latitude:.4f},{longitude:.4f}",
                    headers=headers,
                )
                points_resp.raise_for_status()
                point_props = (points_resp.json() or {}).get("properties") or {}
                office = str(point_props.get("cwa") or point_props.get("forecastOffice") or "").strip().upper()
                if office.startswith("HTTPS://API.WEATHER.GOV/OFFICES/"):
                    office = office.rsplit("/", 1)[-1].strip().upper()
            if not office:
                return None

            product = (
                self._fetch_latest_product_by_location(client, products_url, office, headers)
                or self._fetch_latest_product_by_query(client, products_url, office, headers)
            )
            if not product:
                return None

            product_id = str(product.get("@id") or product.get("id") or "").strip()
            if product_id.startswith("https://api.weather.gov/"):
                detail_url = product_id
            elif product_id:
                detail_url = f"{products_url}/{product_id}"
            else:
                detail_url = ""
            if not detail_url:
                return None

            detail_resp = client.get(detail_url, headers=headers)
            detail_resp.raise_for_status()
            detail = detail_resp.json() or {}
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to fetch HWO: %s", exc)
            return None

        return {
            "office": office,
            "time": detail.get("issuanceTime") or detail.get("issueTime") or "",
            "product_id": detail.get("id") or product_id,
            "text": detail.get("productText") or detail.get("productTextPlain") or "",
            "headline": detail.get("headline") or "Hazardous Weather Outlook",
            "url": detail_url,
        }

    @staticmethod
    def _fetch_latest_product_by_location(client, products_url: str, office: str, headers: Dict[str, str]) -> Dict[str, Any] | None:
        # NB: this endpoint rejects a "limit" query parameter with HTTP 400;
        # results are newest-first so the first entry is the latest product.
        resp = client.get(
            f"{products_url}/types/HWO/locations/{office}",
            headers=headers,
        )
        if resp.status_code >= 400:
            return None
        payload = resp.json() or {}
        products = payload.get("@graph") or payload.get("products") or []
        return products[0] if products else None

    @staticmethod
    def _fetch_latest_product_by_query(client, products_url: str, office: str, headers: Dict[str, str]) -> Dict[str, Any] | None:
        # The "office" filter requires a 4-letter WMO id; the CWA from the
        # points endpoint is 3 letters, so filter by "location" instead.
        resp = client.get(
            products_url,
            params={"type": "HWO", "limit": 1, "location": office},
            headers=headers,
        )
        if resp.status_code >= 400:
            return None
        payload = resp.json() or {}
        products = payload.get("@graph") or payload.get("products") or []
        return products[0] if products else None


def _hwo_endpoints_and_headers() -> tuple[str, str, Dict[str, str]]:
    cfg = settings.load_api_config(Path("modules/intel/weather/settings/api_config.json"))
    providers: Dict[str, Any] = cfg.get("providers", {}) if isinstance(cfg, dict) else {}
    hwo_cfg: Dict[str, Any] = providers.get("hwo", {})
    points_url = (hwo_cfg.get("points_url") or _NWS_POINTS_URL).rstrip("/")
    products_url = (hwo_cfg.get("products_url") or _NWS_PRODUCTS_URL).rstrip("/")
    user_agent: str = (
        hwo_cfg.get("user_agent")
        or "IncidentManagementAssistant/1.0 (contact: admin@example.invalid)"
    )
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/geo+json, application/json;q=0.9",
    }
    return points_url, products_url, headers


__all__ = ["NoaaHwoProvider"]
