from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

# This module bridges the devtools panel to the application's forms renderer.
# Replace the stubbed import with the actual renderer once ready.

try:
    from forms_renderer import render_form  # expected public API
except Exception:  # pragma: no cover - stub for environments without renderer
    def render_form(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError(
            "forms_renderer.render_form not available yet. Wire your renderer here."
        )


@dataclass
class PreviewResult:
    pdf_bytes: bytes
    preview_png: bytes | None
    log: str


def render_preview(
    form_id: str, version: str, map_path: Path, sample_json_path: Path
) -> PreviewResult:
    data = json.loads(sample_json_path.read_text(encoding="utf-8"))
    options = {"flatten": True, "preview_png": True}
    pdf_bytes, preview_png, logs = None, None, ""
    out = render_form(form_id=form_id, form_version=version, data=data, options=options)

    if isinstance(out, tuple) and len(out) == 2:
        pdf_bytes, preview_png = out
    elif isinstance(out, (bytes, bytearray)):
        pdf_bytes = bytes(out)
        preview_png = None
    else:
        raise RuntimeError(
            "Unexpected render_form return type. Expected bytes or (pdf_bytes, preview_png_bytes)"
        )

    return PreviewResult(pdf_bytes=pdf_bytes, preview_png=preview_png, log=str(logs))

