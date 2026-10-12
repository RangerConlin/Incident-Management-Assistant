"""Persistence layer for the IAP Builder — API-backed implementation.

All reads and writes go through the API server
(``/api/incidents/{id}/iap/packages``), which stores data in MongoDB.
The SQLite incident.db is no longer accessed by this module.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable, List, Optional

from .iap_models import FormInstance, IAPPackage

__all__ = ["IAPRepository"]


def _parse_dt(value: str | None) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.utcnow()


def _serialize_dt(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _pkg_from_doc(doc: dict) -> IAPPackage:
    package = IAPPackage(
        incident_id=doc["incident_id"],
        op_number=int(doc["op_number"]),
        op_start=_parse_dt(doc.get("op_start")),
        op_end=_parse_dt(doc.get("op_end")),
        created_at=_parse_dt(doc.get("created_at")),
        status=doc.get("status", "draft"),
        notes=doc.get("notes") or "",
        version_tag=doc.get("version_tag"),
        published_pdf_path=doc.get("published_pdf_path"),
    )
    forms = []
    for i, fd in enumerate(doc.get("forms") or []):
        forms.append(FormInstance(
            form_id=fd["form_id"],
            title=fd.get("title", ""),
            op_number=int(fd.get("op_number", package.op_number)),
            revision=int(fd.get("revision", 0)),
            fields=fd.get("fields") or {},
            attachments=fd.get("attachments") or [],
            status=fd.get("status", "draft"),
            last_updated=_parse_dt(fd.get("last_updated")),
            display_order=int(fd.get("display_order", i)),
        ))
    package.forms = forms
    return package


class IAPRepository:
    """Reads and writes IAP data through the incident API."""

    def __init__(self, incident_id: str):
        self.incident_id = incident_id

    def initialize(self) -> None:
        """No-op — schema is managed by the API/MongoDB layer."""

    # -- package operations ---------------------------------------------------------

    def list_packages(self, incident_id: str) -> List[IAPPackage]:
        from utils.api_client import api_client
        docs = api_client.get(f"/api/incidents/{incident_id}/iap/packages") or []
        return [_pkg_from_doc(d) for d in docs]

    def get_package(self, incident_id: str, op_number: int) -> IAPPackage:
        from utils.api_client import api_client
        doc = api_client.get(f"/api/incidents/{incident_id}/iap/packages/{op_number}")
        if not doc:
            raise KeyError(f"No IAP package for incident {incident_id!r} OP {op_number}")
        return _pkg_from_doc(doc)

    def save_package(self, package: IAPPackage) -> IAPPackage:
        from utils.api_client import api_client
        payload = {
            "incident_id": package.incident_id,
            "op_start": _serialize_dt(package.op_start),
            "op_end": _serialize_dt(package.op_end),
            "created_at": _serialize_dt(package.created_at),
            "status": package.status,
            "notes": package.notes,
            "version_tag": package.version_tag,
            "published_pdf_path": package.published_pdf_path,
        }
        api_client.put(
            f"/api/incidents/{package.incident_id}/iap/packages/{package.op_number}",
            json=payload,
        )
        return package

    # -- form operations ------------------------------------------------------------

    def save_form(self, package: IAPPackage, form: FormInstance) -> FormInstance:
        from utils.api_client import api_client
        payload = {
            "form_id": form.form_id,
            "title": form.title,
            "op_number": package.op_number,
            "revision": form.revision,
            "status": form.status,
            "last_updated": _serialize_dt(form.last_updated),
            "fields": form.fields or {},
            "attachments": form.attachments or [],
            "display_order": form.display_order,
        }
        api_client.put(
            f"/api/incidents/{package.incident_id}/iap/packages/{package.op_number}/forms/{form.form_id}",
            json=payload,
        )
        return form

    def save_forms(self, package: IAPPackage, forms: Iterable[FormInstance]) -> None:
        for index, form in enumerate(forms):
            form.display_order = index
            self.save_form(package, form)

    def delete_form(self, package: IAPPackage, form_id: str) -> None:
        from utils.api_client import api_client
        api_client.delete(
            f"/api/incidents/{package.incident_id}/iap/packages/{package.op_number}/forms/{form_id}"
        )

    def update_form_order(self, package: IAPPackage, order: List[str]) -> None:
        from utils.api_client import api_client
        api_client.put(
            f"/api/incidents/{package.incident_id}/iap/packages/{package.op_number}/forms-order",
            json={"order": order},
        )

    def changelog_for_form(self, form_id: int) -> List[dict]:
        return []

    # -- metadata helpers -----------------------------------------------------------

    def incident_name(self, incident_id: str) -> Optional[str]:
        try:
            from utils.api_client import api_client
            doc = api_client.get(f"/api/incidents/{incident_id}/profile") or {}
            return doc.get("name") or None
        except Exception:
            return None
