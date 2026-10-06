"""Unit tests for BaseRepository.bulk_insert (used by incident import)."""
from __future__ import annotations

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from sarapp_db.mongo.database_manager import get_incident_db
from sarapp_db.mongo.repository import BaseRepository

INCIDENT_ID = "TEST_BULK_INSERT"


class _Repo(BaseRepository):
    collection_name = "teams"


def _clear():
    get_incident_db(INCIDENT_ID)["teams"].delete_many({})


def test_bulk_insert_stamps_missing_defaults_and_preserves_existing_ones():
    _clear()
    repo = _Repo(get_incident_db(INCIDENT_ID))

    inserted = repo.bulk_insert(
        [
            {"name": "Team A"},
            {"_id": "fixed-id", "name": "Team B", "created_at": "2020-01-01T00:00:00", "deleted": True},
        ]
    )
    assert inserted == 2

    docs = {doc["name"]: doc for doc in repo.find_many({}, include_deleted=True)}
    assert docs["Team A"]["deleted"] is False
    assert "created_at" in docs["Team A"]
    assert docs["Team B"]["_id"] == "fixed-id"
    assert docs["Team B"]["created_at"] == "2020-01-01T00:00:00"
    assert docs["Team B"]["deleted"] is True

    _clear()


def test_bulk_insert_empty_list_is_a_noop():
    _clear()
    repo = _Repo(get_incident_db(INCIDENT_ID))
    assert repo.bulk_insert([]) == 0
    assert repo.find_many({}) == []
