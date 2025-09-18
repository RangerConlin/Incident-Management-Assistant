"""Seed the database with a demo template and incident instance."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from uuid import uuid4

from ..services import db
from ..services.templates import FormService

def create_background_image(path: Path) -> None:
    """Create a simple white PNG without external dependencies."""

    width, height = 850, 1100
    path.parent.mkdir(parents=True, exist_ok=True)

    raw = bytearray()
    row = bytes([255, 255, 255] * width)
    for _ in range(height):
        raw.append(0)  # filter type 0
        raw.extend(row)

    compressed = zlib.compress(bytes(raw))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    with path.open("wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", ihdr))
        fh.write(chunk(b"IDAT", compressed))
        fh.write(chunk(b"IEND", b""))


def seed() -> None:
    db.ensure_data_directories()
    service = FormService()

    template_uuid = uuid4().hex
    template_folder = db.TEMPLATES_ROOT / template_uuid
    background_path = template_folder / "background_page_001.png"
    create_background_image(background_path)

    fields = [
        {
            "id": 1,
            "page": 1,
            "name": "incident_commander",
            "type": "text",
            "x": 120.0,
            "y": 160.0,
            "width": 260.0,
            "height": 32.0,
            "font_family": "",
            "font_size": 12,
            "align": "left",
            "required": True,
            "placeholder": "Incident Commander",
            "mask": "",
            "default_value": "",
            "config": {
                "bindings": [
                    {"source_type": "system", "source_ref": "incident.ic_name"}
                ],
                "validations": [
                    {"rule_type": "required", "rule_config": None, "error_message": "Required"}
                ],
                "dropdown": None,
                "table": None,
            },
        }
    ]

    template_id = service.save_template(
        name="Demo ICS Form",
        category="Reference",
        subcategory="Demo",
        background_path=str(template_folder.relative_to(db.DATA_DIR)).replace("\\", "/"),
        page_count=1,
        fields=fields,
    )

    service.create_instance(
        incident_id="INC-DEMO",
        template_id=template_id,
        prefill_ctx={"incident": {"ic_name": "Captain Example"}},
    )
    print(f"Seeded template #{template_id} for incident 'INC-DEMO'.")


if __name__ == "__main__":  # pragma: no cover - manual utility
    seed()

