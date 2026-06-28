"""Desktop-side controller for launching the bundled local SARApp server."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .server_info import (
    DEFAULT_LOCAL_SERVER_NAME,
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    HEALTH_PATH,
    build_base_url,
    is_sarapp_health_payload,
)


class LocalServerError(RuntimeError):
    """Raised when the local server cannot be started safely."""


class PortUnavailableError(LocalServerError):
    """Raised when the configured port is occupied by a non-SARApp process."""


class LocalServerController:
    """Start, stop, and probe the local incident server process.

    The desktop app launches the server as a child process instead of importing
    and running it in the Qt process. That keeps the UI responsive and leaves a
    clean seam for future packaging to swap sarapp_server.py for a bundled exe.
    """

    def __init__(self, host: str = DEFAULT_SERVER_HOST, port: int = DEFAULT_SERVER_PORT):
        self.host = host
        self.port = int(port)
        self.process: Optional[subprocess.Popen] = None
        self.started_by_this_app = False
        self.server_name = DEFAULT_LOCAL_SERVER_NAME
        self._log_file = None

    @property
    def base_url(self) -> str:
        return build_base_url(self.host, self.port)

    def _server_script(self) -> Path:
        return Path(__file__).resolve().parents[2] / "sarapp_server.py"

    def _health_payload(self, timeout_seconds: float = 0.5) -> Optional[dict]:
        try:
            with urlopen(f"{self.base_url}{HEALTH_PATH}", timeout=timeout_seconds) as response:
                if response.status != 200:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except (OSError, HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

    def is_running(self) -> bool:
        """Return True only when a compatible SARApp /health endpoint responds."""
        payload = self._health_payload()
        return is_sarapp_health_payload(payload)

    def _is_port_open(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((self.host, self.port)) == 0

    def start(self) -> None:
        """Start the local server unless one is already available."""
        print(f"[LocalServerController] start() called — checking {self.base_url}{HEALTH_PATH}")
        if self.is_running():
            print("[LocalServerController] server already running — reusing")
            self.started_by_this_app = False
            return

        if self._is_port_open():
            raise PortUnavailableError(
                f"Port {self.port} is already in use, but {self.base_url}{HEALTH_PATH} "
                "did not return a compatible SARApp health response."
            )

        script = self._server_script()
        print(f"[LocalServerController] script path: {script} exists={script.exists()}")
        if not script.exists():
            raise LocalServerError(f"Local server script was not found: {script}")

        command = [
            sys.executable,
            str(script),
            "--host", self.host,
            "--port", str(self.port),
            "--name", self.server_name,
        ]
        print(f"[LocalServerController] spawning: {' '.join(command)}")
        log_dir = script.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / "local_server.log"
        # Redirect to a file instead of PIPE — nothing drains a PIPE during normal
        # operation, so once the server's logging fills the OS pipe buffer the
        # child blocks on write() and the whole server (including request
        # handling) freezes.
        self._log_file = open(log_path, "a", encoding="utf-8")
        # CREATE_NEW_PROCESS_GROUP keeps the child server out of the parent
        # console's process group, so a Ctrl+C/Ctrl+Break delivered to the
        # parent (e.g. VS Code stopping/restarting the debug session) does
        # not also kill the server out from under the app.
        popen_kwargs = {}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(script.parent),
                stdin=subprocess.DEVNULL,
                stdout=self._log_file,
                stderr=self._log_file,
                **popen_kwargs,
            )
        except OSError as exc:
            raise LocalServerError(f"Unable to start local SARApp server: {exc}") from exc
        self.started_by_this_app = True
        print(f"[LocalServerController] spawned PID {self.process.pid}")

    def wait_until_ready(self, timeout_seconds: float = 10.0) -> bool:
        """Poll /health until the server is ready or the timeout expires."""
        print(f"[LocalServerController] waiting up to {timeout_seconds}s for {self.base_url}{HEALTH_PATH}")
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                print(f"[LocalServerController] server process exited (rc={self.process.returncode})")
                if self._log_file is not None:
                    print(f"[LocalServerController] see log: {self._log_file.name}")
                return False
            if self.is_running():
                print("[LocalServerController] /health responded — server ready")
                return True
            time.sleep(0.15)
        print("[LocalServerController] timed out waiting for server")
        return False

    def stop(self) -> None:
        """Stop only the child server process this desktop app started."""
        if not self.started_by_this_app or self.process is None:
            return
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
