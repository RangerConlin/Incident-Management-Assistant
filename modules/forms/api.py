from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from .form_registry import FormRegistry
from .session import FormSession
from .export import export_form
from .templating import resolve_template as legacy_resolve
from .render import render_form as legacy_render
from utils.profile_manager import profile_manager


@dataclass
class ExportResult:
    path: Path
    engine: str  # "v2" or "legacy"
    template_uid: Optional[str]


def export_form_unified(
    form_or_uid: str,
    out_path: Path,
    *,
    values: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    profile_id: Optional[str] = None,
    version: Optional[str] = None,
) -> ExportResult:
    """Single high-level method to export a form.

    - If ``form_or_uid`` looks like a template UID ("<profile>:<form>@<version>"),
      it uses the deterministic v2 pipeline.
    - Otherwise it tries to resolve a v2 template for the active profile and the
      provided form id (optionally with a ``version`` hint).
    - If no v2 template is available, falls back to the legacy registry+mapping
      based renderer (for forms present in data/templates/registry.json),
      ignoring ``values`` (legacy path takes full JSON via mapping).
    """

    ctx = dict(context or {})
    if str(form_or_uid).isdigit() and ctx.get("incident_id"):
        rendered = RendererService().export_instance(str(ctx["incident_id"]), int(form_or_uid), "pdf", out_path)
        return ExportResult(path=Path(rendered["path"]), engine="unified", template_uid=None)

    pid = profile_id or (profile_manager.get_active_profile_id() or "")

    def _is_uid(s: str) -> bool:
        return ":" in s and "@" in s

    # ---------- Try deterministic v2 path ----------
    try:
        reg = FormRegistry("profiles", pid)
        reg.load()

        if _is_uid(form_or_uid):
            tpl_uid = form_or_uid
        else:
            # Pick a template by form_id, optionally filtered by version
            candidates = [m for m in reg.list() if m.form_id.lower() == form_or_uid.lower()]
            # Prefer profile-configured active version
            if not version:
                act = profile_manager.get_active_template_version(pid, form_or_uid.upper())
                if act:
                    version = act
            if version:
                candidates = [m for m in candidates if str(m.form_version) == str(version)] or candidates
            # naive pick: first candidate
            tpl_uid = candidates[0].template_uid if candidates else None

        if tpl_uid:
            sess = FormSession(instance_id=str(uuid.uuid4()), template_uid=tpl_uid, values=dict(values or {}))
            out = Path(out_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            export_form(sess, dict(context or {}), reg, out)
            return ExportResult(path=out, engine="v2", template_uid=tpl_uid)
    except Exception:
        # Swallow and fall back to legacy
        pass

    # ---------- Legacy fallback (registry + YAML mapping) ----------
    # ``legacy_render`` expects the entire form JSON (values), a form_id and a version.
    # Use provided ``version`` or "latest" alias.
    if not version:
        version = "latest"
    try:
        # Resolve and render using the minimal legacy helpers
        # Note: legacy_resolve raises if form/version not in registry
        legacy_id = form_or_uid.lower()
        _ = legacy_resolve(legacy_id, version)  # presence check
        pdf_bytes = legacy_render(legacy_id, version, dict(values or {}), options={"flatten": True})
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(pdf_bytes)
        return ExportResult(path=out, engine="legacy", template_uid=None)
    except Exception as e:
        raise RuntimeError(
            f"Failed to export form '{form_or_uid}'. Tried v2 (profile={pid}) then legacy. Last error: {e}"
        )


__all__ = ["export_form_unified", "ExportResult"]

from fastapi import APIRouter, HTTPException, Query

from .schemas.api_models import (
    ExportRequest, FamilyCreate, InstanceAction, InstanceCreate, RefreshRequest, TemplateCreate,
    TemplateVersionCreate, UploadRequest, ValidateRequest, ValuesPatch,
)
from .services import BindingService, InstanceService, RendererService, TemplateService, UploadService, ValidationService

router = APIRouter(prefix="/api/forms", tags=["forms"])


def _template_service() -> TemplateService:
    return TemplateService()


def _instance_service() -> InstanceService:
    return InstanceService()


@router.get("/families")
def list_families(code: str | None = None, category: str | None = None, active: bool | None = None) -> list[dict[str, Any]]:
    return _template_service().list_families(code=code, category=category, active=active)


@router.post("/families")
def create_family(payload: FamilyCreate) -> dict[str, Any]:
    family = _template_service().create_family(**payload.model_dump())
    return asdict(family)


@router.get("/templates")
def list_templates(family_code: str | None = None, agency: str | None = None, system: str | None = None, status: str | None = None, active_only: bool = False) -> list[dict[str, Any]]:
    return _template_service().list_templates(family_code=family_code, agency=agency, system=system, status=status, active_only=active_only)


@router.post("/templates")
def create_template(payload: TemplateCreate) -> dict[str, Any]:
    return _template_service().create_template(**payload.model_dump())


@router.get("/templates/{template_id}")
def get_template(template_id: int) -> dict[str, Any]:
    template = _template_service().get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="template not found")
    return template


