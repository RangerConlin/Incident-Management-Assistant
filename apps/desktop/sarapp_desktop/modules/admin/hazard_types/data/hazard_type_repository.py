"""MongoDB-backed Hazard Type repository via SARApp API."""
from __future__ import annotations

from typing import Any, Optional

from ..models.hazard_type_models import (
    HazardDefaultSpe,
    HazardType,
    HazardTypeSearchResult,
    SAFETY_SCENARIO_TYPES,
    SAFETY_TARGET_FORMS,
    SafetyAnalysisTemplate,
    SafetyTemplateHazardEntry,
)

_CATALOG_HAZARD_TYPES = "hazard_types"
_CATALOG_SAFETY_TEMPLATES = "safety_analysis_templates"


def _invalidate_hazard_type_catalog() -> None:
    """Call after any write that changes hazard type documents."""
    from utils.catalog_cache import catalog_cache
    catalog_cache.invalidate(_CATALOG_HAZARD_TYPES)


def _invalidate_safety_template_catalog() -> None:
    """Call after any write that changes safety analysis template documents."""
    from utils.catalog_cache import catalog_cache
    catalog_cache.invalidate(_CATALOG_SAFETY_TEMPLATES)


class ApiHazardTypeRepository:
    """Repository that calls the FastAPI hazard type endpoints."""

    def list_hazard_types(self, filters: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        f = filters or {}
        params: dict[str, Any] = {}
        search_text = f.get("search_text")
        if search_text:
            params["search_text"] = search_text
        if f.get("category") and f["category"] != "All":
            params["category"] = f["category"]
        if f.get("active_filter"):
            params["active_filter"] = f["active_filter"]
        if f.get("include_inactive"):
            params["include_inactive"] = True

        if not search_text:
            from utils.catalog_cache import catalog_cache
            return catalog_cache.get(_CATALOG_HAZARD_TYPES, "/api/hazard-types", params=params) or []

        from utils.api_client import api_client
        return api_client.get("/api/hazard-types", params=params) or []

    def search_hazard_types(
        self, query: str, include_inactive: bool = False, limit: int = 20
    ) -> list[HazardTypeSearchResult]:
        from utils.api_client import api_client

        if not query.strip():
            return []
        data = api_client.get(
            "/api/hazard-types/search",
            params={"q": query, "include_inactive": include_inactive, "limit": limit},
        ) or []
        return [
            HazardTypeSearchResult(
                hazard_type_id=d.get("id"),
                hazard_type_text=d.get("name", ""),
                category=d.get("category", ""),
                default_spe_band=d.get("default_spe_band", ""),
                matched_on=d.get("matched_on", ""),
            )
            for d in data
        ]

    def get_hazard_type(self, hazard_type_id: int) -> Optional[HazardType]:
        from utils.api_client import APIError
        from utils.catalog_cache import catalog_cache

        try:
            doc = catalog_cache.get(_CATALOG_HAZARD_TYPES, f"/api/hazard-types/{hazard_type_id}")
        except APIError as exc:
            if getattr(exc, "status_code", None) == 404:
                return None
            raise
        if doc is None:
            return None
        return _api_doc_to_hazard_type(doc)

    def create_hazard_type(self, data: HazardType | dict[str, Any]) -> int:
        from utils.api_client import api_client

        result = api_client.post("/api/hazard-types", json=_hazard_type_to_api_doc(data))
        _invalidate_hazard_type_catalog()
        return int(result["id"])

    def update_hazard_type(self, hazard_type_id: int, data: HazardType | dict[str, Any]) -> int:
        from utils.api_client import api_client

        result = api_client.put(
            f"/api/hazard-types/{hazard_type_id}",
            json=_hazard_type_to_api_doc(data),
        )
        _invalidate_hazard_type_catalog()
        return int(result["id"])

    def clone_hazard_type(self, hazard_type_id: int) -> int:
        from utils.api_client import api_client

        result = api_client.post(f"/api/hazard-types/{hazard_type_id}/clone")
        _invalidate_hazard_type_catalog()
        return int(result["id"])

    def deactivate_hazard_type(self, hazard_type_id: int) -> None:
        from utils.api_client import api_client

        api_client.patch(
            f"/api/hazard-types/{hazard_type_id}/active",
            json={"active": False},
        )
        _invalidate_hazard_type_catalog()

    def reactivate_hazard_type(self, hazard_type_id: int) -> None:
        from utils.api_client import api_client

        api_client.patch(
            f"/api/hazard-types/{hazard_type_id}/active",
            json={"active": True},
        )
        _invalidate_hazard_type_catalog()


def _api_doc_to_hazard_type(doc: dict[str, Any]) -> HazardType:
    default_spe_doc = doc.get("default_spe") or {}
    default_spe = None
    if default_spe_doc:
        default_spe = HazardDefaultSpe(
            severity=int(default_spe_doc.get("severity") or 0),
            probability=int(default_spe_doc.get("probability") or 0),
            exposure=int(default_spe_doc.get("exposure") or 0),
            score=int(default_spe_doc.get("score") or 0),
            band=str(default_spe_doc.get("band") or ""),
            action=str(default_spe_doc.get("action") or ""),
        )

    return HazardType(
        id=int(doc.get("id")) if doc.get("id") is not None else None,
        name=doc.get("name", ""),
        category=doc.get("category", "Other"),
        description=doc.get("description", ""),
        aliases=list(doc.get("aliases") or []),
        controls=[str(value) for value in (doc.get("controls") or []) if str(value).strip()],
        ppe=[str(value) for value in (doc.get("ppe") or []) if str(value).strip()],
        standard_safety_language=doc.get("standard_safety_language", ""),
        default_spe=default_spe,
        active=bool(doc.get("active", True)),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        created_by=doc.get("created_by", ""),
        updated_by=doc.get("updated_by", ""),
    )


class ApiSafetyTemplateRepository:
    """CRUD repository for Safety Analysis Templates via the FastAPI server."""

    def list_templates(
        self,
        search_text: str = "",
        scenario_type: str = "All",
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"include_inactive": include_inactive}
        if search_text:
            params["search_text"] = search_text
        if scenario_type and scenario_type != "All":
            params["scenario_type"] = scenario_type

        if not search_text:
            from utils.catalog_cache import catalog_cache
            return catalog_cache.get(_CATALOG_SAFETY_TEMPLATES, "/api/master/safety-templates", params=params) or []

        from utils.api_client import api_client
        return api_client.get("/api/master/safety-templates", params=params) or []

    def get_template(self, template_id: int) -> Optional[SafetyAnalysisTemplate]:
        from utils.api_client import APIError
        from utils.catalog_cache import catalog_cache

        try:
            doc = catalog_cache.get(_CATALOG_SAFETY_TEMPLATES, f"/api/master/safety-templates/{template_id}")
        except APIError as exc:
            if getattr(exc, "status_code", None) == 404:
                return None
            raise
        if doc is None:
            return None
        return _doc_to_template(doc)

    def create_template(self, data: dict[str, Any]) -> int:
        from utils.api_client import api_client

        result = api_client.post("/api/master/safety-templates", json=data)
        _invalidate_safety_template_catalog()
        return int(result["template_id"])

    def update_template(self, template_id: int, data: dict[str, Any]) -> int:
        from utils.api_client import api_client

        result = api_client.put(f"/api/master/safety-templates/{template_id}", json=data)
        _invalidate_safety_template_catalog()
        return int(result["template_id"])

    def delete_template(self, template_id: int) -> None:
        from utils.api_client import api_client

        api_client.delete(f"/api/master/safety-templates/{template_id}")
        _invalidate_safety_template_catalog()

    def clone_template(self, template_id: int) -> int:
        from utils.api_client import api_client

        result = api_client.post(f"/api/master/safety-templates/{template_id}/clone")
        _invalidate_safety_template_catalog()
        return int(result["template_id"])

    def set_active(self, template_id: int, active: bool) -> None:
        from utils.api_client import api_client

        api_client.patch(
            f"/api/master/safety-templates/{template_id}/active",
            json={"active": active},
        )
        _invalidate_safety_template_catalog()


def _doc_to_template(doc: dict[str, Any]) -> SafetyAnalysisTemplate:
    int_id = doc.get("template_id")
    try:
        int_id = int(int_id) if int_id is not None else None
    except (ValueError, TypeError):
        int_id = None
    return SafetyAnalysisTemplate(
        id=int_id,
        name=doc.get("name", ""),
        description=doc.get("description", ""),
        scenario_type=doc.get("scenario_type", "General"),
        target_forms=list(doc.get("target_forms") or []),
        is_active=bool(doc.get("is_active", True)),
        notes=doc.get("notes", ""),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        created_by=doc.get("created_by", ""),
        updated_by=doc.get("updated_by", ""),
        hazard_entries=[
            SafetyTemplateHazardEntry(
                hazard_type_id=int(e.get("hazard_type_id", 0)),
                sort_order=int(e.get("sort_order", 0)),
                override_notes=e.get("override_notes", ""),
                hazard_name=e.get("hazard_name", ""),
                hazard_category=e.get("hazard_category", ""),
                default_spe_band=e.get("default_spe_band", ""),
            )
            for e in (doc.get("hazard_entries") or [])
        ],
    )


def _hazard_type_to_api_doc(ht: HazardType | dict[str, Any]) -> dict[str, Any]:
    if isinstance(ht, dict):
        return ht
    default_spe = ht.default_spe or HazardDefaultSpe(
        severity=1,
        probability=1,
        exposure=1,
        score=1,
        band="Slight",
        action="Possibly Acceptable",
    )
    return {
        "name": ht.name,
        "category": ht.category,
        "description": ht.description,
        "aliases": list(ht.aliases),
        "controls": list(ht.controls),
        "ppe": list(ht.ppe),
        "standard_safety_language": ht.standard_safety_language,
        "default_spe": {
            "severity": default_spe.severity,
            "probability": default_spe.probability,
            "exposure": default_spe.exposure,
        },
        "active": ht.active,
        "created_by": ht.created_by,
        "updated_by": ht.updated_by,
    }
