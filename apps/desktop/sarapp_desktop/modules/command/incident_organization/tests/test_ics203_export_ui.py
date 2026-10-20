import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from modules.command.incident_organization.panels import incident_organization_panel as panel_module


@pytest.fixture
def export_panel(monkeypatch):
    app = QApplication.instance() or QApplication([])
    panel = panel_module.IncidentOrganizationPanel.__new__(panel_module.IncidentOrganizationPanel)
    QWidget.__init__(panel)
    panel.incident_id = "TEST-203"
    panel.btn_ics203 = QPushButton("Export ICS 203", panel)
    monkeypatch.setattr(panel_module.api_client, "get", lambda *a, **k: [{"id": 7, "number": 3}])
    yield panel
    panel.close()
    app.processEvents()


def test_panel_dispatches_selected_period_and_form_set(monkeypatch, export_panel, tmp_path):
    answers = iter([("OP 3", True), ("USCG", True)])
    monkeypatch.setattr(panel_module.QInputDialog, "getItem", lambda *a, **k: next(answers))
    monkeypatch.setattr(panel_module.QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "203.pdf"), ""))
    workers = []
    class Pool:
        def start(self, worker): workers.append(worker)
    monkeypatch.setattr(panel_module.QThreadPool, "globalInstance", lambda: Pool())
    export_panel._prepare_form("ICS_203")
    assert len(workers) == 1
    assert (workers[0].incident_id, workers[0].period_id, workers[0].form_set_id) == ("TEST-203", 7, "uscg")
    assert not export_panel.btn_ics203.isEnabled()
    monkeypatch.setattr(panel_module.QMessageBox, "warning", lambda *a: None)
    workers[0].signals.failed.emit("Unavailable")
    assert export_panel.btn_ics203.isEnabled()


def test_cancelled_selection_does_not_dispatch(monkeypatch, export_panel):
    monkeypatch.setattr(panel_module.QInputDialog, "getItem", lambda *a, **k: ("", False))
    monkeypatch.setattr(panel_module.QThreadPool, "globalInstance", lambda: pytest.fail("Export dispatched after cancel"))
    export_panel._prepare_form("ICS_203")
    assert export_panel.btn_ics203.isEnabled()
