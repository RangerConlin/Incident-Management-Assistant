from __future__ import annotations

import socket

from lan_server.server_console.controller import ServerConsoleController, check_port, fetch_health
from lan_server.server_console.settings import ServerConsoleSettings


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_server_manager_can_start_and_stop_from_console_controller_code() -> None:
    settings = ServerConsoleSettings(host="127.0.0.1", port=_free_port(), server_name="Controller Test", discovery_enabled=False)
    controller = ServerConsoleController(settings)

    controller.start()
    try:
        assert controller.manager is not None
        assert controller.manager.port == settings.port
        assert controller.state.value == "Running"
    finally:
        controller.stop()

    assert controller.state.value == "Stopped"


def test_health_check_succeeds_while_server_is_running() -> None:
    settings = ServerConsoleSettings(host="127.0.0.1", port=_free_port(), server_name="Health Test", discovery_enabled=False)
    controller = ServerConsoleController(settings)

    controller.start()
    try:
        assert controller.manager is not None
        result = fetch_health(f"http://127.0.0.1:{controller.manager.port}", timeout_seconds=1.0)
    finally:
        controller.stop()

    assert result.ok is True
    assert result.payload is not None
    assert result.payload["server"]["server_name"] == "Health Test"


def test_port_conflict_detection_identifies_running_sarapp_server() -> None:
    settings = ServerConsoleSettings(host="127.0.0.1", port=_free_port(), server_name="Conflict Test", discovery_enabled=False)
    controller = ServerConsoleController(settings)

    controller.start()
    try:
        assert controller.manager is not None
        conflict_settings = ServerConsoleSettings(host="127.0.0.1", port=controller.manager.port)
        result = check_port(conflict_settings, timeout_seconds=1.0)
    finally:
        controller.stop()

    assert result.available is False
    assert result.sarapp_server is True
