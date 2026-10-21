"""Stage 5: Team Builder -- combining packages, individuals, substitution,
splitting across teams, and explicit (never implicit) Save as Package.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from modules.admin.resource_packages.data.repository import ApiResourcePackageRepository
from modules.admin.resource_associations.widgets.resource_picker_dialog import ResourcePickerDialog
from modules.operations.teams.data import repository as team_repo
from modules.operations.teams.data.team import Team
from modules.operations.teams.panels.team_builder_window import TeamBuilderWindow, _PackageBrowserDialog


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _status_payload(**overrides):
    payload = {
        "package_id": "pkg-a",
        "package_name": "Ground Team Alpha",
        "checked_in_count": 2,
        "total_count": 3,
        "members": [
            {"resource_type": "personnel", "resource_id": 1, "label": "Alice", "role": "Leader", "checked_in": True},
            {"resource_type": "personnel", "resource_id": 2, "label": "Bob", "role": "Member", "checked_in": True},
            {"resource_type": "personnel", "resource_id": 3, "label": "Carl", "role": "Member", "checked_in": False},
        ],
    }
    payload.update(overrides)
    return payload


def test_package_browser_only_allows_checked_in_members(qt_app: QApplication, monkeypatch) -> None:
    from modules.logistics.checkin import repository as checkin_repo

    monkeypatch.setattr(checkin_repo, "fetch_package_status", lambda pid: _status_payload())
    monkeypatch.setattr(
        ApiResourcePackageRepository,
        "list_packages",
        lambda self, **kw: [_Pkg("pkg-a", "Ground Team Alpha")],
    )
    dialog = _PackageBrowserDialog()
    row_2_checkbox = dialog.table.cellWidget(2, 0)
    assert row_2_checkbox.isEnabled() is False  # Carl (not checked in) can't be pulled in
    row_0_checkbox = dialog.table.cellWidget(0, 0)
    assert row_0_checkbox.isEnabled() is True


class _Pkg:
    def __init__(self, id_, name):
        self.id = id_
        self.name = name


def test_combining_members_from_multiple_packages(qt_app: QApplication, monkeypatch) -> None:
    from modules.logistics.checkin import repository as checkin_repo

    statuses = {
        "pkg-a": _status_payload(package_id="pkg-a", package_name="Alpha"),
        "pkg-b": _status_payload(
            package_id="pkg-b",
            package_name="Bravo",
            members=[{"resource_type": "vehicle", "resource_id": 50, "label": "Engine 2", "role": "", "checked_in": True}],
            checked_in_count=1,
            total_count=1,
        ),
    }
    monkeypatch.setattr(checkin_repo, "fetch_package_status", lambda pid: statuses[pid])
    monkeypatch.setattr(ApiResourcePackageRepository, "list_packages", lambda self, **kw: [])

    window = TeamBuilderWindow()
    try:
        # Simulate picking checked-in rows from package A then package B.
        dialog_a = _PackageBrowserDialog(window)
        dialog_a.package_combo.addItem("Alpha", "pkg-a")
        dialog_a.package_combo.setCurrentIndex(dialog_a.package_combo.count() - 1)
        dialog_a._accept()
        for ref in dialog_a.selected_refs:
            window._append_resource(ref["resource_type"], int(ref["resource_id"]))
        window._source_package_ids.add("pkg-a")

        dialog_b = _PackageBrowserDialog(window)
        dialog_b.package_combo.addItem("Bravo", "pkg-b")
        dialog_b.package_combo.setCurrentIndex(dialog_b.package_combo.count() - 1)
        dialog_b._accept()
        for ref in dialog_b.selected_refs:
            window._append_resource(ref["resource_type"], int(ref["resource_id"]))
        window._source_package_ids.add("pkg-b")

        assert sorted(window._members) == [1, 2]  # Alice + Bob, both checked in
        assert window._vehicles == [50]
        assert window._source_package_ids == {"pkg-a", "pkg-b"}
    finally:
        window.close()


def test_late_arriving_member_never_auto_added(qt_app: QApplication, monkeypatch) -> None:
    """A package member who wasn't checked in when the operator browsed
    the package must never silently appear in the assembled team -- even
    if they check in later, nothing in Team Builder re-adds them on its
    own."""
    from modules.logistics.checkin import repository as checkin_repo

    monkeypatch.setattr(checkin_repo, "fetch_package_status", lambda pid: _status_payload())
    monkeypatch.setattr(ApiResourcePackageRepository, "list_packages", lambda self, **kw: [])
    window = TeamBuilderWindow()
    try:
        dialog = _PackageBrowserDialog(window)
        dialog.package_combo.addItem("Alpha", "pkg-a")
        dialog.package_combo.setCurrentIndex(dialog.package_combo.count() - 1)
        dialog._accept()
        for ref in dialog.selected_refs:
            window._append_resource(ref["resource_type"], int(ref["resource_id"]))
        assert 3 not in window._members  # Carl, not checked in, never added
    finally:
        window.close()


def test_augmenting_package_with_individual(qt_app: QApplication, monkeypatch) -> None:
    window = TeamBuilderWindow()
    try:
        window._append_resource("personnel", 1, "Alice")
        window._append_resource("personnel", 2, "Bob")
        # Augment with an individual not from any package.
        window._append_resource("personnel", 99, "Dana (walk-up volunteer)")
        assert sorted(window._members) == [1, 2, 99]
    finally:
        window.close()


def test_splitting_package_members_across_teams(qt_app: QApplication, monkeypatch) -> None:
    """Two independent Team Builder sessions drawing from the same
    package's checked-in roster must not interfere with each other."""
    from modules.logistics.checkin import repository as checkin_repo

    monkeypatch.setattr(checkin_repo, "fetch_package_status", lambda pid: _status_payload())
    window_a = TeamBuilderWindow()
    window_b = TeamBuilderWindow()
    try:
        window_a._append_resource("personnel", 1, "Alice")
        window_b._append_resource("personnel", 2, "Bob")
        assert window_a._members == [1]
        assert window_b._members == [2]
    finally:
        window_a.close()
        window_b.close()


