from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import sqlite3
from pathlib import Path
import sys

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "modules" / "operations" / "data" / "repository.py"
spec = importlib.util.spec_from_file_location("team_repository_under_test", MODULE_PATH)
repository = importlib.util.module_from_spec(spec)
sys.modules.setdefault("team_repository_under_test", repository)
sys.modules.setdefault("modules.operations.data.repository", repository)
assert spec and spec.loader is not None
spec.loader.exec_module(repository)


def _init_db(path: Path, *, last_checkin: str, last_status: str) -> None:
    with sqlite3.connect(path) as con:
        con.execute(
            """
            CREATE TABLE teams (
                id INTEGER PRIMARY KEY,
                current_task_id INTEGER,
                name TEXT,
                callsign TEXT,
                status TEXT,
                status_updated TEXT,
                needs_attention INTEGER,
                emergency_flag INTEGER,
                last_checkin_at TEXT,
                checkin_reference_at TEXT,
                team_leader INTEGER
            )
            """
        )
        con.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                title TEXT,
                location TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE personnel (
                id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                contact TEXT,
                email TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE task_teams (
                id INTEGER PRIMARY KEY,
                teamid INTEGER,
                task_id INTEGER,
                sortie_id TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE message_log_entry (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                sender TEXT,
                recipient TEXT
            )
            """
        )

        con.execute(
            "INSERT INTO tasks (id, title, location) VALUES (1, 'Task', 'Loc')"
        )
        con.execute(
            "INSERT INTO personnel (id, name, phone) VALUES (1, 'Lead', '555')"
        )
        con.execute(
            """
            INSERT INTO task_teams (teamid, task_id, sortie_id)
            VALUES (1, 1, 'S1')
            """
        )
        con.execute(
            """
            INSERT INTO teams (
                id,
                current_task_id,
                name,
                callsign,
                status,
                status_updated,
                needs_attention,
                emergency_flag,
                last_checkin_at,
                checkin_reference_at,
                team_leader
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                "Alpha",
                "Alpha",
                "Enroute",
                last_status,
                0,
                0,
                last_checkin,
                last_status,
                1,
            ),
        )
        con.commit()


def _connect_factory(path: Path):
    def _connect() -> sqlite3.Connection:
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        return con

    return _connect


def test_fetch_team_assignment_rows_prefers_persisted_checkin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = datetime.now(timezone.utc) - timedelta(hours=5)
    fresh = baseline + timedelta(hours=4)
    baseline_iso = baseline.isoformat()
    fresh_iso = fresh.isoformat()

    db_path = tmp_path / "incident.db"
    _init_db(db_path, last_checkin=fresh_iso, last_status=baseline_iso)

    monkeypatch.setattr(repository, "_connect", _connect_factory(db_path))

    rows = repository.fetch_team_assignment_rows()

    assert len(rows) == 1
    record = rows[0]
    # Persisted check-in timestamp should be surfaced for both alert logic and UI timers.
    assert record["last_checkin_at"] == fresh_iso
    assert record["last_updated"] == fresh_iso
    # Status-updated timestamps remain available for downstream fallbacks.
    assert record["team_status_updated"] == baseline_iso
