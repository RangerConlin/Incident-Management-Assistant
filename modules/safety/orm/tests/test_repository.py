from __future__ import annotations

import sqlite3
import sys
from importlib import reload
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    from modules.safety.orm import repository

    reload(repository)
    return repository


def test_unique_form_constraint(repo):
    with pytest.raises(sqlite3.IntegrityError):
        with repo.incident_connection(7) as conn:
            repo.insert_form(conn, 7, 1)
            repo.insert_form(conn, 7, 1)


def test_fetch_returns_singleton(repo):
    with repo.incident_connection(9) as conn:
        form = repo.insert_form(conn, 9, 2)
    with repo.incident_connection(9) as conn:
        loaded = repo.fetch_form(conn, 9, 2)
        assert loaded is not None
        assert loaded.id == form.id
        assert loaded.op_period == 2