@router.get("/templates/{template_id}/versions")
def list_versions(template_id: int) -> list[dict[str, Any]]:
    return _template_service().list_versions(template_id)


@router.get("/templates/{template_id}/versions/{version_id}")
def get_version(template_id: int, version_id: int) -> dict[str, Any]:
    version = _template_service().get_version(template_id, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="template version not found")
    return version


@router.post("/templates/{template_id}/versions")
def create_version(template_id: int, payload: TemplateVersionCreate) -> dict[str, Any]:
    return _template_service().create_version(template_id, **payload.model_dump())


@router.post("/templates/{template_id}/retire")
def retire_template(template_id: int, user_id: str | None = None) -> dict[str, bool]:
    _template_service().retire_template(template_id, user_id)
    return {"ok": True}


@router.get("/instances")
def list_instances(
    incident_id: str = Query(...), family_code: str | None = None, agency: str | None = None, status: str | None = None,
    operational_period_id: str | None = None, linked_module: str | None = None, linked_record_id: str | None = None,
) -> list[dict[str, Any]]:
    return _instance_service().list_instances(incident_id, family_code=family_code, agency=agency, status=status, operational_period_id=operational_period_id, linked_module=linked_module, linked_record_id=linked_record_id)


@router.post("/instances")
def create_instance(payload: InstanceCreate) -> dict[str, Any]:
    return _instance_service().create_instance(**payload.model_dump())


@router.get("/instances/{instance_id}")
def get_instance(instance_id: int, incident_id: str = Query(...)) -> dict[str, Any]:
    instance = _instance_service().get_instance(incident_id, instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="instance not found")
    return instance


@router.patch("/instances/{instance_id}/values")
def update_values(instance_id: int, payload: ValuesPatch) -> dict[str, Any]:
    return _instance_service().update_values(payload.incident_id, instance_id, payload.values, payload.user_id)


@router.post("/instances/{instance_id}/refresh")
def refresh_instance(instance_id: int, payload: RefreshRequest) -> dict[str, Any]:
    return _instance_service().refresh(payload.incident_id, instance_id, payload.context, payload.user_id)


@router.post("/instances/{instance_id}/finalize")
def finalize_instance(instance_id: int, payload: InstanceAction) -> dict[str, Any]:
    return _instance_service().finalize(payload.incident_id, instance_id, payload.user_id)


@router.post("/instances/{instance_id}/reopen")
def reopen_instance(instance_id: int, payload: InstanceAction) -> dict[str, Any]:
    return _instance_service().reopen(payload.incident_id, instance_id, payload.user_id, payload.reason)


@router.get("/instances/{instance_id}/revisions")
def list_instance_revisions(instance_id: int, incident_id: str = Query(...)) -> list[dict[str, Any]]:
    return _instance_service().list_revisions(incident_id, instance_id)


@router.get("/instances/{instance_id}/audit")
def list_instance_audit(instance_id: int, incident_id: str = Query(...)) -> list[dict[str, Any]]:
    return _instance_service().list_audit(incident_id, instance_id)


@router.post("/instances/{instance_id}/export")
def export_instance(instance_id: int, payload: ExportRequest) -> dict[str, Any]:
    return RendererService().export_instance(payload.incident_id, instance_id, payload.export_type, payload.output_path, payload.user_id)


@router.post("/upload")
def upload_form(payload: UploadRequest) -> dict[str, Any]:
    return UploadService().register_source_asset(**payload.model_dump())


@router.get("/bindings")
def list_bindings() -> list[dict[str, Any]]:
    return BindingService().describe_available_bindings()


@router.post("/validate")
def validate(payload: ValidateRequest) -> list[dict[str, Any]]:
    return [r.__dict__ for r in ValidationService().validate_fields(payload.fields, payload.values, status=payload.status)]
