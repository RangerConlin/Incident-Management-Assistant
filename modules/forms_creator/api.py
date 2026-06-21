from __future__ import annotations

from dataclasses import dataclass
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
            candidates = [m for m in reg.list() if m.form_id.lower() == form_or_uid.lower()]
            if not version:
                act = profile_manager.get_active_template_version(pid, form_or_uid.upper())
                if act:
                    version = act
            if version:
                candidates = [m for m in candidates if str(m.form_version) == str(version)] or candidates
            tpl_uid = candidates[0].template_uid if candidates else None

        if tpl_uid:
            sess = FormSession(instance_id=str(uuid.uuid4()), template_uid=tpl_uid, values=dict(values or {}))
            out = Path(out_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            export_form(sess, dict(context or {}), reg, out)
            return ExportResult(path=out, engine="v2", template_uid=tpl_uid)
    except Exception:
        pass

    # ---------- Legacy fallback (registry + YAML mapping) ----------
    if not version:
        version = "latest"
    try:
        legacy_id = form_or_uid.lower()
        _ = legacy_resolve(legacy_id, version)
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
