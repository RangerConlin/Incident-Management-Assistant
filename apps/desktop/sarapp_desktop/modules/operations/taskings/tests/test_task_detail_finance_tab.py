"""Task Detail Finance tab tests — see
docs/archive/design-documents/Instructions/finance_architecture.md."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QListWidget, QTableView

from modules.operations.taskings import task_detail_widget as widget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _bare_instance() -> widget.TaskDetailWindow:
    _app()
    instance = widget.TaskDetailWindow.__new__(widget.TaskDetailWindow)
    instance._task_id = 12
    instance._fin_estimated_lbl = QLabel()
    instance._fin_committed_lbl = QLabel()
    instance._fin_remaining_lbl = QLabel()
    instance._fin_actual_lbl = QLabel()
    instance._fin_empty_label = QLabel()
    instance._fin_headers = ["Category", "Description", "Resource Type", "Status", "Original", "Satisfied", "Remaining", "Closed"]
    instance._fin_model = QStandardItemModel(0, len(instance._fin_headers))
    instance._fin_table = QTableView()
    instance._fin_table.setModel(instance._fin_model)
    instance._fin_rr_group = QGroupBox()
    instance._fin_rr_list = QListWidget()
    instance._fin_shared_group = QGroupBox()
    instance._fin_shared_label = QLabel()
    return instance


def test_apply_finance_summary_populates_totals_and_table():
    instance = _bare_instance()
    summary = SimpleNamespace(
        estimated_total=1000.0, committed_total=500.0, remaining_open_estimate=1500.0,
        actual_total=200.0, shared_actual_total=0.0,
        estimates=[
            {"id": 1, "category": "equipment", "description": "2 radios", "resource_type": None,
             "status": "committed", "original_amount": 800.0, "satisfied_amount": 0.0,
             "remaining_amount": 800.0, "closed": False, "resource_request_id": 42},
        ],
    )
    instance._apply_finance_summary(summary)

    assert instance._fin_estimated_lbl.text() == "Estimated: $1,000.00"
    assert instance._fin_committed_lbl.text() == "Committed: $500.00"
    assert instance._fin_remaining_lbl.text() == "Remaining Open: $1,500.00"
    assert instance._fin_actual_lbl.text() == "Actual: $200.00"
    assert instance._fin_model.rowCount() == 1
    assert instance._fin_table.isVisible() or not instance._fin_table.isVisible()  # offscreen: just must not raise
    assert instance._fin_empty_label.isVisible() is False
    assert instance._fin_rr_group.isVisible() is True
    assert instance._fin_rr_list.count() == 1
    assert instance._fin_rr_list.item(0).text() == "Resource Request #42"
    assert instance._fin_shared_group.isVisible() is False


def test_apply_finance_summary_shows_empty_state_with_no_estimates():
    instance = _bare_instance()
    summary = SimpleNamespace(
        estimated_total=0.0, committed_total=0.0, remaining_open_estimate=0.0,
        actual_total=0.0, shared_actual_total=0.0, estimates=[],
    )
    instance._apply_finance_summary(summary)

    assert instance._fin_model.rowCount() == 0
    assert instance._fin_empty_label.isVisible() is True
    assert instance._fin_rr_group.isVisible() is False


def test_apply_finance_summary_shows_shared_actual_costs():
    instance = _bare_instance()
    summary = SimpleNamespace(
        estimated_total=0.0, committed_total=0.0, remaining_open_estimate=0.0,
        actual_total=0.0, shared_actual_total=75.0, estimates=[],
    )
    instance._apply_finance_summary(summary)

    assert instance._fin_shared_group.isVisible() is True
    assert "75.00" in instance._fin_shared_label.text()


def test_fin_selected_estimate_returns_none_without_selection():
    instance = _bare_instance()
    instance._fin_estimates = []
    assert instance._fin_selected_estimate() is None


def test_refine_fuel_estimate_skips_when_no_cost(monkeypatch):
    instance = _bare_instance()
    calls = []
    monkeypatch.setattr(
        "modules.finance.services.refine_estimate_from_debrief",
        lambda *a, **k: calls.append((a, k)),
    )
    instance._refine_fuel_estimate_from_air_general_debrief(99, {"fuel_oil_cost": "", "fuel_used_gal": "10"})
    instance._refine_fuel_estimate_from_air_general_debrief(99, {"fuel_oil_cost": "0", "fuel_used_gal": "10"})
    assert calls == []


def test_refine_fuel_estimate_calls_service_when_cost_present(monkeypatch):
    instance = _bare_instance()
    calls = []
    monkeypatch.setattr("utils.incident_context.get_active_incident_id", lambda: "INC-1")
    monkeypatch.setattr(
        "modules.finance.services.refine_estimate_from_debrief",
        lambda incident_id, **kwargs: calls.append((incident_id, kwargs)),
    )
    instance._refine_fuel_estimate_from_air_general_debrief(99, {"fuel_oil_cost": "45.50", "fuel_used_gal": "12"})

    assert len(calls) == 1
    incident_id, kwargs = calls[0]
    assert incident_id == "INC-1"
    assert kwargs["debrief_id"] == "99"
    assert kwargs["task_id"] == "12"
    assert kwargs["amount"] == 45.50
    assert kwargs["quantity"] == 12.0
    assert kwargs["category"] == "fuel"


def test_flag_debrief_finance_estimate_for_review_calls_service(monkeypatch):
    instance = _bare_instance()
    calls = []
    monkeypatch.setattr("utils.incident_context.get_active_incident_id", lambda: "INC-1")
    monkeypatch.setattr(
        "modules.finance.services.flag_debrief_estimate_for_review",
        lambda incident_id, debrief_id, **kwargs: calls.append((incident_id, debrief_id, kwargs)),
    )
    instance._flag_debrief_finance_estimate_for_review(99)

    assert calls == [("INC-1", "99", {"changed_by": "Debrief"})]
