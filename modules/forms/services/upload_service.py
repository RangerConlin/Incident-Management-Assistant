from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .template_service import TemplateService


class UploadService:
    def __init__(self, template_service: TemplateService | None = None) -> None:
        self.template_service = template_service or TemplateService()

    def register_source_asset(self, *, source_path: str | Path, family_id: int | None = None, family_code: str | None = None, agency: str, code: str, title: str, system: str | None = None, category: str | None = None, created_by: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        path = Path(source_path)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        return self.template_service.create_template(
            family_id=family_id, family_code=family_code, agency=agency, system=system, code=code, title=title,
            description=(metadata or {}).get("description"), fields=[], layout={"asset_path": str(path), "category": category},
            source_asset_path=str(path), checksum=checksum, created_by=created_by, status="draft",
        )
