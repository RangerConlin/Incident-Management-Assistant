"""Tests for the placeholder PDF exporter."""

from __future__ import annotations

from datetime import datetime

from app.modules.planning.iap.models.exporter import IAPPacketExporter
from app.modules.planning.iap.models.iap_models import FormInstance, IAPPackage


def _build_package() -> IAPPackage:
    package = IAPPackage(
        incident_id="demo-incident",
        op_number=2,
        op_start=datetime(2025, 9, 23, 7, 0, 0),
        op_end=datetime(2025, 9, 23, 19, 0, 0),
    )
    package.forms.append(FormInstance(form_id="ICS-202", title="Incident Objectives", op_number=2))
    package.forms.append(FormInstance(form_id="ICS-205", title="Communications Plan", op_number=2))
    return package


def test_exporter_creates_placeholder_pdf(tmp_path) -> None:
    package = _build_package()
    exporter = IAPPacketExporter(tmp_path)

    pdf_path = exporter.export_packet(package, draft=True)

    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF-PLACEHOLDER")


def test_table_of_contents_reflects_form_order() -> None:
    package = _build_package()
    exporter = IAPPacketExporter("/tmp")

    toc = exporter.build_table_of_contents(package)
    members = list(exporter.iter_packet_members(package))

    assert toc == ["Incident Objectives", "Communications Plan"]
    assert members == toc
