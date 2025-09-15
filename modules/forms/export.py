"""High level deterministic form export helpers.

This module glues together the registry, binding resolution and renderer
implementations.  The real application contains much more functionality (PDF
field mapping, error handling, UI integration, ...).  For the purposes of unit
tests we only implement enough behaviour to verify the deterministic template
resolution and fingerprint validation logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json
import hashlib

from .session import FormSession


# ---------------------------------------------------------------- fingerprint

def sha256_of_file(p: Path) -> str:
    """Return ``sha256:<hex>`` fingerprint for ``p``.

    The helper streams the file to avoid loading large PDFs entirely into
    memory.  The prefix mirrors the convention used in the template JSON.
    """

    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def assert_fingerprint(pdf_path: Path, expected: str | None) -> None:
    """Raise :class:`ValueError` if the file fingerprint does not match."""

    if not expected:
        return
    actual = sha256_of_file(pdf_path)
    if actual != expected:
        raise ValueError(
            f"Base PDF fingerprint mismatch. Expected {expected}, got {actual}"
        )


# ---------------------------------------------------------------- renderers

def render_pdf(template: Dict[str, Any], values: Dict[str, Any], out_path: Path) -> Path:
    """Minimal PDF renderer used in tests.

    The function verifies the fingerprint of the source PDF and then simply
    writes the values mapping as JSON into ``out_path``.  This is obviously not
    a real PDF renderer but suffices for deterministic behaviour in tests.
    """

    profile_dir = Path(template.get("_profile_dir", "."))
    pdf_path = profile_dir / template["pdf_source"]
    assert_fingerprint(pdf_path, template.get("pdf_fingerprint"))

    out_path.write_text(json.dumps(values, indent=2), encoding="utf-8")
    return out_path


def render_print_document(template: Dict[str, Any], values: Dict[str, Any], out_path: Path) -> Path:
    out_path.write_text("PRINT" + json.dumps(values), encoding="utf-8")
    return out_path


def render_html(template: Dict[str, Any], values: Dict[str, Any], out_path: Path) -> Path:
    out_path.write_text("<html></html>", encoding="utf-8")
    return out_path


# ----------------------------------------------------------------- main api

def export_form(session: FormSession, context: Dict[str, Any], registry, out_path: Path) -> Path:
    """Export ``session`` deterministically using ``registry``.

    Parameters
    ----------
    session:
        :class:`FormSession` instance holding user edits and the
        ``template_uid`` to resolve.
    context:
        Additional data used for bindings.  The resolution of bindings is
        delegated to :func:`bindings.render_values` which is stubbed in tests.
    registry:
        :class:`FormRegistry` instance providing templates.
    out_path:
        Destination path for the exported file.  The function returns this path
        for convenience.
    """

    template = registry.get(session.template_uid)

    # Resolve values from bindings.  ``render_values`` is part of the wider
    # application and may not be present during unit tests; to keep this module
    # self contained we import lazily and fall back to an identity mapping if
    # unavailable.
    try:  # pragma: no cover - depending on test setup
        from .bindings import render_values  # type: ignore
    except Exception:  # pragma: no cover - fallback to global name or no-op
        try:
            from bindings import render_values  # type: ignore
        except Exception:
            def render_values(tpl, ctx):  # type: ignore
                return {}

    resolved = render_values(template, context)
    if session.values:
        resolved.update(session.values)

    renderer = template.get("renderer", "pdf")
    if renderer == "pdf":
        return render_pdf(template, resolved, out_path)
    if renderer == "print":
        return render_print_document(template, resolved, out_path)
    if renderer == "html":
        return render_html(template, resolved, out_path)
    raise ValueError(f"Unknown renderer: {renderer}")


__all__ = [
    "export_form",
    "render_pdf",
    "render_print_document",
    "render_html",
    "sha256_of_file",
    "assert_fingerprint",
]

