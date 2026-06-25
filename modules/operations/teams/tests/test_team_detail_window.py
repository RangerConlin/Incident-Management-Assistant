import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from datetime import datetime, timezone

import pytest
from PySide6.QtWidgets import QApplication

from modules.operations.taskings.models import TaskTeam
from modules.operations.teams.data import repository as team_repo
from modules.operations.teams.data.team import Team
from modules.operations.teams.panels import team_detail_window as team_window
from modules.operations.teams.panels.team_detail_window import TeamDetailBridge, TeamDetailWindow


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_team_detail_window_populates_empty_assigned_unit(qt_app: QApplication) -> None:
    window = TeamDetailWindow()
    try:
        # No active incident in this test environment, so the org chart
        # lookup in _refresh_assignable_units no-ops and only the
        # "Unassigned" sentinel item is present - that's still the
        # correct, safe default for a team with no operational_unit_id.
        window._populate_assigned_unit_selection({"operational_unit_id": None})

        assert window._assigned_unit_combo.count() >= 1
        assert window._assigned_unit_combo.itemData(0) is None
        assert window._assigned_unit_combo.currentIndex() == 0
    finally:
        window.close()


class _FakeApiClient:
    def __init__(self) -> None:
        self.doc: dict = {}
        self.patch_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []

    def get(self, _url: str, **_kwargs):
        return dict(self.doc)

    def patch(self, url: str, json: dict | None = None):
        payload = dict(json or {})
        self.patch_calls.append((url, payload))
        self.doc.update(payload)
        return dict(self.doc)

    def post(self, url: str, json: dict | None = None):
        payload = dict(json or {})
        self.post_calls.append((url, payload))
        self.doc = {"int_id": 9, **payload}
        return dict(self.doc)


def test_team_repository_round_trips_attention_and_asset_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeApiClient()
    monkeypatch.setattr(team_repo, "_client", lambda: client)
    monkeypatch.setattr(team_repo, "_base", lambda: "/api/incidents/INC/operations")

    team = Team(
        team_id=7,
        name="Alpha",
        members=[101, 102],
        vehicles=["11"],
        equipment=["22"],
        aircraft=["33"],
        needs_attention=True,
    )

    team_repo.save_team(team)

    payload = client.patch_calls[-1][1]
    assert json.loads(payload["members_json"]) == [101, 102]
    assert json.loads(payload["vehicles_json"]) == ["11"]
    assert json.loads(payload["equipment_json"]) == ["22"]
    assert json.loads(payload["aircraft_json"]) == ["33"]
    assert payload["needs_attention"] is True

    client.doc.update(
        {
            "int_id": 7,
            "name": "Alpha",
            "members_json": "[101, 102]",
            "vehicles_json": '["11"]',
            "equipment_json": '["22"]',
            "aircraft_json": '["33"]',
            "needs_attention": True,
        }
    )

    loaded = team_repo.get_team(7)

    assert loaded is not None
    assert loaded.members == [101, 102]
    assert loaded.vehicles == ["11"]
    assert loaded.equipment == ["22"]
    assert loaded.aircraft == ["33"]
    assert loaded.needs_attention is True


