from __future__ import annotations

import socket
import threading
import time
from http.server import ThreadingHTTPServer

import pytest

from core.networking import ConnectionManager, ConnectionState, LocalServerController, PortUnavailableError
from server.server_manager import SARAppServerManager


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _RunningTestServer:
    def __init__(self, port: int, compatible: bool = True):
        self.port = port
        if compatible:
            manager = SARAppServerManager("127.0.0.1", port, "Test SARApp Server")
            handler = manager.make_handler()
        else:
            from http.server import BaseHTTPRequestHandler

            class handler(BaseHTTPRequestHandler):  # type: ignore[no-redef]
                def do_GET(self):  # noqa: N802
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"not sarapp")

                def log_message(self, format, *args):  # noqa: A002,N802
                    return

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        time.sleep(0.05)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.httpd.shutdown()
        self.thread.join(timeout=2)
        self.httpd.server_close()


def test_local_server_controller_detects_already_running_server():
    port = _free_port()
    with _RunningTestServer(port, compatible=True):
        controller = LocalServerController(port=port)
        assert controller.is_running() is True
        controller.start()
        assert controller.started_by_this_app is False
        assert controller.process is None


def test_local_server_controller_can_start_server_and_wait_for_readiness():
    port = _free_port()
    controller = LocalServerController(port=port)
    try:
        controller.start()
        assert controller.started_by_this_app is True
        assert controller.wait_until_ready(timeout_seconds=5.0) is True
        assert controller.is_running() is True
    finally:
        controller.stop()


def test_starting_local_server_allows_connection_manager_to_connect():
    port = _free_port()
    controller = LocalServerController(port=port)
    manager = ConnectionManager(timeout_seconds=1.0)
    try:
        controller.start()
        assert controller.wait_until_ready(timeout_seconds=5.0) is True
        assert manager.connect_manual("127.0.0.1", port) is True
        snapshot = manager.snapshot
        assert snapshot.state == ConnectionState.LAN
        assert snapshot.is_connected is True
        assert snapshot.is_offline is False
    finally:
        controller.stop()


def test_offline_mode_remains_available_when_server_start_fails():
    port = _free_port()
    manager = ConnectionManager(timeout_seconds=0.2)
    with _RunningTestServer(port, compatible=False):
        controller = LocalServerController(port=port)
        with pytest.raises(PortUnavailableError):
            controller.start()
        manager.work_offline()
        assert manager.snapshot.state == ConnectionState.OFFLINE
        assert manager.snapshot.is_offline is True


def test_manual_connection_still_works():
    port = _free_port()
    manager = ConnectionManager(timeout_seconds=1.0)
    with _RunningTestServer(port, compatible=True):
        assert manager.connect_manual("127.0.0.1", port) is True
        assert manager.snapshot.state == ConnectionState.LAN
        assert manager.snapshot.server_name == "Test SARApp Server"
