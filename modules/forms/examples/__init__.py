from __future__ import annotations

import json
from pathlib import Path

_205_path = Path(__file__).with_name("ics_205.example.json")
ics_205_example = json.loads(_205_path.read_text())

__all__ = ["ics_205_example"]
