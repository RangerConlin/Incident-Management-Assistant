"""PDF export scaffolding for the IAP Builder."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from .iap_models import IAPPackage

__all__ = ["IAPPacketExporter"]


class IAPPacketExporter:
    """Placeholder exporter that produces stub PDF files.

    The scaffold focuses on generating deterministic filesystem paths and
    creating an empty file to represent the exported PDF.  The heavy lifting of
    rendering forms to PDF will be layered in during later milestones.
    """

    def __init__(self, base_output_dir: Path):
        self.base_output_dir = Path(base_output_dir)

    def packet_output_path(self, package: IAPPackage, draft: bool = False) -> Path:
        """Return the output path for ``package``.

        The directory structure mirrors the specification.  Draft exports keep a
        ``-DRAFT`` suffix so they can live alongside the final, published PDF.
        """

        op_dir = self.base_output_dir / package.incident_id / "iap" / f"op_{package.op_number}"
        status = "DRAFT" if draft else "FINAL"
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"IAP_OP{package.op_number}_{status}_{timestamp}.pdf"
        return op_dir / filename

    def export_packet(self, package: IAPPackage, draft: bool = False) -> Path:
        """Create a placeholder PDF on disk and return its path."""

        output_path = self.packet_output_path(package, draft=draft)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not output_path.exists():
            output_path.write_bytes(b"%PDF-PLACEHOLDER\n")
        return output_path

    def build_table_of_contents(self, package: IAPPackage) -> List[str]:
        """Return a list of strings describing the packet order."""

        return [form.title for form in package.forms]

    def iter_packet_members(self, package: IAPPackage) -> Iterable[str]:
        """Yield the titles of forms included in the packet order."""

        for form in package.forms:
            yield form.title
