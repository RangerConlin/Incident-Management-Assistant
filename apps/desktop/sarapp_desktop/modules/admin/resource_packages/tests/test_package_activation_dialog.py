"""Stage 4: package activation dialog + repository-level integration (no Mongo)."""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog

from modules.admin.resource_packages.widgets.package_activation_dialog import (
    PackageActivationDialog,
    offer_package_activation,
)


@pytest.fixture
def qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _package(**overrides):
    package = {
        "package_id": "pkg-1",
        "package_name": "GT-1",
        "checked_in_count": 1,
        "total_count": 3,
        "members": [
            {"resource_type": "personnel", "resource_id": 1, "label": "Jane", "role": "Leader", "checked_in": True},
            {"resource_type": "personnel", "resource_id": 2, "label": "Bob", "role": "Member", "checked_in": False},
            {"resource_type": "vehicle", "resource_id": 9, "label": "Engine 1", "role": "", "checked_in": False},
        ],
    }
    package.update(overrides)
    return package


def test_already_checked_in_member_has_no_action_combo(qt_app: QApplication) -> None:
    dialog = PackageActivationDialog(_package())
    assert 0 not in dialog._combos  # row 0 (Jane) is already checked in
    assert 1 in dialog._combos
    assert 2 in dialog._combos


def test_confirm_arrived_builds_confirmed_payload(qt_app: QApplication) -> None:
    dialog = PackageActivationDialog(_package())
    dialog._combos[1].setCurrentIndex(1)  # "Confirm Arrived"
    payload = dialog.result_payload()
    assert payload == {
        "confirmed": [{"resource_type": "personnel", "resource_id": 2}],
        "substitutions": [],
        "omitted": [],
    }


def test_omit_builds_omitted_payload(qt_app: QApplication) -> None:
    dialog = PackageActivationDialog(_package())
    dialog._combos[2].setCurrentIndex(3)  # "Omit (not coming)"
    payload = dialog.result_payload()
    assert payload["omitted"] == [{"resource_type": "vehicle", "resource_id": 9}]
    assert payload["confirmed"] == []


def test_pending_rows_never_appear_in_any_payload_list(qt_app: QApplication) -> None:
    """Never auto-check-in an absent member -- rows left at the default
    'Pending' action must not appear anywhere in the result."""
    dialog = PackageActivationDialog(_package())
    payload = dialog.result_payload()
    assert payload == {"confirmed": [], "substitutions": [], "omitted": []}


def test_offer_package_activation_skips_fully_checked_in_packages(qt_app: QApplication, monkeypatch) -> None:
    """No dialog, no API calls, when every member is already checked in."""
    from modules.logistics.checkin import repository as checkin_repo

    monkeypatch.setattr(
        checkin_repo,
        "fetch_package_suggestions",
        lambda rt, rid: [_package(checked_in_count=3, total_count=3)],
    )
    activate_calls = []
    monkeypatch.setattr(checkin_repo, "activate_package", lambda *a, **k: activate_calls.append((a, k)))

    offer_package_activation("personnel", 1, None)
    assert activate_calls == []


def test_offer_package_activation_calls_activate_with_dialog_result(qt_app: QApplication, monkeypatch) -> None:
    from modules.logistics.checkin import repository as checkin_repo

    monkeypatch.setattr(checkin_repo, "fetch_package_suggestions", lambda rt, rid: [_package()])
    activate_calls = []
    monkeypatch.setattr(
        checkin_repo,
        "activate_package",
        lambda package_id, **kwargs: activate_calls.append((package_id, kwargs)),
    )

    def _auto_confirm(self):
        self._combos[1].setCurrentIndex(1)  # Confirm Arrived
        return QDialog.Accepted

    monkeypatch.setattr(PackageActivationDialog, "exec", _auto_confirm)

    offer_package_activation("personnel", 1, None, activated_by="tester")

    assert len(activate_calls) == 1
    package_id, kwargs = activate_calls[0]
    assert package_id == "pkg-1"
    assert kwargs["confirmed"] == [{"resource_type": "personnel", "resource_id": 2}]
    assert kwargs["activated_by"] == "tester"
