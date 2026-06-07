from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FormExportRecord:
    instance_id: int
    export_type: str
    export_path: str
    template_version_id: int
    revision_number: int
    id: int | None = None
    created_by: str | None = None
    created_at: str | None = None
    checksum: str | None = None
