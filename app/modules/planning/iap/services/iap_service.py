"""High level orchestration for the IAP Builder module."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from typing import Dict, Iterable, List, Optional, Sequence

from ..models.autofill import AutofillEngine
from ..models.exporter import IAPPacketExporter
from ..models.iap_models import FormInstance, IAPPackage
from ..models.repository import IAPRepository
from utils import incident_context

DEFAULT_FORMS: Dict[str, str] = {
    "COVER": "Cover & Table of Contents",
    "ICS-202": "Incident Objectives",
    "ICS-203": "Organization Assignment List",
    "ICS-204": "Assignment List",
    "ICS-205": "Communications Plan",
    "ICS-206": "Medical Plan",
    "ICS-207": "Organizational Chart",
    "ICS-208": "Safety Message/Plan",
    "ICS-215": "Operational Planning Worksheet",
    "ICS-215A": "Incident Action Safety Analysis",
    "ICS-220": "Air Operations Summary",
    "DIST": "Distribution List",
}


_LOGGER = logging.getLogger(__name__)


class IAPService:
    """Facade for the IAP Builder business logic.
    """

    def __init__(
        self,
        repository: Optional[IAPRepository] = None,
        exporter: Optional[IAPPacketExporter] = None,
        autofill_engine: Optional[AutofillEngine] = None,
        base_output_dir: Optional[Path] = None,
        incident_id: Optional[str] = None,
    ):
        data_root = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))
        output_dir = base_output_dir or (data_root / "incidents")
        self.exporter = exporter or IAPPacketExporter(output_dir)
        self.autofill_engine = autofill_engine or AutofillEngine()
        self.incident_id = incident_id
        if repository is None:
            repository = self._build_repository(incident_id, data_root)
        self.repository = repository

    # ------------------------------------------------------------------ public API
    def create_package(
        self,
        incident_id: str,
        op_number: int,
        op_start: datetime,
        op_end: datetime,
        forms: Iterable[str],
    ) -> IAPPackage:
        """Create a new :class:`IAPPackage` populated with blank forms."""

        repository = self._require_repository()
        package = IAPPackage(
            incident_id=incident_id,
            op_number=op_number,
            op_start=op_start,
            op_end=op_end,
        )
        for display_order, form_id in enumerate(forms):
            title = DEFAULT_FORMS.get(form_id, form_id)
            package.forms.append(
                FormInstance(
                    form_id=form_id,
                    title=title,
                    op_number=op_number,
                    display_order=display_order,
                )
            )
        repository.save_package(package)
        repository.save_forms(package, package.forms)
        return repository.get_package(incident_id, op_number)

    def list_packages(self, incident_id: str) -> List[IAPPackage]:
        """List packages for ``incident_id`` ordered by operational period."""

        repository = self._require_repository()
        return repository.list_packages(incident_id)

    def get_package(self, incident_id: str, op_number: int) -> IAPPackage:
        """Return a package for ``incident_id`` and ``op_number``."""

        repository = self._require_repository()
        return repository.get_package(incident_id, op_number)

    def save_form(self, package: IAPPackage, form: FormInstance) -> None:
        """Persist ``form`` within ``package``."""

        form.mark_updated()
        package.add_form(form)
        repository = self._require_repository()
        repository.save_form(package, form)
        self.refresh_package(package)

    def add_form(self, package: IAPPackage, form_id: str, title: Optional[str] = None) -> FormInstance:
        """Add a new form to ``package`` and persist it."""

        if package.get_form(form_id):
            raise ValueError(f"Form {form_id} already exists in package")
        repository = self._require_repository()
        display_order = max((form.display_order for form in package.forms), default=-1) + 1
        form = FormInstance(
            form_id=form_id,
            title=title or DEFAULT_FORMS.get(form_id, form_id),
            op_number=package.op_number,
            display_order=display_order,
        )
        repository.save_form(package, form)
        self.refresh_package(package)
        refreshed = package.get_form(form_id)
        if refreshed is None:  # pragma: no cover - defensive
            raise RuntimeError(f"Unable to load form {form_id} after insertion")
        return refreshed

    def remove_form(self, package: IAPPackage, form_id: str) -> None:
        """Remove ``form_id`` from ``package`` and persist the change."""

        if not package.get_form(form_id):
            return
        repository = self._require_repository()
        repository.delete_form(package, form_id)
        package.remove_form(form_id)
        repository.update_form_order(package, [form.form_id for form in package.forms])
        self.refresh_package(package)

    def reorder_forms(self, package: IAPPackage, order: Sequence[str]) -> None:
        """Persist ``order`` for ``package`` and update local state."""

        repository = self._require_repository()
        repository.update_form_order(package, list(order))
        self.refresh_package(package)

    def duplicate_package(
        self,
        package: IAPPackage,
        new_op_number: int,
        op_start: Optional[datetime] = None,
        op_end: Optional[datetime] = None,
    ) -> IAPPackage:
        """Create a duplicate of ``package`` with ``new_op_number``."""

        repository = self._require_repository()
        start = op_start or package.op_start
        end = op_end or package.op_end
        duplicate = IAPPackage(
            incident_id=package.incident_id,
            op_number=new_op_number,
            op_start=start,
            op_end=end,
            notes=package.notes,
        )
        forms: List[FormInstance] = []
        for form in package.forms:
            clone = FormInstance(
                form_id=form.form_id,
                title=form.title,
                op_number=new_op_number,
                revision=0,
                fields=deepcopy(form.fields),
                attachments=list(form.attachments),
                status="draft",
                display_order=form.display_order,
            )
            forms.append(clone)
        duplicate.forms = sorted(forms, key=lambda item: item.display_order)
        repository.save_package(duplicate)
        repository.save_forms(duplicate, duplicate.forms)
        return repository.get_package(duplicate.incident_id, new_op_number)

    def validate_package(self, package: IAPPackage) -> Dict[str, List[str]]:
        """Return validation errors keyed by form ID.

        Validation is intentionally empty for now; the behaviour will be fleshed
        out during a later milestone when the form templates and rules are wired
        in.  Returning an empty dict keeps the calling code straightforward.
        """

        return {}

    def publish(self, package: IAPPackage) -> str:
        """Mark ``package`` as published and export the immutable PDF."""

        package.status = "published"
        package.version_tag = package.version_tag or f"OP{package.op_number}-FINAL-v1"
        repository = self._require_repository()
        repository.save_package(package)
        output_path = self.exporter.export_packet(package, draft=False)
        package.published_pdf_path = str(output_path)
        repository.save_package(package)
        return package.published_pdf_path

    def export_pdf(self, package: IAPPackage, draft: bool = False) -> str:
        """Export ``package`` to a placeholder PDF path."""

        output_path = self.exporter.export_packet(package, draft=draft)
        return str(output_path)

    def describe_autofill(self, form: FormInstance) -> List[str]:
        """Return human readable descriptions of autofill mappings for ``form``."""

        return self.autofill_engine.describe_rules(form.form_id)

    def incident_display_name(self, incident_id: str) -> str:
        """Return a friendly name for ``incident_id`` if available."""

        if self.repository:
            name = self.repository.incident_name(incident_id)
            if name:
                return name
        return incident_id

    # ------------------------------------------------------------------ internals
    def _build_repository(self, incident_id: Optional[str], data_root: Path) -> Optional[IAPRepository]:
        incident_path: Optional[Path]
        if incident_id:
            incident_path = data_root / "incidents" / f"{incident_id}.db"
        else:
            try:
                incident_path = incident_context.get_active_incident_db_path()
            except RuntimeError:
                _LOGGER.warning("IAP repository unavailable – no active incident selected.")
                return None
        master_path = data_root / "master.db"
        repository = IAPRepository(incident_path, master_path)
        repository.initialize()
        return repository

    def _require_repository(self) -> IAPRepository:
        if not self.repository:
            raise RuntimeError("IAP repository is not configured; select an incident first.")
        return self.repository

    def refresh_package(self, package: IAPPackage) -> IAPPackage:
        """Reload ``package`` from the repository, updating the instance in place."""

        repository = self._require_repository()
        latest = repository.get_package(package.incident_id, package.op_number)
        package.op_start = latest.op_start
        package.op_end = latest.op_end
        package.created_at = latest.created_at
        package.status = latest.status
        package.notes = latest.notes
        package.version_tag = latest.version_tag
        package.published_pdf_path = latest.published_pdf_path
        package.forms = latest.forms
        return package
