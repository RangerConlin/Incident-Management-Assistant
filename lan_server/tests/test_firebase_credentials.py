from __future__ import annotations

import os

import pytest

from lan_server import firebase_credentials
from lan_server.server_console.settings import ServerConsoleSettings


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    monkeypatch.delenv("SARAPP_FIREBASE_CREDENTIALS_PATH", raising=False)


def test_resolve_prefers_explicit_upload_over_bundled_default(tmp_path, monkeypatch):
    bundled = tmp_path / "sarapp-mobile-companion-firebase-adminsdk-abc123.json"
    bundled.write_text("{}")
    monkeypatch.setattr(firebase_credentials, "lan_server_dir", lambda: tmp_path)

    uploaded = tmp_path / "uploaded.json"
    uploaded.write_text("{}")
    settings = ServerConsoleSettings(firebase_credentials_path=str(uploaded))

    resolved = firebase_credentials.resolve_credentials_path(settings)

    assert resolved == uploaded


def test_resolve_falls_back_to_bundled_default_when_unconfigured(tmp_path, monkeypatch):
    bundled = tmp_path / "sarapp-mobile-companion-firebase-adminsdk-abc123.json"
    bundled.write_text("{}")
    monkeypatch.setattr(firebase_credentials, "lan_server_dir", lambda: tmp_path)

    settings = ServerConsoleSettings(firebase_credentials_path="")

    resolved = firebase_credentials.resolve_credentials_path(settings)

    assert resolved == bundled


def test_resolve_falls_back_to_bundled_default_when_configured_file_missing(tmp_path, monkeypatch):
    bundled = tmp_path / "sarapp-mobile-companion-firebase-adminsdk-abc123.json"
    bundled.write_text("{}")
    monkeypatch.setattr(firebase_credentials, "lan_server_dir", lambda: tmp_path)

    settings = ServerConsoleSettings(firebase_credentials_path=str(tmp_path / "does-not-exist.json"))

    resolved = firebase_credentials.resolve_credentials_path(settings)

    assert resolved == bundled


def test_resolve_returns_none_when_nothing_available(tmp_path, monkeypatch):
    monkeypatch.setattr(firebase_credentials, "lan_server_dir", lambda: tmp_path)

    resolved = firebase_credentials.resolve_credentials_path(ServerConsoleSettings())

    assert resolved is None


def test_apply_credentials_env_sets_the_env_var(tmp_path, monkeypatch):
    bundled = tmp_path / "sarapp-mobile-companion-firebase-adminsdk-abc123.json"
    bundled.write_text("{}")
    monkeypatch.setattr(firebase_credentials, "lan_server_dir", lambda: tmp_path)

    resolved = firebase_credentials.apply_credentials_env(ServerConsoleSettings())

    assert resolved == bundled
    assert os.environ["SARAPP_FIREBASE_CREDENTIALS_PATH"] == str(bundled)


def test_store_uploaded_credentials_copies_into_settings_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(firebase_credentials, "lan_server_dir", lambda: tmp_path)
    source = tmp_path / "somewhere" / "my-key.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"type": "service_account"}')

    destination = firebase_credentials.store_uploaded_credentials(source)

    assert destination == tmp_path / "settings" / "firebase_credentials.json"
    assert destination.read_text() == '{"type": "service_account"}'
