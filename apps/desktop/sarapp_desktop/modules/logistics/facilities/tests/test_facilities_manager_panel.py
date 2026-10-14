from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # pragma: no cover - import guard for environments without Qt libs
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    pytest.skip("PySide6 QtWidgets is unavailable", allow_module_level=True)

from modules.logistics.facilities.models import FacilityRecord
from modules.logistics.facilities.panels import facilities_manager_panel as panel_module
from modules.logistics.facilities.panels.facilities_manager_panel import FacilitiesManagerPanel


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_facilities_manager_uses_passed_incident_id(qt_app: QApplication, monkeypatch) -> None:
    seen_incidents: list[str] = []

    class _FakeService:
        def __init__(self, incident_id=None):
            seen_incidents.append(str(incident_id or ""))

        def list_facilities(self, **kwargs):
            return []

    monkeypatch.setattr(panel_module, "FacilitiesService", _FakeService)

    panel = FacilitiesManagerPanel(incident_id="INC-42")

    assert panel._incident_id() == "INC-42"
    assert seen_incidents == ["INC-42", "INC-42"]


def test_facilities_manager_primary_filter(qt_app: QApplication, monkeypatch) -> None:
    class _FakeService:
        def __init__(self, incident_id=None):
            pass

        def list_facilities(self, **kwargs):
            return [
                FacilityRecord(id="f-1", name="ICP", facility_type="command_post", is_primary=True),
                FacilityRecord(id="f-2", name="Secondary ICP", facility_type="command_post", is_primary=False),
            ]

    monkeypatch.setattr(panel_module, "FacilitiesService", _FakeService)

    panel = FacilitiesManagerPanel(incident_id="INC-42")
    assert panel._list.count() == 2

    panel._primary_only.setChecked(True)

    assert panel._list.count() == 1
    assert "ICP" in panel._list.item(0).text()


def test_facilities_manager_status_color_uses_palette(qt_app: QApplication, monkeypatch) -> None:
    class _Color:
        def __init__(self, value: str) -> None:
            self._value = value

        def name(self) -> str:
            return self._value

    monkeypatch.setattr(
        panel_module,
        "get_palette",
        lambda: {"success": _Color("green"), "danger": _Color("red"), "fg": _Color("black")},
    )

    class _FakeService:
        def __init__(self, incident_id=None):
            pass

        def list_facilities(self, **kwargs):
            return []

    monkeypatch.setattr(panel_module, "FacilitiesService", _FakeService)

    panel = FacilitiesManagerPanel(incident_id="INC-42")
    panel._set_status("Problem", error=True)

    assert "red" in panel._status.styleSheet()