def test_vehicle_substitution_replaces_entry(qt_app: QApplication, monkeypatch) -> None:
    window = TeamBuilderWindow()
    try:
        window._append_resource("vehicle", 10, "Engine 1")

        def fake_exec(self):
            self.selected_resource_type = "vehicle"
            self.selected_resource_id = 20
            self.selected_label = "Engine 2 (spare)"
            return QDialog.Accepted

        monkeypatch.setattr(ResourcePickerDialog, "exec", fake_exec)
        window.substitute_resource("vehicle", 10)

        assert window._vehicles == [20]
        assert window._lists["vehicle"].count() == 1
        assert window._lists["vehicle"].item(0).text() == "Engine 2 (spare)"
    finally:
        window.close()


def test_activation_reuses_team_repository_save(qt_app: QApplication, monkeypatch) -> None:
    captured = {}

    def fake_save_team(team: Team, **kwargs):
        captured["team"] = team
        team.team_id = 42
        return team

    monkeypatch.setattr(team_repo, "save_team", fake_save_team)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)

    window = TeamBuilderWindow()
    try:
        window.name_edit.setText("GT-9")
        window._append_resource("personnel", 1, "Alice")
        window._activate_team()

        assert captured["team"].name == "GT-9"
        assert captured["team"].members == [1]
        assert window._activated_team_id == 42
        assert window.save_as_package_button.isEnabled() is True
    finally:
        window.close()


def test_readiness_revalidates_on_composition_change_after_activation(qt_app: QApplication, monkeypatch) -> None:
    """Validation must re-run whenever an activated team's composition
    changes, and must read the team's live composition each time rather
    than a cached value."""
    outcomes = iter([
        {"outcome": "Not Ready", "messages": ["Requires 1 additional personnel."]},
        {"outcome": "Ready", "messages": ["All staffing, qualification, and equipment requirements are met."]},
    ])
    validation_calls = []

    def fake_fetch_validation(team_id):
        validation_calls.append(team_id)
        return next(outcomes)

    def fake_save_team(team, **kw):
        team.team_id = 55
        return team

    monkeypatch.setattr(team_repo, "fetch_team_validation", fake_fetch_validation)
    monkeypatch.setattr(team_repo, "save_team", fake_save_team)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)

    window = TeamBuilderWindow()
    try:
        window.name_edit.setText("GT-9")
        window._append_resource("personnel", 1, "Alice")
        window._activate_team()
        assert window.readiness_label.text() == "Readiness: Not Ready"
        assert len(validation_calls) == 1

        window._append_resource("personnel", 2, "Bob")
        assert window.readiness_label.text() == "Readiness: Ready"
        assert len(validation_calls) == 2
    finally:
        window.close()


def test_readiness_not_evaluated_before_activation(qt_app: QApplication) -> None:
    window = TeamBuilderWindow()
    try:
        window._append_resource("personnel", 1, "Alice")
        assert window.readiness_label.text().startswith("Readiness: Not Evaluated")
    finally:
        window.close()


def test_save_as_package_is_explicit_and_separate_from_activation(qt_app: QApplication, monkeypatch) -> None:
    """Activating a team must never, on its own, write a package. Only the
    dedicated Save as Package action does, and it always creates a new
    package rather than silently overwriting a source package."""
    save_calls = []
    monkeypatch.setattr(ApiResourcePackageRepository, "save_package", lambda self, pkg, **kw: save_calls.append(pkg))

    def fake_save_team(team: Team, **kwargs):
        team.team_id = 7
        return team

    monkeypatch.setattr(team_repo, "save_team", fake_save_team)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)

    from modules.admin.resource_packages.windows.resource_package_editor_window import (
        ResourcePackageEditorWindow,
    )

    monkeypatch.setattr(ResourcePackageEditorWindow, "exec", lambda self: QDialog.Accepted)

    window = TeamBuilderWindow()
    try:
        window.name_edit.setText("GT-9")
        window._append_resource("personnel", 1, "Alice")
        window._activate_team()
        assert save_calls == []  # activation alone never writes a package

        window._save_as_package()
        assert len(save_calls) == 1
        assert save_calls[0].id is None  # always a new package, never an overwrite
        assert save_calls[0].resources[0].resource_id == 1
    finally:
        window.close()
