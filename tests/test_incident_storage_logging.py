from __future__ import annotations

import logging
from pathlib import Path

from utils import incident_storage


def test_layout_initialization_is_quiet_and_idempotent(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(data_dir))
    incident_storage._INITIALIZED_ROOTS.clear()

    calls = 0

    def fake_migrate() -> list[tuple[Path, Path]]:
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(incident_storage, "migrate_legacy_incident_databases", fake_migrate)

    with caplog.at_level(logging.INFO, logger="utils.incident_storage"):
        incident_storage.ensure_layout_initialized()
        incident_storage.ensure_layout_initialized()

    assert calls == 1
    assert not caplog.records
