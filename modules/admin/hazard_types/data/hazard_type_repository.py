"""MongoDB-backed Hazard Type repository via SARApp API."""
from __future__ import annotations
from typing import Any, Optional

from ..models.hazard_type_models import (
    HazardType,
    HazardTypeSearchResult,
)

# Keep these for callsites that import them
from ..models.hazard_type_models import (
    HAZARD_CATEGORIES,
    HAZARD_LIKELIHOODS,
    HAZARD_RISK_LEVELS,
    HAZARD_SEVERITIES,
    HAZARD_SOURCES,
    SAFETY_SCENARIO_TYPES,
    SAFETY_TARGET_FORMS,
    HazardMitigation,
    HazardPpeItem,
    HazardReference,
    HazardTypeResourceDefault,
    SafetyAnalysisTemplate,
    SafetyTemplateHazardEntry,
)

class ApiHazardTypeRepository:
    """Drop-in replacement for HazardTypeRepository that calls the FastAPI server."""

    def list_hazard_types(self, filters: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        from utils.api_client import api_client
        f = filters or {}
        params: dict[str, Any] = {}
        if f.get("search_text"):
            params["search_text"] = f["search_text"]
        if f.get("category") and f["category"] != "All":
            params["category"] = f["category"]
        if f.get("source") and f["source"] != "All":
            params["source"] = f["source"]
        if f.get("risk_level") and f["risk_level"] != "All":
            params["risk_level"] = f["risk_level"]
        if f.get("active_filter"):
            params["active_filter"] = f["active_filter"]
        if f.get("include_inactive"):
            params["include_inactive"] = True
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
                hazard_type_id=d.get("hazard_type_id"),
                hazard_type_text=d.get("hazard_type_text", ""),
                category=d.get("category", ""),
                default_risk_level=d.get("default_risk_level", ""),
                source=d.get("source", ""),
                matched_on=d.get("matched_on", ""),
            )
            for d in data
        ]

    def get_hazard_type(self, hazard_type_id: int) -> Optional[HazardType]:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/hazard-types/{hazard_type_id}")
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
        return int(result["hazard_type_id"])

    def update_hazard_type(self, hazard_type_id: int, data: HazardType | dict[str, Any]) -> int:
        from utils.api_client import api_client
        result = api_client.put(
            f"/api/hazard-types/{hazard_type_id}",
            json=_hazard_type_to_api_doc(data),
        )
        return int(result["hazard_type_id"])

    def clone_hazard_type(self, hazard_type_id: int) -> int:
        from utils.api_client import api_client
        result = api_client.post(f"/api/hazard-types/{hazard_type_id}/clone")
        return int(result["hazard_type_id"])

    def deactivate_hazard_type(self, hazard_type_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/hazard-types/{hazard_type_id}/active",
            json={"active": False},
        )

    def reactivate_hazard_type(self, hazard_type_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/hazard-types/{hazard_type_id}/active",
            json={"active": True},
        )

    # Child-CRUD stubs kept for API surface compatibility; the full document
    # replace approach (create/update_hazard_type with embedded children) is
    # the preferred path.

    def list_aliases(self, hazard_type_id: int) -> list[dict[str, Any]]:
        ht = self.get_hazard_type(hazard_type_id)
        if ht is None:
            return []
        return [{"alias": a, "hazard_type_id": hazard_type_id} for a in ht.aliases]

    def list_mitigations(self, hazard_type_id: int) -> list[dict[str, Any]]:
        ht = self.get_hazard_type(hazard_type_id)
        if ht is None:
            return []
        return [
            {
                "mitigation_text": m.mitigation_text,
                "mitigation_category": m.mitigation_category,
                "is_default": m.is_default,
                "sort_order": m.sort_order,
                "hazard_type_id": hazard_type_id,
            }
            for m in ht.mitigations
        ]

    def list_ppe(self, hazard_type_id: int) -> list[dict[str, Any]]:
        ht = self.get_hazard_type(hazard_type_id)
        if ht is None:
            return []
        return [
            {
                "ppe_text": p.ppe_text,
                "is_default": p.is_default,
                "sort_order": p.sort_order,
                "hazard_type_id": hazard_type_id,
            }
            for p in ht.ppe_items
        ]

    def list_references(self, hazard_type_id: int) -> list[dict[str, Any]]:
        ht = self.get_hazard_type(hazard_type_id)
        if ht is None:
            return []
        return [
            {
                "title": r.title,
                "url_or_path": r.url_or_path,
                "notes": r.notes,
                "hazard_type_id": hazard_type_id,
            }
            for r in ht.references
        ]

    def list_resource_defaults(self, hazard_type_id: int) -> list[dict[str, Any]]:
        ht = self.get_hazard_type(hazard_type_id)
        if ht is None:
            return []
        return [
            {
                "resource_type_id": rd.resource_type_id,
                "notes": rd.notes,
                "hazard_type_id": hazard_type_id,
            }
            for rd in ht.resource_defaults
        ]

    def get_default_hazards_for_resource_type(self, resource_type_id: int) -> list[HazardType]:
        from utils.api_client import api_client
        docs = api_client.get(
            "/api/hazard-types",
            params={"active_filter": "Active"},
        ) or []
        return [
            _api_doc_to_hazard_type(d)
            for d in docs
            if any(
                rd.get("resource_type_id") == resource_type_id
                for rd in (d.get("resource_defaults") or [])
            )
        ]


def _to_int_id(id_str: str) -> Optional[int]:
    try:
        return int(id_str) if id_str else None
    except (ValueError, TypeError):
        return None


