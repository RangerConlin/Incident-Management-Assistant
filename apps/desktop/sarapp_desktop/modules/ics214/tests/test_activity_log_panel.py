"""Desktop behavior for immutable built-in ICS-214 logs."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules.ics214.widgets.activity_log import Ics214ActivityLogPanel


def test_medical_launcher_needs_no_organization_options(monkeypatch):
    app = QApplication.instance() or QApplication([])
    created = []
    monkeypatch.setattr("modules.ics214.services.association_options", lambda _incident: {})
    monkeypatch.setattr("modules.ics214.services.list_operational_periods", lambda _incident: [])
    monkeypatch.setattr("modules.ics214.services.list_entries", lambda _incident, _filters: [])
    monkeypatch.setattr(
        "modules.ics214.services.list_log_definitions",
        lambda _incident: [{
            "id": "builtin:medical_unit",
            "key": "medical_unit",
            "name": "Medical Unit",
            "filters": {"log_keys": ["medical_unit"]},
            "builtin": True,
        }],
    )
    monkeypatch.setattr(
        "modules.ics214.services.create_entry",
        lambda incident, entry: created.append((incident, entry)),
    )

    panel = Ics214ActivityLogPanel("incident-no-org", launch_context={
        "default_log_key": "medical_unit",
        "default_log_name": "Medical Unit",
    })
    assert panel._current_filter().log_keys == ["medical_unit"]
    assert panel.saved_bar_widget.isHidden()
    assert panel.filters_widget.isHidden()
    assert panel.correct_button.isEnabled() is False
    assert panel.void_button.isEnabled() is False

    panel.quick_entry.setText("Patient transported")
    panel.quick_incident_wide.setChecked(True)
    panel._quick_add_entry()

    assert created[0][0] == "incident-no-org"
    assert created[0][1].log_keys == ["medical_unit"]
    assert created[0][1].incident_wide is True
    panel.deleteLater()
    app.processEvents()
