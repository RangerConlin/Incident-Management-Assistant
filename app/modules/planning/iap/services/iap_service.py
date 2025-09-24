"""High level orchestration for the IAP Builder module."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ..models.autofill import AutofillEngine
from ..models.exporter import IAPPacketExporter
from ..models.iap_models import FormInstance, IAPPackage
from ..models.repository import IAPRepository

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


class IAPService:
    """Facade for the IAP Builder business logic.

    The class currently provides in-memory storage for packages so that the UI
    scaffolding has concrete data to interact with.  Once the repository layer
    is implemented these methods will delegate to :class:`IAPRepository` for
    persistence.
    """

    def __init__(
        self,
        repository: Optional[IAPRepository] = None,
        exporter: Optional[IAPPacketExporter] = None,
        autofill_engine: Optional[AutofillEngine] = None,
        base_output_dir: Optional[Path] = None,
    ):
        self.repository = repository
        output_dir = base_output_dir or Path("data/incidents")
        self.exporter = exporter or IAPPacketExporter(output_dir)
        self.autofill_engine = autofill_engine or AutofillEngine()
        self._packages: Dict[Tuple[str, int], IAPPackage] = {}

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

        package = IAPPackage(
            incident_id=incident_id,
            op_number=op_number,
            op_start=op_start,
            op_end=op_end,
        )
        for form_id in forms:
            title = DEFAULT_FORMS.get(form_id, form_id)
            package.forms.append(FormInstance(form_id=form_id, title=title, op_number=op_number))
        self._packages[(incident_id, op_number)] = package
        return package

    def list_packages(self, incident_id: str) -> List[IAPPackage]:
        """List packages for ``incident_id`` ordered by operational period."""

        packages = [pkg for (pkg_incident, _), pkg in self._packages.items() if pkg_incident == incident_id]
        return sorted(packages, key=lambda pkg: pkg.op_number)

    def get_package(self, incident_id: str, op_number: int) -> IAPPackage:
        """Return a package for ``incident_id`` and ``op_number``."""

        key = (incident_id, op_number)
        if key not in self._packages:
            raise KeyError(f"No package for incident {incident_id!r} OP {op_number}")
        return self._packages[key]

    def save_form(self, package: IAPPackage, form: FormInstance) -> None:
        """Persist ``form`` within ``package``."""

        form.mark_updated()
        package.add_form(form)
        self._packages[(package.incident_id, package.op_number)] = package

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
        output_path = self.exporter.export_packet(package, draft=False)
        package.published_pdf_path = str(output_path)
        self._packages[(package.incident_id, package.op_number)] = package
        return package.published_pdf_path

    def export_pdf(self, package: IAPPackage, draft: bool = False) -> str:
        """Export ``package`` to a placeholder PDF path."""

        output_path = self.exporter.export_packet(package, draft=draft)
        return str(output_path)

    # ---------------------------------------------------------------- convenience
    def ensure_demo_package(self, incident_id: str, op_number: int = 1) -> IAPPackage:
        """Return an existing package or create a simple demonstration package."""

        key = (incident_id, op_number)
        if key not in self._packages:
            op_start = datetime.utcnow().replace(hour=7, minute=0, second=0, microsecond=0)
            op_end = op_start + timedelta(hours=12)
            forms = [
                "COVER",
                "ICS-202",
                "ICS-203",
                "ICS-204",
                "ICS-205",
                "ICS-206",
                "DIST",
            ]
            package = self.create_package(incident_id, op_number, op_start, op_end, forms)
            # Seed a few field values so that the autofill preview shows content.
            objectives = package.get_form("ICS-202")
            if objectives:
                objectives.fields.update({
                    "incident_name": "Pine Ridge Wildfire",
                    "operational_period": f"OP {op_number}",
                    "objectives": [
                        "Ensure responder safety",
                        "Protect critical infrastructure",
                        "Contain fire perimeter to 5 miles",
                    ],
                })
            comms = package.get_form("ICS-205")
            if comms:
                comms.fields.update({
                    "nets": [
                        {"name": "TAC-1", "rx": "155.160", "tx": "155.160", "assignment": "Division A"},
                        {"name": "TAC-2", "rx": "155.190", "tx": "155.190", "assignment": "Division B"},
                    ]
                })
        return self._packages[key]

    def describe_autofill(self, form: FormInstance) -> List[str]:
        """Return human readable descriptions of autofill mappings for ``form``."""

        return self.autofill_engine.describe_rules(form.form_id)