def _api_doc_to_hazard_type(doc: dict[str, Any]) -> HazardType:
    int_id = _to_int_id(str(doc.get("hazard_type_id") or doc.get("id") or ""))
    return HazardType(
        id=int_id,
        name=doc.get("name", ""),
        display_name=doc.get("display_name", ""),
        category=doc.get("category", "Other"),
        source=doc.get("source", "AHJ Custom"),
        owner_agency=doc.get("owner_agency", ""),
        description=doc.get("description", ""),
        default_risk_level=doc.get("default_risk_level", "Unknown"),
        default_likelihood=doc.get("default_likelihood", "Unknown"),
        default_severity=doc.get("default_severity", "Unknown"),
        default_control_measure=doc.get("default_control_measure", ""),
        default_ppe=doc.get("default_ppe", ""),
        default_safety_message=doc.get("default_safety_message", ""),
        is_active=bool(doc.get("is_active", True)),
        notes=doc.get("notes", ""),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        created_by=doc.get("created_by", ""),
        updated_by=doc.get("updated_by", ""),
        aliases=list(doc.get("aliases") or []),
        mitigations=[
            HazardMitigation(
                hazard_type_id=int_id or 0,
                mitigation_text=m.get("mitigation_text", ""),
                mitigation_category=m.get("mitigation_category", ""),
                is_default=bool(m.get("is_default", False)),
                sort_order=int(m.get("sort_order") or 0),
            )
            for m in (doc.get("mitigations") or [])
        ],
        ppe_items=[
            HazardPpeItem(
                hazard_type_id=int_id or 0,
                ppe_text=p.get("ppe_text", ""),
                is_default=bool(p.get("is_default", False)),
                sort_order=int(p.get("sort_order") or 0),
            )
            for p in (doc.get("ppe_items") or [])
        ],
        references=[
            HazardReference(
                hazard_type_id=int_id or 0,
                title=r.get("title", ""),
                url_or_path=r.get("url_or_path", ""),
                notes=r.get("notes", ""),
            )
            for r in (doc.get("references") or [])
        ],
        resource_defaults=[
            HazardTypeResourceDefault(
                hazard_type_id=int_id or 0,
                resource_type_id=int(rd.get("resource_type_id") or 0),
                notes=rd.get("notes", ""),
            )
            for rd in (doc.get("resource_defaults") or [])
        ],
    )


class ApiSafetyTemplateRepository:
    """CRUD repository for Safety Analysis Templates via the FastAPI server."""

    def list_templates(
        self,
        search_text: str = "",
        scenario_type: str = "All",
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        from utils.api_client import api_client
        params: dict[str, Any] = {"include_inactive": include_inactive}
        if search_text:
            params["search_text"] = search_text
        if scenario_type and scenario_type != "All":
            params["scenario_type"] = scenario_type
        return api_client.get("/api/master/safety-templates", params=params) or []

    def get_template(self, template_id: int) -> Optional[SafetyAnalysisTemplate]:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/master/safety-templates/{template_id}")
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
        return int(result["template_id"])

    def update_template(self, template_id: int, data: dict[str, Any]) -> int:
        from utils.api_client import api_client
        result = api_client.put(f"/api/master/safety-templates/{template_id}", json=data)
        return int(result["template_id"])

    def delete_template(self, template_id: int) -> None:
        from utils.api_client import api_client
        api_client.delete(f"/api/master/safety-templates/{template_id}")

    def clone_template(self, template_id: int) -> int:
        from utils.api_client import api_client
        result = api_client.post(f"/api/master/safety-templates/{template_id}/clone")
        return int(result["template_id"])

    def set_active(self, template_id: int, active: bool) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/master/safety-templates/{template_id}/active",
            json={"active": active},
        )


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
                default_risk_level=e.get("default_risk_level", ""),
            )
            for e in (doc.get("hazard_entries") or [])
        ],
    )


def _hazard_type_to_api_doc(ht: HazardType | dict[str, Any]) -> dict[str, Any]:
    if isinstance(ht, dict):
        return ht
    return {
        "name": ht.name,
        "display_name": ht.display_name,
        "category": ht.category,
        "source": ht.source,
        "owner_agency": ht.owner_agency,
        "description": ht.description,
        "default_risk_level": ht.default_risk_level,
        "default_likelihood": ht.default_likelihood,
        "default_severity": ht.default_severity,
        "default_control_measure": ht.default_control_measure,
        "default_ppe": ht.default_ppe,
        "default_safety_message": ht.default_safety_message,
        "is_active": ht.is_active,
        "notes": ht.notes,
        "created_by": ht.created_by,
        "updated_by": ht.updated_by,
        "aliases": list(ht.aliases),
        "mitigations": [
            {
                "mitigation_text": m.mitigation_text,
                "mitigation_category": m.mitigation_category,
                "is_default": m.is_default,
                "sort_order": m.sort_order,
            }
            for m in ht.mitigations
        ],
        "ppe_items": [
            {
                "ppe_text": p.ppe_text,
                "is_default": p.is_default,
                "sort_order": p.sort_order,
            }
            for p in ht.ppe_items
        ],
        "references": [
            {
                "title": r.title,
                "url_or_path": r.url_or_path,
                "notes": r.notes,
            }
            for r in ht.references
        ],
        "resource_defaults": [
            {
                "resource_type_id": rd.resource_type_id,
                "notes": rd.notes,
            }
            for rd in ht.resource_defaults
        ],
    }
