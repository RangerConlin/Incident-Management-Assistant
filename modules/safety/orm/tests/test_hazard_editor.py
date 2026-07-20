from __future__ import annotations

from modules.safety.orm.ui.hazard_editor import HazardEditorDialog


def test_normalize_default_op_period_ids_accepts_active_op_period_dict() -> None:
    assert HazardEditorDialog._normalize_default_op_period_ids(
        {"number": 4, "id": "op-4", "status": "Active"}
    ) == {4}


def test_normalize_default_op_period_ids_falls_back_to_one_for_invalid_values() -> None:
    assert HazardEditorDialog._normalize_default_op_period_ids({}) == {1}
    assert HazardEditorDialog._normalize_default_op_period_ids(None) == {1}

