from __future__ import annotations

import os

import pytest

try:  # pragma: no cover - import guard for CI environments without Qt libs
    from PySide6 import QtWidgets
except ImportError:  # pragma: no cover
    pytest.skip("PySide6 QtWidgets is unavailable", allow_module_level=True)

from modules.logistics.resource_requests.api.service import ResourceRequestService
from modules.logistics.resource_requests.models.enums import Priority
from modules.logistics.resource_requests.panels.request_detail_panel import ResourceRequestDetailPanel
from modules.logistics.resource_requests.panels.request_list_panel import ResourceRequestListPanel
from modules.logistics.resource_requests.panels.widgets.filters_bar import FiltersBar


class _FakeService:
    def __init__(self) -> None:
        self._records: dict[str, dict[str, object]] = {}
        self._counter = 0

    def create_request(self, header, items):
        self._counter += 1
        request_id = f"REQ-{self._counter}"
        self._records[request_id] = {
            "id": request_id,
            **header,
            "items": list(items),
            "approvals": [],
            "fulfillments": [],
            "audit": [],
            "status": "DRAFT",
            "priority": header.get("priority"),
        }
        return request_id

    def get_request(self, request_id):
        return dict(self._records[request_id])

    def update_request(self, request_id, patch):
        self._records[request_id].update(patch)

    def replace_items(self, request_id, items):
        self._records[request_id]["items"] = list(items)

    def list_requests(self, filters=None):
        return list(self._records.values())


@pytest.fixture(scope="session")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def service(tmp_path):
    return ResourceRequestService("UI-INC", tmp_path / "incident.db")


def test_list_panel_loads(qt_app, service):
    request_id = service.create_request(
        {
            "title": "UI Test",
            "requesting_section": "Logistics",
            "priority": Priority.HIGH.value,
            "created_by_id": "tester",
        },
        [
            {
                "kind": "SUPPLY",
                "description": "Cones",
                "quantity": 10,
                "unit": "ea",
            }
        ],
    )

    panel = ResourceRequestListPanel(service=service)
    panel.refresh()
    assert panel.model.rowCount() >= 1

    # simulate double click to emit signal
    first_index = panel.model.index(0, 0)
    panel.requestActivated.connect(lambda rid: None)
    panel._on_double_click(first_index)


def test_detail_panel_new_and_load(qt_app, service):
    panel = ResourceRequestDetailPanel(service=service)
    panel.start_new()
    panel.title_edit.setText("Water")
    panel.section_edit.setText("Logistics")
    panel.save()
    assert panel.current_request_id is not None

    panel.load_request(panel.current_request_id)
    assert panel.title_edit.text() == "Water"


def test_filters_bar_filters(qt_app):
    bar = FiltersBar()
    status = next(iter(bar.status_buttons.values()))
    status.setChecked(True)
    bar.search_field.setText("med")
    filters = bar.filters()
    assert "status" in filters and "text" in filters


def test_detail_panel_tracks_delivery_facility_with_fake_service(qt_app):
    service = _FakeService()
    panel = ResourceRequestDetailPanel(service=service)
    panel.start_new()
    panel.title_edit.setText("Water")
    panel.section_edit.setText("Logistics")
    panel.delivery_edit.setText("Base Camp")
    panel.delivery_facility_picker.set_value("fac-base", "Base Camp")
    panel.save()

    assert panel.current_request_id is not None
    saved = service.get_request(panel.current_request_id)
    assert saved["delivery_location"] == "Base Camp"
    assert saved["delivery_facility_id"] == "fac-base"
