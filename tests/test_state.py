import sys
from pathlib import Path
import logging
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.state import AppState


@pytest.fixture(autouse=True)
def reset_state():
    AppState._active_incident_number = None
    AppState._active_op_period_id = None
    AppState._active_user_id = None
    AppState._active_user_role = None
    yield
    AppState._active_incident_number = None
    AppState._active_op_period_id = None
    AppState._active_user_id = None
    AppState._active_user_role = None


def test_active_incident():
    assert AppState.get_active_incident() is None
    AppState.set_active_incident("incident1")
    assert AppState.get_active_incident() == "incident1"


def test_active_op_period():
    assert AppState.get_active_op_period() is None
    AppState.set_active_op_period("op1")
    assert AppState.get_active_op_period() == "op1"


def test_active_user_id():
    assert AppState.get_active_user_id() is None
    AppState.set_active_user_id("user1")
    assert AppState.get_active_user_id() == "user1"


def test_active_user_role():
    assert AppState.get_active_user_role() is None
    AppState.set_active_user_role("admin")
    assert AppState.get_active_user_role() == "admin"


class _BoomSignal:
    def emit(self, *args, **kwargs):
        raise RuntimeError("boom")


def test_set_active_incident_logs_warning_on_signal_failure(monkeypatch, caplog):
    failing = SimpleNamespace(incidentChanged=_BoomSignal())
    monkeypatch.setattr("utils.app_signals.app_signals", failing)
    monkeypatch.setattr("utils.incident_context.set_active_incident", lambda *_: None)
    with caplog.at_level(logging.WARNING):
        AppState.set_active_incident("incident1")
    assert "failed to emit incidentChanged" in caplog.text


def test_set_active_op_period_logs_warning_on_signal_failure(monkeypatch, caplog):
    failing = SimpleNamespace(opPeriodChanged=_BoomSignal())
    monkeypatch.setattr("utils.app_signals.app_signals", failing)
    with caplog.at_level(logging.WARNING):
        AppState.set_active_op_period("op1")
    assert "failed to emit opPeriodChanged" in caplog.text


def test_set_active_user_id_logs_warning_on_signal_failure(monkeypatch, caplog):
    failing = SimpleNamespace(userChanged=_BoomSignal())
    monkeypatch.setattr("utils.app_signals.app_signals", failing)
    with caplog.at_level(logging.WARNING):
        AppState.set_active_user_id("user1")
    assert "failed to emit userChanged" in caplog.text


def test_set_active_user_role_logs_warning_on_signal_failure(monkeypatch, caplog):
    failing = SimpleNamespace(userChanged=_BoomSignal())
    monkeypatch.setattr("utils.app_signals.app_signals", failing)
    with caplog.at_level(logging.WARNING):
        AppState.set_active_user_role("admin")
    assert "failed to emit userChanged" in caplog.text
