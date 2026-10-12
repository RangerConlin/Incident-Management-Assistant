from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict, Any

from pypdf import PdfReader, PdfWriter


def fill_pdf(template_path: Path, field_values: Dict[str, Any], flatten: bool = True) -> bytes:
    """Fill ``field_values`` into ``template_path`` and return PDF bytes."""
    reader = PdfReader(str(template_path))
    writer = PdfWriter()
    writer.clone_reader_document_root(reader)
    writer.update_page_form_field_values(writer.pages[0], field_values)
    if flatten:
        writer.remove_annotations(None)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
