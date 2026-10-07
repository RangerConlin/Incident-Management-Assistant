"""Coverage for the "last synced" status label shared by Edit-menu catalog
windows (make_sync_status_label/refresh_sync_status_label), added so each
window can show sync state without duplicating the fetch-and-format logic
15 times over.

Requires QT_QPA_PLATFORM=offscreen (see Design Documents/Instructions/
testing_and_qa.md) since it instantiates real Qt widgets.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from utils import api_client as api_client_module
from utils.edit_window_kit import make_sync_status_label, refresh_sync_status_label


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def owner(qapp):
    widget = QWidget()
    yield widget
    widget.deleteLater()


def _wait_for_text_change(label, initial: str, qapp, timeout_s: float = 2.0) -> str:
    import time

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        qapp.processEvents()
        if label.text() != initial:
            return label.text()
        time.sleep(0.02)
    return label.text()


def test_make_sync_status_label_starts_blank(qapp):
    label = make_sync_status_label()
    assert label.text() == ""


def test_refresh_shows_disabled_when_sync_not_configured(owner, qapp, monkeypatch):
    label = make_sync_status_label()
    monkeypatch.setattr(
        api_client_module.api_client, "get",
        lambda *a, **k: {"enabled": False, "central_master_url": "", "pending_count": 0, "last_pulled": {}},
    )

    refresh_sync_status_label(owner, label, "personnel")
    text = _wait_for_text_change(label, "", qapp)

    assert text == "Central catalog sync: disabled"


def test_refresh_shows_not_available_for_unsynced_collection(owner, qapp, monkeypatch):
    label = make_sync_status_label()
    monkeypatch.setattr(
        api_client_module.api_client, "get",
        lambda *a, **k: {
            "enabled": True,
            "central_master_url": "https://central.test",
            "pending_count": 0,
            "last_pulled": {"personnel": None},
        },
    )

    refresh_sync_status_label(owner, label, "task_types")
    text = _wait_for_text_change(label, "", qapp)

    assert text == "Central catalog sync: not available for this catalog yet"


def test_refresh_shows_never_when_not_yet_pulled(owner, qapp, monkeypatch):
    label = make_sync_status_label()
    monkeypatch.setattr(
        api_client_module.api_client, "get",
        lambda *a, **k: {
            "enabled": True,
            "central_master_url": "https://central.test",
            "pending_count": 0,
            "last_pulled": {"personnel": None},
        },
    )

    refresh_sync_status_label(owner, label, "personnel")
    text = _wait_for_text_change(label, "", qapp)

    assert text == "Last synced: never"


def test_refresh_shows_last_pulled_timestamp(owner, qapp, monkeypatch):
    label = make_sync_status_label()
    monkeypatch.setattr(
        api_client_module.api_client, "get",
        lambda *a, **k: {
            "enabled": True,
            "central_master_url": "https://central.test",
            "pending_count": 2,
            "last_pulled": {"personnel": "2026-01-01T00:00:00"},
        },
    )

    refresh_sync_status_label(owner, label, "personnel")
    text = _wait_for_text_change(label, "", qapp)

    assert text.startswith("Last synced: ")
    assert text != "Last synced: never"


def test_refresh_handles_api_error_gracefully(owner, qapp, monkeypatch):
    label = make_sync_status_label()

    def _raise(*_a, **_k):
        raise RuntimeError("server unreachable")

    monkeypatch.setattr(api_client_module.api_client, "get", _raise)

    refresh_sync_status_label(owner, label, "personnel")
    text = _wait_for_text_change(label, "", qapp)

    assert text == "Last synced: unknown"
