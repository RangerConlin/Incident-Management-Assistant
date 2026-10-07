"""Unit coverage for the backfill_master_links one-time migration."""
from __future__ import annotations

import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[4]))

import os

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from sarapp_db.migrations.backfill_master_links import _backfill_database, _master_id_by_person_record
from sarapp_db.mongo.database_manager import get_incident_db, get_master_db
from sarapp_db.mongo.master_link import LINKED, ORPHANED
from sarapp_db.mongo.mongo_client import get_client

INCIDENT_ID = "TEST_BACKFILL_MASTER_LINKS"
SERVER_ID = "test-server"


def _reset():
    get_client().drop_database(f"sarapp_incident_{INCIDENT_ID}")
    get_master_db()["personnel"].delete_many({"_id": {"$in": ["TEST-BF-MATCHED"]}})


def test_backfill_links_matched_unmatched_and_leaves_already_linked_alone():
    _reset()
    try:
        get_master_db()["personnel"].insert_one(
            {"_id": "TEST-BF-MATCHED", "person_record": 777001, "name": "Matched Person"}
        )
        col = get_incident_db(INCIDENT_ID)["incident_personnel"]
        col.insert_many(
            [
                {"person_record": 777001, "name": "Matched Person"},  # should link
                {"person_record": 777999, "name": "Unmatched Person"},  # should orphan
                {"name": "Never master-derived"},  # no person_record -> untouched
                {
                    "person_record": 777001,
                    "name": "Already linked",
                    "master_link": {"sync_state": "conflict", "master_id": "existing"},
                },  # should be left alone
            ]
        )

        master_id_by_record = _master_id_by_person_record(get_client())
        stats = _backfill_database(get_incident_db(INCIDENT_ID), master_id_by_record, SERVER_ID, dry_run=False)

        assert stats == {
            "scanned": 4,
            "linked": 1,
            "orphaned": 1,
            "skipped_no_person_record": 1,
            "already_linked": 1,
        }

        matched = col.find_one({"person_record": 777001, "name": "Matched Person"})
        assert matched["master_link"]["sync_state"] == LINKED
        assert matched["master_link"]["master_id"] == "TEST-BF-MATCHED"
        assert matched["master_link"]["master_server_origin"] == SERVER_ID

        unmatched = col.find_one({"person_record": 777999})
        assert unmatched["master_link"]["sync_state"] == ORPHANED
        assert unmatched["master_link"]["master_id"] is None

        untouched = col.find_one({"name": "Never master-derived"})
        assert "master_link" not in untouched

        already_linked = col.find_one({"name": "Already linked"})
        assert already_linked["master_link"]["sync_state"] == "conflict"
    finally:
        _reset()


def test_backfill_dry_run_makes_no_changes():
    _reset()
    try:
        col = get_incident_db(INCIDENT_ID)["incident_personnel"]
        col.insert_one({"person_record": 777001, "name": "Matched Person"})

        master_id_by_record = _master_id_by_person_record(get_client())
        stats = _backfill_database(get_incident_db(INCIDENT_ID), master_id_by_record, SERVER_ID, dry_run=True)

        assert stats["scanned"] == 1
        doc = col.find_one({"person_record": 777001})
        assert "master_link" not in doc
    finally:
        _reset()
