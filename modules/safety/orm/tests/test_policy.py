from __future__ import annotations

import pytest

from modules.safety.orm import service


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


def test_highest_m_allows_approval(orm_app_client):
    service.ensure_form(1001, 1)
    service.add_hazard(1001, 1, _hazard("L hazard", residual="L"))
    service.add_hazard(1001, 1, _hazard("M hazard", residual="M"))
    form = service.ensure_form(1001, 1)
    assert form.highest_residual_risk == "M"
    approved = service.attempt_approval(1001, 1)
    assert approved.status == "approved"


def test_high_risk_blocks(orm_app_client):
    service.ensure_form(1001, 2)
    low = service.add_hazard(1001, 2, _hazard("Base", residual="M"))
    high = service.add_hazard(1001, 2, _hazard("High", residual="H"))
    form = service.ensure_form(1001, 2)
    assert form.highest_residual_risk == "H"
    assert form.approval_blocked is True
    with pytest.raises(service.ApprovalBlockedError):
        service.attempt_approval(1001, 2)

    service.edit_hazard(1001, 2, high.id, _hazard("High", residual="M"))
    form = service.ensure_form(1001, 2)
    assert form.highest_residual_risk == "M"
    assert form.approval_blocked is False

    service.remove_hazard(1001, 2, low.id)
    form = service.ensure_form(1001, 2)
    assert form.highest_residual_risk in {"L", "M"}


def test_delete_highest_updates_state(orm_app_client):
    service.ensure_form(1001, 3)
    h1 = service.add_hazard(1001, 3, _hazard("H", residual="H"))
    h2 = service.add_hazard(1001, 3, _hazard("M", residual="M"))
    form = service.ensure_form(1001, 3)
    assert form.highest_residual_risk == "H"
    service.remove_hazard(1001, 3, h1.id)
    form = service.ensure_form(1001, 3)
    assert form.highest_residual_risk == "M"
    assert form.approval_blocked is False
