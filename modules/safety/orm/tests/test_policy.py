from __future__ import annotations

import sys
from importlib import reload
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest

from utils.state import AppState


@pytest.fixture()
def orm_service(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    from modules.safety.orm import repository, service

    reload(repository)
    reload(service)
    AppState.set_active_incident(1001)
    AppState.set_active_user_id(55)
    return service


def _hazard(sub, residual="L", initial="L"):
    return {
        "sub_activity": sub,
        "hazard_outcome": "Outcome",
        "initial_risk": initial,
        "control_text": "Controls",
        "residual_risk": residual,
        "implement_how": "",
        "implement_who": "",
    }


def test_highest_m_allows_approval(orm_service):
    orm_service.ensure_form(1001, 1)
    orm_service.add_hazard(1001, 1, _hazard("L hazard", residual="L"))
    orm_service.add_hazard(1001, 1, _hazard("M hazard", residual="M"))
    form = orm_service.ensure_form(1001, 1)
    assert form.highest_residual_risk == "M"
    approved = orm_service.attempt_approval(1001, 1)
    assert approved.status == "approved"


def test_high_risk_blocks(orm_service):
    orm_service.ensure_form(1001, 2)
    low = orm_service.add_hazard(1001, 2, _hazard("Base", residual="M"))
    high = orm_service.add_hazard(1001, 2, _hazard("High", residual="H"))
    form = orm_service.ensure_form(1001, 2)
    assert form.highest_residual_risk == "H"
    assert form.approval_blocked is True
    with pytest.raises(orm_service.ApprovalBlockedError):
        orm_service.attempt_approval(1001, 2)

    orm_service.edit_hazard(1001, 2, high.id, _hazard("High", residual="M"))
    form = orm_service.ensure_form(1001, 2)
    assert form.highest_residual_risk == "M"
    assert form.approval_blocked is False

    orm_service.remove_hazard(1001, 2, low.id)
    form = orm_service.ensure_form(1001, 2)
    assert form.highest_residual_risk in {"L", "M"}


def test_delete_highest_updates_state(orm_service):
    orm_service.ensure_form(1001, 3)
    h1 = orm_service.add_hazard(1001, 3, _hazard("H", residual="H"))
    h2 = orm_service.add_hazard(1001, 3, _hazard("M", residual="M"))
    form = orm_service.ensure_form(1001, 3)
    assert form.highest_residual_risk == "H"
    orm_service.remove_hazard(1001, 3, h1.id)
    form = orm_service.ensure_form(1001, 3)
    assert form.highest_residual_risk == "M"
    assert form.approval_blocked is False
