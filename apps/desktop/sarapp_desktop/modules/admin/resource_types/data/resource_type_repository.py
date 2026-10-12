"""SQLite repository for Resource Type Library master data.

The UI intentionally calls this repository for all persistence so SQL stays in
one beginner-friendly place.  The repository creates and lightly migrates the
master database tables on startup; no demo rows are inserted.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional


from ..models.resource_type_models import (
    FemaNimsMapping,
    RESOURCE_CATEGORIES,
    RESOURCE_SOURCES,
    ResourceCapability,
    ResourceType,
    ResourceTypeComponent,
    ResourceTypeSearchResult,
)

ISO_TIMESTAMP = "%Y-%m-%dT%H:%M:%S"

_CATALOG_TYPES = "resource_types"
_CATALOG_CAPABILITIES = "resource_type_capabilities"


def _now() -> str:
    """Return the timestamp format used by existing repository modules."""

    return datetime.now().strftime(ISO_TIMESTAMP)


def _invalidate_resource_type_catalog() -> None:
    """Call after any write that changes resource type documents."""
    from utils.catalog_cache import catalog_cache
    catalog_cache.invalidate(_CATALOG_TYPES)


def _invalidate_capability_catalog() -> None:
    """Call after any write that changes capability documents."""
    from utils.catalog_cache import catalog_cache
    catalog_cache.invalidate(_CATALOG_CAPABILITIES)


class ApiResourceTypeRepository:
    """Drop-in replacement for ResourceTypeRepository that calls the FastAPI server."""

    def list_resource_types(
        self,
        search_text: str = "",
        include_inactive: bool = False,
        category: str = "All",
        source: str = "All",
        active_filter: str = "Active",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"active_filter": active_filter}
        if search_text:
            params["search_text"] = search_text
        if category and category != "All":
            params["category"] = category
        if source and source != "All":
            params["source"] = source
        if include_inactive:
            params["include_inactive"] = True

        if not search_text:
            # The library window's search box is live/debounced-as-you-type;
            # only memoize the no-search "default view" load, not every
            # keystroke's distinct query.
            from utils.catalog_cache import catalog_cache
            return catalog_cache.get(_CATALOG_TYPES, "/api/resource-types", params=params) or []

        from utils.api_client import api_client
        return api_client.get("/api/resource-types", params=params) or []

    def search_resource_types(self, text: str, limit: int = 20) -> list[ResourceTypeSearchResult]:
        from utils.api_client import api_client
        if not text.strip():
            return []
        data = api_client.get(
            "/api/resource-types/search",
            params={"q": text, "limit": limit},
        ) or []
        return [
            ResourceTypeSearchResult(
                resource_type_id=d.get("resource_type_id"),
                resource_type_text=d.get("resource_type_text", ""),
                category=d.get("category", ""),
                source=d.get("source", ""),
                owner_agency=d.get("owner_agency", ""),
                matched_on=d.get("matched_on", ""),
            )
            for d in data
        ]

    def get_resource_type(self, resource_type_id: int) -> Optional[ResourceType]:
        from utils.api_client import APIError
        from utils.catalog_cache import catalog_cache
        try:
            doc = catalog_cache.get(_CATALOG_TYPES, f"/api/resource-types/{resource_type_id}")
        except APIError as exc:
            if getattr(exc, "status_code", None) == 404:
                return None
            raise
        return _api_doc_to_resource_type(doc) if doc else None

    def get_resource_type_by_name(self, name: str) -> Optional[ResourceType]:
        from utils.api_client import api_client
        docs = api_client.get(
            "/api/resource-types",
            params={"search_text": name, "active_filter": "All"},
        ) or []
        for d in docs:
            if (d.get("name") or "").lower() == name.lower():
                return _api_doc_to_resource_type(d)
        return None

    def save_resource_type(self, resource_type: ResourceType) -> int:
        from utils.api_client import api_client
        payload = _resource_type_to_api_doc(resource_type)
        if resource_type.id is None:
            result = api_client.post("/api/resource-types", json=payload)
        else:
            result = api_client.put(f"/api/resource-types/{resource_type.id}", json=payload)
        _invalidate_resource_type_catalog()
        return int(result["resource_type_id"])

    def replace_components(
        self, resource_type_id: int, components: list[ResourceTypeComponent]
    ) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/{resource_type_id}/components",
            json={"components": [_component_to_dict(c) for c in components]},
        )
        _invalidate_resource_type_catalog()

    def clone_resource_type(self, resource_type_id: int) -> int:
        from utils.api_client import api_client
        result = api_client.post(f"/api/resource-types/{resource_type_id}/clone")
        _invalidate_resource_type_catalog()
        return int(result["resource_type_id"])

    def deactivate_resource_type(self, resource_type_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/{resource_type_id}/active",
            json={"active": False},
        )
        _invalidate_resource_type_catalog()

    def activate_resource_type(self, resource_type_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/{resource_type_id}/active",
            json={"active": True},
        )
        _invalidate_resource_type_catalog()

    # Alias for windows that call set_resource_type_active directly
    def set_resource_type_active(self, resource_type_id: int, active: bool) -> None:
        if active:
            self.activate_resource_type(resource_type_id)
        else:
            self.deactivate_resource_type(resource_type_id)

    # ------------------------------------------------------------------
    # Capabilities

    def list_capabilities(
        self,
        filters: Optional[dict[str, Any]] = None,
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        from utils.catalog_cache import catalog_cache
        params: dict[str, Any] = {}
        if include_inactive:
            params["include_inactive"] = True
        f = filters or {}
        if f.get("category") and f["category"] != "All":
            params["category"] = f["category"]
        return catalog_cache.get(_CATALOG_CAPABILITIES, "/api/resource-types/capabilities", params=params) or []

    def get_capability(self, capability_id: int) -> Optional[dict[str, Any]]:
        caps = self.list_capabilities(include_inactive=True)
        return next((c for c in caps if c.get("id") == capability_id), None)

    def get_capability_by_name(self, name: str) -> Optional[dict[str, Any]]:
        caps = self.list_capabilities(include_inactive=True)
        return next((c for c in caps if (c.get("name") or "").lower() == name.lower()), None)

    def save_capability(self, capability: ResourceCapability) -> int:
        from utils.api_client import api_client
        payload: dict[str, Any] = {
            "name": capability.name,
            "category": capability.category,
            "description": capability.description,
            "aliases": list(capability.aliases),
            "is_active": capability.is_active,
            "notes": capability.notes,
        }
        if capability.id is not None:
            payload["capability_id"] = str(capability.id)
        result = api_client.post("/api/resource-types/capabilities/save", json=payload)
        _invalidate_capability_catalog()
        return int(result["id"])

    def deactivate_capability(self, capability_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/capabilities/{capability_id}/active",
            json={"active": False},
        )
        _invalidate_capability_catalog()

    def activate_capability(self, capability_id: int) -> None:
        from utils.api_client import api_client
        api_client.patch(
            f"/api/resource-types/capabilities/{capability_id}/active",
            json={"active": True},
        )
        _invalidate_capability_catalog()

    def set_capability_active(self, capability_id: int, active: bool) -> None:
        if active:
            self.activate_capability(capability_id)
        else:
            self.deactivate_capability(capability_id)

    def set_resource_type_capabilities(
        self,
        resource_type_id: int,
        capability_ids: list[int],
        _conn: Any = None,
    ) -> None:
        """Update the capability list on a resource type by looking up names."""
        caps = self.list_capabilities(include_inactive=True)
        cap_map = {c["id"]: c.get("name", "") for c in caps if c.get("id") is not None}
        names = [cap_map[cid] for cid in capability_ids if cid in cap_map]
        from utils.api_client import api_client
        rt_doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        if rt_doc:
            rt = _api_doc_to_resource_type(rt_doc)
            rt.capability_ids = capability_ids
            rt.id = resource_type_id
            payload = _resource_type_to_api_doc(rt)
            payload["capability_names"] = names
            api_client.put(f"/api/resource-types/{resource_type_id}", json=payload)
            _invalidate_resource_type_catalog()

    # ------------------------------------------------------------------
    # Components (list / add / remove — used by component editor dialogs)

    def list_components(self, resource_type_id: int) -> list[dict[str, Any]]:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        except APIError:
            return []
        return list(doc.get("components") or []) if doc else []

    def add_component(self, component: ResourceTypeComponent) -> int:
        existing = self.list_components(component.parent_resource_type_id)
        existing.append(_component_to_dict(component))
        self.replace_components(component.parent_resource_type_id, [
            ResourceTypeComponent(
                parent_resource_type_id=component.parent_resource_type_id,
                component_resource_type_id=c.get("component_resource_type_id", 0),
                quantity=c.get("quantity", 1.0),
                unit=c.get("unit", "each"),
                notes=c.get("notes", ""),
                required=c.get("required", True),
            )
            for c in existing
        ])
        return len(existing)

    def remove_component(self, component_id: int) -> None:
        pass  # Components are replaced wholesale; individual remove not needed by UI

    def would_create_cycle(self, parent_id: int, child_id: int) -> bool:
        return False  # Cycle detection deferred to server-side validation

    def replace_aliases(
        self,
        resource_type_id: int,
        aliases: list[str],
        _conn: Any = None,
    ) -> None:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        except APIError:
            return
        if not doc:
            return
        rt = _api_doc_to_resource_type(doc)
        rt.aliases = aliases
        rt.id = resource_type_id
        api_client.put(f"/api/resource-types/{resource_type_id}", json=_resource_type_to_api_doc(rt))
        _invalidate_resource_type_catalog()

    def replace_fema_mappings(
        self,
        resource_type_id: int,
        mappings: list[FemaNimsMapping],
        _conn: Any = None,
    ) -> None:
        from utils.api_client import api_client
        from utils.api_client import APIError
        try:
            doc = api_client.get(f"/api/resource-types/{resource_type_id}")
        except APIError:
            return
        if not doc:
            return
        rt = _api_doc_to_resource_type(doc)
        rt.fema_mappings = mappings
        rt.id = resource_type_id
        api_client.put(f"/api/resource-types/{resource_type_id}", json=_resource_type_to_api_doc(rt))
        _invalidate_resource_type_catalog()


def _to_int_id(id_str: str) -> Optional[int]:
    try:
        return int(id_str) if id_str else None
    except (ValueError, TypeError):
        return None


def _api_doc_to_resource_type(doc: dict[str, Any]) -> ResourceType:
    rt_id = _to_int_id(str(doc.get("resource_type_id") or doc.get("id") or ""))
    return ResourceType(
        id=rt_id,
        name=doc.get("name", ""),
        resource_name=doc.get("resource_name") or doc.get("name", ""),
        category=doc.get("category", "Other"),
        source=doc.get("source", "AHJ Custom"),
        owner_agency=doc.get("owner_agency", ""),
        description=doc.get("description", ""),
        default_unit=doc.get("default_unit", "each"),
        typical_quantity=float(doc.get("typical_quantity") or 1.0),
        typical_team_size=doc.get("typical_team_size"),
        is_kit_cache=bool(doc.get("is_kit_cache", False)),
        is_consumable=bool(doc.get("is_consumable", False)),
        is_active=bool(doc.get("is_active", True)),
        notes=doc.get("notes", ""),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        created_by=doc.get("created_by", ""),
        updated_by=doc.get("updated_by", ""),
        aliases=list(doc.get("aliases") or []),
        capability_ids=list(doc.get("capability_ids") or []),
        components=[
            ResourceTypeComponent(
                parent_resource_type_id=rt_id or 0,
                component_resource_type_id=int(c.get("component_resource_type_id") or 0),
                quantity=float(c.get("quantity") or 1.0),
                unit=c.get("unit", "each"),
                notes=c.get("notes", ""),
                required=bool(c.get("required", True)),
            )
            for c in (doc.get("components") or [])
        ],
        fema_mappings=[
            FemaNimsMapping(
                resource_type_id=rt_id or 0,
                nims_name=m.get("nims_name", ""),
                discipline=m.get("discipline", ""),
                type_code=m.get("type_code", ""),
                kind=m.get("kind", ""),
                reference_url=m.get("reference_url", ""),
                notes=m.get("notes", ""),
                typed_level=m.get("typed_level", ""),
            )
            for m in (doc.get("fema_mappings") or [])
        ],
    )


def _resource_type_to_api_doc(rt: ResourceType) -> dict[str, Any]:
    return {
        "name": rt.name,
        "resource_name": rt.resource_name,
        "category": rt.category,
        "source": rt.source,
        "owner_agency": rt.owner_agency,
        "description": rt.description,
        "default_unit": rt.default_unit,
        "typical_quantity": float(rt.typical_quantity),
        "typical_team_size": rt.typical_team_size,
        "is_kit_cache": rt.is_kit_cache,
        "is_consumable": rt.is_consumable,
        "is_active": rt.is_active,
        "notes": rt.notes,
        "created_by": rt.created_by,
        "updated_by": rt.updated_by,
        "aliases": list(rt.aliases),
        "capability_ids": list(rt.capability_ids),
        "capability_names": [],  # resolved server-side via set_resource_type_capabilities
        "components": [_component_to_dict(c) for c in rt.components],
        "fema_mappings": [
            {
                "nims_name": m.nims_name,
                "discipline": m.discipline,
                "type_code": m.type_code,
                "kind": m.kind,
                "reference_url": m.reference_url,
                "notes": m.notes,
                "typed_level": m.typed_level,
            }
            for m in rt.fema_mappings
        ],
    }


def _component_to_dict(c: ResourceTypeComponent) -> dict[str, Any]:
    return {
        "component_resource_type_id": c.component_resource_type_id,
        "quantity": float(c.quantity),
        "unit": c.unit,
        "notes": c.notes,
        "required": c.required,
    }
