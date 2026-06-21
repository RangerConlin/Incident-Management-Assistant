from __future__ import annotations

import socket
from datetime import timedelta

from core.networking.connection_manager import ConnectionManager
from core.networking.discovery import DiscoveryClient
from core.networking.heartbeat import HeartbeatTracker
from core.networking.server_info import (
    ConnectionHealth,
    ConnectionMode,
    ConnectionState,
    DiscoveryAnnouncement,
    ServerInfo,
    utc_now,
)
from server.server_manager import SARAppServerManager


def test_discovery_packet_decodes_and_uses_packet_host_for_wildcard_bind() -> None:
    server = ServerInfo(
        server_id="server-1",
        server_name="Incident LAN Server",
        host="0.0.0.0",
        port=8765,
    )
    payload = DiscoveryAnnouncement(server).to_dict()

    decoded = DiscoveryClient._decode_packet(  # noqa: SLF001 - targeted wire-format test
        __import__("json").dumps(payload).encode("utf-8"),
        "192.0.2.10",
    )

    assert decoded is not None
    assert decoded.server_id == "server-1"
    assert decoded.host == "192.0.2.10"
    assert decoded.last_heartbeat is not None


def test_connection_manager_connects_to_local_server_health_endpoint() -> None:
    server = SARAppServerManager(
        host="127.0.0.1",
        port=0,
        server_id="test-server",
        server_name="Test Server",
    )
    server.start()
    try:
        manager = ConnectionManager(request_timeout_seconds=1.0)
        snapshot = manager.connect_to_server(server.server_info, mode=ConnectionMode.LAN)

        assert snapshot.state == ConnectionState.CONNECTED_LAN
        assert snapshot.mode == ConnectionMode.LAN
        assert snapshot.health == ConnectionHealth.HEALTHY
        assert snapshot.server is not None
        assert snapshot.server.connected_timestamp is not None
    finally:
        server.stop()


def test_offline_mode_is_explicit_valid_state() -> None:
    manager = ConnectionManager()

    snapshot = manager.enter_offline_mode()

    assert snapshot.state == ConnectionState.OFFLINE
    assert snapshot.mode == ConnectionMode.OFFLINE
    assert not snapshot.is_connected


def test_heartbeat_tracker_marks_stale_after_timeout() -> None:
    tracker = HeartbeatTracker(timeout_seconds=5)
    server = ServerInfo(server_id="stale-server", server_name="Stale Server")
    observed_at = utc_now() - timedelta(seconds=30)

    tracker.observe(server, observed_at=observed_at)

    assert tracker.health_for("stale-server") == ConnectionHealth.STALE


def test_discovery_client_can_receive_udp_announcement_on_loopback() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])

    server = ServerInfo(
        server_id="udp-server",
        server_name="UDP Server",
        host="127.0.0.1",
        port=8765,
    )

    def send_packet() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            packet = __import__("json").dumps(
                DiscoveryAnnouncement(server).to_dict()
            ).encode("utf-8")
            sock.sendto(packet, ("127.0.0.1", port))

    import threading

    timer = threading.Timer(0.05, send_packet)
    timer.start()
    try:
        servers = DiscoveryClient(port=port, bind_host="127.0.0.1").discover(timeout_seconds=0.5)
    finally:
        timer.cancel()

    assert [item.server_id for item in servers] == ["udp-server"]
