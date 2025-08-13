import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils.state import AppState


@pytest.fixture(autouse=True)
def reset_state():
    AppState._active_mission_number = None
    AppState._active_op_period_id = None
    AppState._active_user_id = None
    AppState._active_user_role = None
    yield
    AppState._active_mission_number = None
    AppState._active_op_period_id = None
    AppState._active_user_id = None
    AppState._active_user_role = None


def test_active_mission():
    assert AppState.get_active_mission() is None
    AppState.set_active_mission("mission1")
    assert AppState.get_active_mission() == "mission1"


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
