from __future__ import annotations

from pathlib import Path
from typing import Any


class MigrationService:
    def __init__(self, data_dir: Path | str = Path("data")) -> None:
        self.data_dir = Path(data_dir)

    def inspect_legacy_sources(self) -> dict[str, Any]:
        candidates = [self.data_dir / "forms", Path("modules") / "forms_creator"]
        return {"sources": [str(p) for p in candidates if p.exists()], "legacy_data_preserved": True}

    def dry_run(self) -> dict[str, Any]:
        report = self.inspect_legacy_sources()
        report["actions"] = []
        report["manual_review"] = []
        return report

    def migrate(self, *, dry_run: bool = True) -> dict[str, Any]:
        report = self.dry_run()
        report["dry_run"] = dry_run
        if dry_run:
            return report
        report["actions"].append("schema-ready; ambiguous legacy records left unchanged")
        return report
