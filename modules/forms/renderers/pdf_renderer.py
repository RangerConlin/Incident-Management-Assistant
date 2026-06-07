from __future__ import annotations

from pathlib import Path
from typing import Any

from .summary_renderer import SummaryRenderer


class PdfRenderer:
    def render(self, instance: dict[str, Any], template_version: dict[str, Any], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        text = SummaryRenderer().render(instance, template_version)
        # Minimal stable printable output; a richer PDF overlay can replace this writer.
        content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n4 0 obj<</Length 0>>stream\nendstream\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
        output_path.write_bytes(content + ("\n" + text).encode("utf-8"))
        return output_path
