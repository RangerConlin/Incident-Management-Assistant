from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from modules.forms.renderers import HtmlRenderer, PdfRenderer, SummaryRenderer
from modules.forms.repositories.incident_forms_repository import ApiIncidentFormsRepository
from modules.forms.repositories.master_forms_repository import ApiMasterFormsRepository


class RendererService:
    def __init__(self, master_repository=None, output_dir: Path | str = Path("data") / "forms" / "exports", incident_base_dir=None) -> None:
        self.master_repository = master_repository or ApiMasterFormsRepository()
        self.output_dir = Path(output_dir)
        self.incident_base_dir = incident_base_dir

    def _load(self, incident_id: str, instance_id: int) -> tuple[ApiIncidentFormsRepository, dict[str, Any], dict[str, Any]]:
        repo = ApiIncidentFormsRepository(incident_id)
        instance = repo.get_instance(instance_id)
        if not instance:
            raise ValueError("instance not found")
        version = self.master_repository.get_template_version(int(instance["template_id"]), int(instance["template_version_id"]))
        if not version:
            raise ValueError("template version not found")
        return repo, instance, version

    def render_pdf(self, incident_id: str, instance_id: int, output_path: Path | str | None = None, user_id: str | None = None) -> Path:
        repo, instance, version = self._load(incident_id, instance_id)
        path = Path(output_path) if output_path else self.output_dir / incident_id / f"form_{instance_id}_r{instance['revision_number']}.pdf"
        PdfRenderer().render(instance, version, path)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        repo.create_export_record({"instance_id": instance_id, "export_type": "pdf", "export_path": str(path), "template_version_id": instance["template_version_id"], "revision_number": instance["revision_number"], "created_by": user_id, "checksum": checksum})
        repo.set_exported_pdf(instance_id, str(path), user_id)
        return path

    def render_summary(self, incident_id: str, instance_id: int) -> str:
        _, instance, version = self._load(incident_id, instance_id)
        return SummaryRenderer().render(instance, version)

    def render_edit_model(self, incident_id: str, instance_id: int) -> dict[str, Any]:
        _, instance, version = self._load(incident_id, instance_id)
        return {"instance": instance, "template_version": version}

    def export_instance(self, incident_id: str, instance_id: int, export_type: str = "pdf", output_path: Path | str | None = None, user_id: str | None = None) -> dict[str, Any]:
        if export_type == "pdf":
            path = self.render_pdf(incident_id, instance_id, output_path, user_id)
            return {"export_type": "pdf", "path": str(path)}
        if export_type == "summary":
            text = self.render_summary(incident_id, instance_id)
            path = Path(output_path) if output_path else self.output_dir / incident_id / f"form_{instance_id}_summary.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return {"export_type": "summary", "path": str(path), "content": text}
        if export_type == "html":
            _, instance, version = self._load(incident_id, instance_id)
            return {"export_type": "html", "content": HtmlRenderer().render(instance, version)}
        raise ValueError(f"unsupported export type: {export_type}")
