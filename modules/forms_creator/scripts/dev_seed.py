"""Seed the databases with a minimal demo template and instance."""

from __future__ import annotations

import struct
import sys
import uuid
import zlib
from pathlib import Path

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from modules.forms_creator.services.templates import FormService  # type: ignore  # noqa: E402
else:
    from ..services.templates import FormService


def main() -> None:
    try:
        service = FormService()
    except RuntimeError as exc:
        print(f"Unable to initialise form service: {exc}")
        return

    template_uuid = uuid.uuid4().hex
    template_dir = service.templates_dir / template_uuid
    template_dir.mkdir(parents=True, exist_ok=True)

    background = template_dir / "background_page_001.png"
    _write_blank_png(background, 800, 600)

    field = {
        "id": 1,
        "page": 1,
        "name": "incident_commander",
        "type": "text",
        "x": 120,
        "y": 140,
        "width": 260,
        "height": 28,
        "font_family": "",
        "font_size": 12,
        "align": "left",
        "required": True,
        "placeholder": "",
        "mask": "",
        "default_value": "",
        "config": {
            "bindings": [
                {"source_type": "system", "source_ref": "incident.ic_name"},
            ],
            "validations": [
                {"rule_type": "required", "rule_config": {}, "error_message": "Provide a name"}
            ],
            "dropdown": None,
            "table": None,
        },
    }

    background_rel = Path("forms") / "templates" / template_uuid
    template_id = service.save_template(
        name="ICS 201 Demo",
        category="ICS",
        subcategory="Cover",
        background_path=str(background_rel),
        page_count=1,
        fields=[field],
    )

    context = {"incident": {"ic_name": "Chief Ranger"}}
    incident_id = "INC-DEMO"
    instance_id = service.create_instance(incident_id, template_id, context)
    service.save_instance_value(instance_id, field["id"], "Chief Ranger", incident_id=incident_id)

    output_pdf = template_dir / "demo_instance.pdf"
    try:
        service.export_instance_pdf(incident_id, instance_id, output_pdf)
        print(f"Seeded template {template_id} with instance {instance_id} → {output_pdf}")
    except RuntimeError as exc:
        print(f"Seeded template {template_id} with instance {instance_id} (PDF export skipped: {exc})")


def _write_blank_png(path: Path, width: int, height: int, color: tuple[int, int, int] = (255, 255, 255)) -> None:
    """Write a simple opaque PNG without relying on GUI libraries."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = bytearray()
    row = bytes(color) * width
    for _ in range(height):
        raw.append(0)
        raw.extend(row)
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    png.extend(chunk(b"IDAT", zlib.compress(bytes(raw))))
    png.extend(chunk(b"IEND", b""))
    path.write_bytes(bytes(png))


if __name__ == "__main__":  # pragma: no cover - helper script
    main()
