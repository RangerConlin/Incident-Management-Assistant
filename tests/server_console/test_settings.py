from __future__ import annotations

import pytest

from server.server_console.settings import ServerConsoleSettings, ServerConsoleSettingsStore, validate_port


def test_server_console_settings_load_defaults_when_no_config_exists(tmp_path) -> None:
    store = ServerConsoleSettingsStore(tmp_path / "missing" / "server_console.json")

    settings = store.load()

    assert settings.server_name == "SARApp Incident Server"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8765
    assert settings.discovery_enabled is True


def test_server_console_settings_save_and_reload(tmp_path) -> None:
    path = tmp_path / "settings" / "server_console.json"
    store = ServerConsoleSettingsStore(path)
    expected = ServerConsoleSettings(
        server_name="ICP Server",
        host="127.0.0.1",
        port=9876,
        discovery_enabled=False,
        discovery_port=45455,
    )

    store.save(expected)
    loaded = store.load()

    assert loaded == expected


@pytest.mark.parametrize("value", [0, 65536, "not-a-port"])
def test_invalid_port_validation_fails_cleanly(value) -> None:
    with pytest.raises(ValueError, match="port"):
        validate_port(value)