def test_team_repository_round_trips_operational_unit_id(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeApiClient()
    monkeypatch.setattr(team_repo, "_client", lambda: client)
    monkeypatch.setattr(team_repo, "_base", lambda: "/api/incidents/INC/operations")

    team = Team(team_id=7, name="Alpha", operational_unit_id=42)
    team_repo.save_team(team)

    assert client.patch_calls[-1][1]["operational_unit_id"] == 42

    client.doc.update({"int_id": 7, "name": "Alpha", "operational_unit_id": 42})
    loaded = team_repo.get_team(7)

    assert loaded is not None
    assert loaded.operational_unit_id == 42


def test_team_repository_save_team_explicit_clear_sends_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """A plain save with operational_unit_id=None must NOT send the field at
    all (so it's left untouched server-side, consistent with every other
    None-valued field) - only clear_operational_unit=True should explicitly
    null it out. This matters because operations.py's create_team/update_team
    auto-slots AIR teams onto the Air Ops Branch whenever the key is absent
    from the PATCH body."""
    client = _FakeApiClient()
    monkeypatch.setattr(team_repo, "_client", lambda: client)
    monkeypatch.setattr(team_repo, "_base", lambda: "/api/incidents/INC/operations")

    team = Team(team_id=7, name="Alpha", operational_unit_id=None)
    team_repo.save_team(team)
    assert "operational_unit_id" not in client.patch_calls[-1][1]

    team_repo.save_team(team, clear_operational_unit=True)
    assert client.patch_calls[-1][1]["operational_unit_id"] is None


def test_reset_team_comm_timer_sends_when_key(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeApiClient()
    monkeypatch.setattr(team_repo, "_client", lambda: client)
    monkeypatch.setattr(team_repo, "_base", lambda: "/api/incidents/INC/operations")
    when = datetime(2026, 6, 23, 12, 30, tzinfo=timezone.utc)

    team_repo.reset_team_comm_timer(7, when)

    assert client.patch_calls == [
        ("/api/incidents/INC/operations/teams/7/comm-ping", {"when": when.isoformat(timespec="seconds")})
    ]


def test_team_bridge_removes_members_and_assets_from_persisted_lists(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TeamDetailBridge()
    bridge._team = Team(
        team_id=7,
        members=[101, 102],
        vehicles=["11"],
        equipment=["22"],
        aircraft=["33"],
    )
    saved: list[Team] = []

    monkeypatch.setattr(team_window, "set_person_team", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(team_window, "set_vehicle_team", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(team_window, "set_equipment_team", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(team_window, "set_aircraft_team", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(team_window.team_repo, "save_team", lambda team: saved.append(Team(**team.__dict__)) or team)
    monkeypatch.setattr(TeamDetailBridge, "_team_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(TeamDetailBridge, "_emit_incident_refresh", lambda *_args, **_kwargs: None)

    bridge.removeMember(101)
    bridge.removeVehicle("11")
    bridge.removeEquipment("22")
    bridge.removeAircraft("33")

    assert bridge._team.members == [102]
    assert bridge._team.vehicles == []
    assert bridge._team.equipment == []
    assert bridge._team.aircraft == []
    assert saved[-1].aircraft == []


def test_team_bridge_links_and_unlinks_through_task_team_assignments(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TeamDetailBridge()
    bridge._team = Team(team_id=7, current_task_id=None)
    added: list[tuple[int, int]] = []
    removed: list[tuple[int, int, int | None]] = []

    from modules.operations.taskings import repository as task_repo

    monkeypatch.setattr(task_repo, "add_task_team", lambda task_id, team_id: added.append((task_id, team_id)) or 3)
    monkeypatch.setattr(
        task_repo,
        "list_task_teams",
        lambda _task_id: [
            TaskTeam(
                id=3,
                team_id=7,
                team_name="Alpha",
                team_leader="",
                team_leader_phone="",
                status="Assigned",
            )
        ],
    )
    monkeypatch.setattr(
        task_repo,
        "remove_task_team_from_task",
        lambda task_id, tt_id, team_id=None: removed.append((task_id, tt_id, team_id)),
    )
    monkeypatch.setattr(team_window.TeamDetailBridge, "_emit_incident_refresh", lambda *_args, **_kwargs: None)

    bridge.linkTask(17)
    bridge.unlinkTask(17)

    assert added == [(17, 7)]
    assert removed == [(17, 3, 7)]
    assert bridge._team.current_task_id is None


def test_team_bridge_leader_name_falls_back_to_id(qt_app: QApplication) -> None:
    bridge = TeamDetailBridge()
    bridge._personnel = []

    assert bridge.leaderName(123) == "#123"


def test_team_bridge_load_team_does_not_save_on_read(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TeamDetailBridge()
    saves: list[Team] = []

    monkeypatch.setattr(team_window.team_repo, "get_team", lambda _team_id: Team(team_id=7, name="Alpha"))
    monkeypatch.setattr(team_window.team_repo, "save_team", lambda team: saves.append(team) or team)
    monkeypatch.setattr(team_window, "fetch_team_leader_id", lambda _team_id: None)
    monkeypatch.setattr(TeamDetailBridge, "_refresh_assets", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(TeamDetailBridge, "_auto_set_pilot", lambda *_args, **_kwargs: None)

    bridge.loadTeam(7)

    assert saves == []


def test_team_bridge_open_selected_member_uses_selected_id(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TeamDetailBridge()
    opened: list[str] = []

    class _FakeFinishedSignal:
        def connect(self, _cb) -> None:
            return None

    class _FakeDialog:
        def __init__(self, _parent, personnel_id: str) -> None:
            opened.append(personnel_id)
            self.finished = _FakeFinishedSignal()

        def open(self) -> None:
            return None

    import ui.personnel as personnel_ui

    monkeypatch.setattr(personnel_ui, "PersonnelDetailDialog", _FakeDialog)

    bridge.setSelectedMember("101")
    bridge.openSelectedMember()

    assert opened == ["101"]


def test_team_bridge_does_not_remove_member_from_other_team(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TeamDetailBridge()
    bridge._team = Team(team_id=7, members=[101])
    calls: list[tuple[int, int | None]] = []
    errors: list[str] = []
    bridge.error.connect(errors.append)

    monkeypatch.setattr(team_window, "set_person_team", lambda pid, tid: calls.append((pid, tid)))

    bridge.removeMember(999)

    assert calls == []
    assert bridge._team.members == [101]
    assert errors and "not assigned to this team" in errors[-1].lower()


def test_team_bridge_does_not_clear_assets_from_other_teams(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TeamDetailBridge()
    bridge._team = Team(team_id=7, vehicles=["11"], equipment=["22"], aircraft=["33"])
    vehicle_calls: list[tuple[int, int | None]] = []
    equipment_calls: list[tuple[int, int | None]] = []
    aircraft_calls: list[tuple[int, int | None]] = []
    errors: list[str] = []
    bridge.error.connect(errors.append)

    monkeypatch.setattr(team_window, "set_vehicle_team", lambda aid, tid: vehicle_calls.append((aid, tid)))
    monkeypatch.setattr(team_window, "set_equipment_team", lambda aid, tid: equipment_calls.append((aid, tid)))
    monkeypatch.setattr(team_window, "set_aircraft_team", lambda aid, tid: aircraft_calls.append((aid, tid)))

    bridge.removeVehicle("999")
    bridge.removeEquipment("999")
    bridge.removeAircraft("999")

    assert vehicle_calls == []
    assert equipment_calls == []
    assert aircraft_calls == []
    assert bridge._team.vehicles == ["11"]
    assert bridge._team.equipment == ["22"]
    assert bridge._team.aircraft == ["33"]
    assert len(errors) == 3


def test_team_bridge_refresh_assets_prefers_checkin_identity_for_members(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge = TeamDetailBridge()
    bridge._team = Team(team_id=7, members=[101, 102], vehicles=[], equipment=[], aircraft=[])
    personnel_fallback_calls: list[int] = []

    from modules.logistics.checkin import repository as ci_repo

    class _Identity:
        name = "Alex Pilot"
        primary_role = "Pilot"
        phone = "555-0101"
        callsign = "CAP101"
        home_unit = "Unit 1"

    monkeypatch.setattr(ci_repo, "get_person_identity", lambda pid: _Identity() if str(pid) == "101" else None)
    monkeypatch.setattr(team_window, "fetch_team_personnel", lambda _tid: personnel_fallback_calls.append(_tid) or [])
    monkeypatch.setattr(team_window, "fetch_team_vehicles", lambda _tid: [])
    monkeypatch.setattr(team_window, "fetch_team_equipment", lambda _tid: [])
    monkeypatch.setattr(team_window, "fetch_team_aircraft", lambda _tid: [])

    bridge._refresh_assets()

    assert personnel_fallback_calls == []
    assert [p.get("id") for p in bridge._personnel] == [101, 102]
    assert bridge._personnel[0].get("name") == "Alex Pilot"
    assert bridge._personnel[1].get("name") == "Personnel 102"
