"""Optional host/container update runner for the cloud dashboard."""

from __future__ import annotations

import os
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class UpdateState:
    running: bool = False
    last_started_at: str | None = None
    last_finished_at: str | None = None
    last_returncode: int | None = None
    last_output: deque[str] = field(default_factory=lambda: deque(maxlen=200))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": bool(update_command()),
                "running": self.running,
                "last_started_at": self.last_started_at,
                "last_finished_at": self.last_finished_at,
                "last_returncode": self.last_returncode,
                "last_output": list(self.last_output),
            }


_STATE = UpdateState()


def update_command() -> str:
    return os.environ.get("CLOUD_UPDATE_COMMAND", "").strip()


def update_state() -> dict[str, Any]:
    return _STATE.snapshot()


def start_update() -> dict[str, Any]:
    command = update_command()
    if not command:
        raise RuntimeError("CLOUD_UPDATE_COMMAND is not configured")
    with _STATE._lock:
        if _STATE.running:
            raise RuntimeError("An update is already running")
        _STATE.running = True
        _STATE.last_started_at = _utcnow()
        _STATE.last_finished_at = None
        _STATE.last_returncode = None
        _STATE.last_output.clear()

    thread = threading.Thread(target=_run_update, args=(command,), daemon=True)
    thread.start()
    return _STATE.snapshot()


def _append(line: str) -> None:
    with _STATE._lock:
        _STATE.last_output.append(line.rstrip())


def _run_update(command: str) -> None:
    returncode = 1
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            _append(line)
        returncode = process.wait(timeout=900)
    except Exception as exc:  # noqa: BLE001 - preserve failure in dashboard state
        _append(f"Update failed: {exc}")
        returncode = 1
    finally:
        with _STATE._lock:
            _STATE.running = False
            _STATE.last_finished_at = _utcnow()
            _STATE.last_returncode = returncode

