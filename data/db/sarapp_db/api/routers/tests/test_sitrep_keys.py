"""Guard the contract between the sitrep operational-summary keys and the UI.

The SITREP panel (modules/command/sitrep/panel.py) reads fixed task/team keys
from the operational summary; these tests fail if the router's normalization
maps drift away from them.
"""
from __future__ import annotations

from sarapp_db.api.routers.sitrep import (
    _MVP_SECTIONS,
    _TASK_STATUS_NORM,
    _TEAM_STATUS_NORM,
    _default_sections,
)

# Keys the panel reads (OperationalSummaryTab and the Current SITREP fact panel).
UI_TASK_KEYS = {"planned", "assigned", "in_progress", "complete", "blocked", "suspended"}
UI_TEAM_KEYS = {"active", "available", "enroute", "returning"}


def test_task_norm_targets_cover_ui_keys():
    assert UI_TASK_KEYS <= set(_TASK_STATUS_NORM.values())


def test_team_norm_targets_cover_ui_keys():
    assert UI_TEAM_KEYS <= set(_TEAM_STATUS_NORM.values())


def test_default_sections_match_mvp_list():
    types = [s["section_type"] for s in _default_sections()]
    assert types == _MVP_SECTIONS
    for s in _default_sections():
        assert s["visibility"] == "internal"
        assert s["review_status"] == "auto_filled"
